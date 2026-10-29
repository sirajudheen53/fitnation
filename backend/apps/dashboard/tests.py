"""Tests for the dashboard app (FBOS-008)."""

from __future__ import annotations

from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.attendance.models import AttendanceRecord
from apps.customers.models import Customer
from apps.dashboard import services
from apps.dashboard.models import DashboardCache
from apps.memberships.models import Membership, MembershipPlan
from apps.payments.models import Payment
from apps.tenants.services import provision_tenant
from apps.trainers.models import TrainerAssignment, TrainerPerformance
from apps.users.models import User
from apps.users.services import create_user, issue_token


def _make_customer(tenant, email):
    """Create a raw customer user and its Customer profile."""
    user = User.objects.create_user(
        email=email,
        password="F1tNati0n!",
        first_name="Customer",
        last_name="User",
        role=User.Role.CUSTOMER,
        tenant=tenant,
    )
    return Customer.objects.create(
        tenant=tenant,
        user=user,
        name=email,
        email=email,
    )


def _make_plan(tenant, name="Monthly", price="1500.00", duration_days=30):
    """Create a membership plan for a tenant."""
    return MembershipPlan.objects.create(
        tenant=tenant,
        name=name,
        price=price,
        duration_days=duration_days,
    )


class DashboardCacheModelTests(TestCase):
    """Unit tests for DashboardCache and tenant isolation."""

    def setUp(self) -> None:
        """Create two isolated tenants."""
        self.tenant_a = provision_tenant(name="Gym A", contact_email="a@local.test")
        self.tenant_b = provision_tenant(name="Gym B", contact_email="b@local.test")

    def test_cache_requires_tenant(self) -> None:
        """Saving a DashboardCache without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            DashboardCache.objects.create(metric_name="overview", metric_value={})

    def test_cache_unique_per_tenant_metric_date(self) -> None:
        """A second cache row for the same tenant/metric/date raises IntegrityError."""
        from django.db import IntegrityError

        DashboardCache.objects.create(
            tenant=self.tenant_a,
            metric_name="overview",
            metric_value={"total_members": 1},
        )
        with self.assertRaises(IntegrityError):
            DashboardCache.objects.create(
                tenant=self.tenant_a,
                metric_name="overview",
                metric_value={"total_members": 2},
            )

    def test_cache_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's cached metrics."""
        DashboardCache.objects.create(
            tenant=self.tenant_a,
            metric_name="overview",
            metric_value={"total_members": 5},
        )
        self.assertEqual(DashboardCache.objects.for_tenant(self.tenant_a).count(), 1)
        self.assertEqual(DashboardCache.objects.for_tenant(self.tenant_b).count(), 0)


