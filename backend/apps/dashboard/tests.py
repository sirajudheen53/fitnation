"""Tests for the dashboard app (FBOS-008)."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.attendance.models import AttendanceRecord
from apps.customers.models import Customer
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