class DashboardAPITests(APITestCase):
    """Integration tests for the dashboard endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, customer, plan, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_user(
            tenant=self.tenant,
            email="owner@local.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.plan = _make_plan(self.tenant)
        self.customer = _make_customer(self.tenant, "cust@local.test")

        today = timezone.localdate()
        Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=today,
            end_date=today + timedelta(days=30),
            status=Membership.Status.ACTIVE,
        )
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.UPI,
            status=Payment.Status.COMPLETED,
            paid_at=timezone.now(),
        )
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.PENDING,
        )
        AttendanceRecord.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            check_in_time=timezone.now(),
            date=today,
        )

        self.trainer_user = create_user(
            tenant=self.tenant,
            email="trainer@local.test",
            first_name="Trainer",
            last_name="User",
            role=User.Role.TRAINER,
        )
        self.trainer = self.trainer_user.trainer_profile
        TrainerPerformance.objects.create(
            tenant=self.tenant,
            trainer=self.trainer,
            month=today.replace(day=1),
            revenue="5000.00",
            customer_count=2,
            rating_avg="4.8",
            sessions_completed=10,
        )
        TrainerAssignment.objects.create(
            tenant=self.tenant,
            trainer=self.trainer,
            customer=self.customer,
            is_active=True,
        )

    def test_overview_endpoint(self) -> None:
        """GET overview/ returns the overview shape incl. mrr."""
        response = self.client.get("/api/v1/dashboard/overview/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_members"], 1)
        self.assertEqual(response.data["active_memberships"], 1)
        self.assertEqual(response.data["today_attendance"], 1)
        self.assertEqual(response.data["trainer_count"], 1)
        self.assertEqual(response.data["pending_payments"], 1)
        self.assertEqual(
            response.data["revenue_summary"]["total"],
            1500.0,
        )
        # MRR: single active membership, plan 1500.00 over 30 days → 1500/mo.
        self.assertIn("mrr", response.data)
        self.assertEqual(float(response.data["mrr"]), 1500.0)

    def test_overview_cache_shape_invalidation(self) -> None:
        """A same-day cache row from an older payload shape is recomputed."""
        DashboardCache.objects.create(
            tenant=self.tenant,
            metric_name="overview",
            metric_value={"total_members": 99},
        )
        response = self.client.get("/api/v1/dashboard/overview/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("mrr", response.data)
        self.assertEqual(response.data["total_members"], 1)

    def test_revenue_endpoint(self) -> None:
        """GET revenue/ returns daily/weekly/monthly series with label+amount."""
        response = self.client.get("/api/v1/dashboard/revenue/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data.keys()), {"daily", "weekly", "monthly"})
        for series_name in ("daily", "weekly", "monthly"):
            series = response.data[series_name]
            self.assertGreaterEqual(len(series), 1)
            for point in series:
                self.assertIn("label", point)
                self.assertIn("amount", point)
        # The setUp payment was completed today → present in all three series.
        for series_name in ("daily", "weekly", "monthly"):
            total = sum(p["amount"] for p in response.data[series_name])
            self.assertEqual(total, 1500.0)

    def test_revenue_ignores_period_param(self) -> None:
        """The period query param is accepted (back-compat) and ignored."""
        response = self.client.get("/api/v1/dashboard/revenue/?period=hourly")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data.keys()), {"daily", "weekly", "monthly"})

    def test_attendance_endpoint(self) -> None:
        """GET attendance/ returns peak hours and the 7-day weekly trend."""
        response = self.client.get("/api/v1/dashboard/attendance/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("peak_hours", response.data)
        self.assertIn("weekly_trend", response.data)
        # Every point uses the {hour: <label>, check_ins: <count>} shape.
        for point in response.data["peak_hours"] + response.data["weekly_trend"]:
            self.assertIn("hour", point)
            self.assertIn("check_ins", point)
        self.assertEqual(len(response.data["weekly_trend"]), 7)
        trend_total = sum(p["check_ins"] for p in response.data["weekly_trend"])
        self.assertEqual(trend_total, 1)

    def test_memberships_endpoint(self) -> None:
        """GET memberships/ returns the breakdown and plan distribution."""
        response = self.client.get("/api/v1/dashboard/memberships/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("breakdown", response.data)
        self.assertEqual(response.data["breakdown"]["active"], 1)
        self.assertGreaterEqual(len(response.data["plan_distribution"]), 1)

    def test_trainers_endpoint(self) -> None:
        """GET trainers/ returns a flat TrainerOverviewData[] list."""
        response = self.client.get("/api/v1/dashboard/trainers/")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row["id"], self.trainer.id)
        self.assertEqual(row["revenue"], 5000.0)
        self.assertEqual(row["rating"], 4.8)
        self.assertEqual(row["active_clients"], 1)

    def test_tenant_isolation(self) -> None:
        """Tenant B sees none of tenant A's dashboard data."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_owner = create_user(
            tenant=other_tenant,
            email="other-owner@local.test",
            first_name="Other",
            last_name="Owner",
            role=User.Role.GYM_OWNER,
        )
        other_token = issue_token(other_owner, other_tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")

        response = self.client.get("/api/v1/dashboard/overview/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_members"], 0)
        self.assertEqual(response.data["active_memberships"], 0)
        self.assertEqual(response.data["today_attendance"], 0)
        self.assertEqual(response.data["pending_payments"], 0)

        response = self.client.get("/api/v1/dashboard/revenue/")
        self.assertEqual(response.status_code, 200)
        # Zero-filled series, but no revenue for tenant B.
        self.assertGreaterEqual(len(response.data["daily"]), 1)
        self.assertEqual(sum(p["amount"] for p in response.data["daily"]), 0.0)

    def test_unauthenticated_denied(self) -> None:
        """Requests without a token are rejected."""
        self.client.credentials()
        response = self.client.get("/api/v1/dashboard/overview/")
        self.assertEqual(response.status_code, 401)


class PendingPaymentsDuesTests(APITestCase):
    """Issue #84: a lapsed membership with no covering charge is a pending due.

    Rubric: amount = plan price (the renewal contract), due_date = end_date,
    one due per customer (most recently lapsed membership), suppressed while
    an explicit pending membership-kind payment exists for the customer.
    """

    def setUp(self) -> None:
        """Create tenant, owner, plan, customer and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_user(
            tenant=self.tenant,
            email="owner@local.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.plan = _make_plan(self.tenant, price="1500.00", duration_days=30)
        self.customer = _make_customer(self.tenant, "cust@local.test")

    def _make_lapsed_membership(self, customer=None, plan=None, ended_days_ago=5):
        """Create a membership whose end_date has already passed."""
        today = timezone.localdate()
        return Membership.objects.create(
            tenant=self.tenant,
            customer=customer or self.customer,
            plan=plan or self.plan,
            start_date=today - timedelta(days=ended_days_ago + 30),
            end_date=today - timedelta(days=ended_days_ago),
        )

    def _pending_rows(self) -> list[dict]:
        """Fetch the dashboard pending-payments list."""
        response = self.client.get("/api/v1/dashboard/pending-payments/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def _overview(self) -> dict:
        """Fetch the dashboard overview payload."""
        response = self.client.get("/api/v1/dashboard/overview/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_expired_membership_appears_as_pending_due(self) -> None:
        """The owner's report: expired membership, no payments → not zero."""
        membership = self._make_lapsed_membership()

        rows = self._pending_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], -membership.id)
        self.assertEqual(row["customer_name"], self.customer.name)
        self.assertEqual(row["amount"], 1500.0)
        self.assertEqual(row["due_date"], membership.end_date.isoformat())
        self.assertFalse(row["customer_is_deleted"])
        self.assertEqual(self._overview()["pending_payments"], 1)

    def test_active_membership_is_not_a_due(self) -> None:
        """A membership with end_date in the future is covered — no due."""
        today = timezone.localdate()
        Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=today,
            end_date=today + timedelta(days=30),
        )
        self.assertEqual(self._pending_rows(), [])
        self.assertEqual(self._overview()["pending_payments"], 0)

    def test_cancelled_membership_is_not_a_due(self) -> None:
        """A cancelled membership is a deliberate exit — no due."""
        membership = self._make_lapsed_membership()
        membership.status = Membership.Status.CANCELLED
        membership.save()

        self.assertEqual(self._pending_rows(), [])
        self.assertEqual(self._overview()["pending_payments"], 0)

    def test_stale_active_status_still_lapses_by_date(self) -> None:
        """Lapsedness is judged by end_date, not the stored (stale) status."""
        membership = self._make_lapsed_membership()
        # Bypass save() so the stored status stays "active" past the end_date.
        Membership.objects.filter(pk=membership.pk).update(status=Membership.Status.ACTIVE)

        rows = self._pending_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], -membership.id)

    def test_renewal_clears_the_due(self) -> None:
        """After the renewal endpoint extends the membership, the due is gone."""
        membership = self._make_lapsed_membership()
        response = self.client.post(
            f"/api/v1/memberships/memberships/{membership.id}/renewal/",
            {"days": 30},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self._pending_rows(), [])
        self.assertEqual(self._overview()["pending_payments"], 0)

    def test_pending_membership_payment_suppresses_the_due(self) -> None:
        """An explicit pending membership payment replaces the derived due — no duplicate."""
        membership = self._make_lapsed_membership()
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            membership=membership,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.PENDING,
        )

        rows = self._pending_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], payment.id)
        self.assertNotEqual(rows[0]["id"], -membership.id)
        self.assertEqual(self._overview()["pending_payments"], 1)

    def test_admission_pending_payment_does_not_cover_the_renewal(self) -> None:
        """An admission-fee charge is different money — the membership due stays."""
        membership = self._make_lapsed_membership()
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.PENDING,
            kind=Payment.Kind.ADMISSION,
        )

        rows = self._pending_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["id"] for row in rows}, {payment.id, -membership.id})
        self.assertEqual(self._overview()["pending_payments"], 2)

    def test_completed_payment_does_not_cover_the_renewal(self) -> None:
        """Completed money was for the past period — the lapsed renewal is still owed."""
        membership = self._make_lapsed_membership()
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            membership=membership,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.UPI,
            status=Payment.Status.COMPLETED,
            paid_at=timezone.now(),
        )

        rows = self._pending_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], -membership.id)

    def test_one_due_per_customer_uses_latest_membership(self) -> None:
        """Multiple lapsed memberships collapse to the most recently lapsed one."""
        quarterly = _make_plan(self.tenant, name="Quarterly", price="4000.00", duration_days=90)
        older = self._make_lapsed_membership(ended_days_ago=10)
        latest = self._make_lapsed_membership(plan=quarterly, ended_days_ago=2)

        rows = self._pending_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], -latest.id)
        self.assertNotEqual(rows[0]["id"], -older.id)
        self.assertEqual(rows[0]["amount"], 4000.0)
        self.assertEqual(rows[0]["due_date"], latest.end_date.isoformat())

    def test_deleted_member_due_is_flagged(self) -> None:
        """A soft-deleted member's due stays visible with the deleted marker (#81)."""
        self._make_lapsed_membership()
        self.customer.deleted_at = timezone.now()
        self.customer.save(update_fields=["deleted_at", "updated_at"])

        rows = self._pending_rows()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["customer_is_deleted"])

    def test_dues_are_tenant_scoped(self) -> None:
        """Another tenant sees none of this tenant's dues."""
        self._make_lapsed_membership()
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_owner = create_user(
            tenant=other_tenant,
            email="other-owner@local.test",
            first_name="Other",
            last_name="Owner",
            role=User.Role.GYM_OWNER,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {issue_token(other_owner, other_tenant).key}")

        self.assertEqual(self._pending_rows(), [])
        overview = self._overview()
        self.assertEqual(overview["pending_payments"], 0)
        self.assertEqual(overview["total_members"], 0)

    def test_overview_cache_row_from_before_dues_is_recomputed(self) -> None:
        """A same-day cache row computed before #84 (no marker) is not served."""
        self._make_lapsed_membership()
        DashboardCache.objects.create(
            tenant=self.tenant,
            metric_name="overview",
            # Has "mrr" (passes the old shape check) but no dues marker.
            metric_value={"total_members": 1, "mrr": "0", "pending_payments": 0},
        )

        overview = self._overview()
        self.assertEqual(overview["pending_payments"], 1)

        cached = DashboardCache.objects.for_tenant(self.tenant).get(metric_name="overview")
        self.assertEqual(cached.metric_value.get("pending_dues_semantics"), "issue-84")


class DashboardAggregationTests(TestCase):
    """Issue #82: bucket/boundary semantics of the SQL-aggregated services.

    The dashboard aggregations used to hydrate every payment/check-in row in
    Python; they now group in SQL. These tests pin the bucketing semantics
    that must not drift in that rewrite (week/month boundaries, window edges,
    mixed plan durations).
    """

    def setUp(self) -> None:
        """Create a tenant with one customer and a monthly plan."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.customer = _make_customer(self.tenant, "cust@local.test")
        self.plan = _make_plan(self.tenant, price="1500.00", duration_days=30)

    def _paid(self, amount, paid_at):
        """Create a completed payment at a specific moment."""
        return Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount=amount,
            payment_method=Payment.PaymentMethod.UPI,
            status=Payment.Status.COMPLETED,
            paid_at=paid_at,
        )

    def test_revenue_weekly_buckets_split_at_monday_boundary(self) -> None:
        """A payment one hour before Monday lands in the previous week bucket."""
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())
        inside_week = timezone.make_aware(datetime.combine(monday, dt_time(0, 30)))
        before_week = inside_week - timedelta(hours=1)  # Sunday 23:00
        self._paid("400.00", before_week)
        self._paid("600.00", inside_week)

        weekly = {point["label"]: point["amount"] for point in services.get_revenue_breakdown(self.tenant)["weekly"]}

        # Weekly buckets are labelled by their Monday start.
        self.assertEqual(weekly.get(monday.strftime("%b %d")), 600.0)
        self.assertEqual(weekly.get((monday - timedelta(days=7)).strftime("%b %d")), 400.0)

    def test_revenue_monthly_buckets_split_at_month_boundary(self) -> None:
        """A payment one hour past midnight on the 1st lands in the new month."""
        today = timezone.localdate()
        first_of_month = today.replace(day=1)
        prev_month_last = first_of_month - timedelta(days=1)
        inside_month = timezone.make_aware(datetime.combine(first_of_month, dt_time(0, 30)))
        before_month = timezone.make_aware(datetime.combine(prev_month_last, dt_time(23, 0)))
        self._paid("250.00", before_month)
        self._paid("600.00", inside_month)

        monthly = {point["label"]: point["amount"] for point in services.get_revenue_breakdown(self.tenant)["monthly"]}

        # Monthly buckets are labelled by month start.
        self.assertEqual(monthly.get(first_of_month.strftime("%b %Y")), 600.0)
        self.assertEqual(monthly.get(prev_month_last.replace(day=1).strftime("%b %Y")), 250.0)

    def test_revenue_excludes_payments_older_than_the_window(self) -> None:
        """A 13-month-old payment is outside every series' window."""
        old = timezone.make_aware(datetime(2020, 1, 15, 10, 0))
        self._paid("999.00", old)
        self._paid("250.00", timezone.now())

        data = services.get_revenue_breakdown(self.tenant)

        for series_name in ("daily", "weekly", "monthly"):
            total = sum(point["amount"] for point in data[series_name])
            self.assertEqual(total, 250.0, series_name)

    def test_attendance_trend_counts_per_day_and_drops_old_checkins(self) -> None:
        """The 7-day trend buckets per local day and ignores older check-ins."""
        today = timezone.localdate()
        for days_ago, count in ((0, 2), (3, 1), (6, 1)):
            for _ in range(count):
                moment = timezone.make_aware(datetime.combine(today - timedelta(days=days_ago), dt_time(7, 30)))
                AttendanceRecord.objects.create(
                    tenant=self.tenant,
                    customer=self.customer,
                    check_in_time=moment,
                    date=(today - timedelta(days=days_ago)),
                )
        # 7 days ago: outside the trend window entirely.
        stale = timezone.make_aware(datetime.combine(today - timedelta(days=7), dt_time(8, 0)))
        AttendanceRecord.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            check_in_time=stale,
            date=today - timedelta(days=7),
        )

        data = services.get_attendance_analytics(self.tenant)

        by_label = {point["hour"]: point["check_ins"] for point in data["weekly_trend"]}
        self.assertEqual(len(data["weekly_trend"]), 7)
        self.assertEqual(by_label[(today - timedelta(days=0)).strftime("%a")], 2)
        self.assertEqual(by_label[(today - timedelta(days=3)).strftime("%a")], 1)
        self.assertEqual(by_label[(today - timedelta(days=6)).strftime("%a")], 1)
        self.assertEqual(sum(point["check_ins"] for point in data["weekly_trend"]), 4)

    def test_mrr_mixes_plan_durations_and_skips_zero_length_plans(self) -> None:
        """MRR normalizes each active plan to 30 days; duration 0 contributes 0."""
        quarterly = _make_plan(self.tenant, name="Quarterly", price="4000.00", duration_days=90)
        zero = _make_plan(self.tenant, name="Zero", price="5000.00", duration_days=0)
        today = timezone.localdate()
        for plan in (self.plan, quarterly, zero):
            Membership.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                plan=plan,
                start_date=today,
                end_date=today + timedelta(days=plan.duration_days),
                status=Membership.Status.ACTIVE,
            )

        overview = services.get_overview(self.tenant)

        # MRR normalizes each plan to a 30-day equivalent: 1500*30/30 +
        # 4000*30/90 = 1500 + 1333.33 = 2833.33 (duration 0 skipped).
        self.assertAlmostEqual(float(overview["mrr"]), 2833.33, places=2)

    def test_overview_pending_count_matches_pending_list(self) -> None:
        """The overview's pending count always agrees with the queue list."""
        today = timezone.localdate()
        lapsed = Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=today - timedelta(days=60),
            end_date=today - timedelta(days=5),
        )
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="300.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.PENDING,
            kind=Payment.Kind.ADMISSION,  # does not cover the renewal
        )
        other = _make_customer(self.tenant, "other@local.test")
        Payment.objects.create(
            tenant=self.tenant,
            customer=other,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.PENDING,
            kind=Payment.Kind.MEMBERSHIP,  # covers other's due
        )
        Membership.objects.create(
            tenant=self.tenant,
            customer=other,
            plan=self.plan,
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=2),
        )
        self.assertIsNotNone(lapsed.id)

        overview = services.get_overview(self.tenant)

        self.assertEqual(overview["pending_payments"], len(services.get_pending_payments(self.tenant)))
        # 2 explicit pending rows (admission + other's membership charge)
        # plus 1 uncovered due (the customer's lapsed membership).
        self.assertEqual(overview["pending_payments"], 3)

    def test_revenue_endpoint_row_volume_does_not_scale_queries(self) -> None:
        """GET revenue/ issues a constant, small number of queries (#82)."""
        today = timezone.localdate()
        for i in range(40):
            moment = timezone.make_aware(datetime.combine(today, dt_time(10, i % 60)))
            self._paid(f"{10 + i}.00", moment)

        with CaptureQueriesContext(connection) as ctx:
            services.get_revenue_breakdown(self.tenant)
        # One aggregate query per series (daily/weekly/monthly), regardless
        # of how many payments fall in the window.
        self.assertLessEqual(len(ctx.captured_queries), 6)
