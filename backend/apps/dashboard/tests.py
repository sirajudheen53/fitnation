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
        self.assertEqual(
            DashboardCache.objects.for_tenant(self.tenant_a).count(), 1
        )
        self.assertEqual(
            DashboardCache.objects.for_tenant(self.tenant_b).count(), 0
        )


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
        """GET overview/ returns the overview shape."""
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

    def test_revenue_endpoint(self) -> None:
        """GET revenue/ returns a series for daily/weekly/monthly."""
        for period in ("daily", "weekly", "monthly"):
            response = self.client.get(
                f"/api/v1/dashboard/revenue/?period={period}"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["period"], period)
            total = sum(r["amount"] for r in response.data["results"])
            self.assertEqual(total, 1500.0)

    def test_revenue_invalid_period_defaults_monthly(self) -> None:
        """An unknown period defaults to monthly rather than erroring."""
        response = self.client.get("/api/v1/dashboard/revenue/?period=hourly")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["period"], "monthly")

    def test_attendance_endpoint(self) -> None:
        """GET attendance/ returns peak hours and weekly counts."""
        response = self.client.get("/api/v1/dashboard/attendance/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("peak_hours", response.data)
        self.assertIn("weekly_counts", response.data)
        weekly_total = sum(r["count"] for r in response.data["weekly_counts"])
        self.assertEqual(weekly_total, 1)

    def test_memberships_endpoint(self) -> None:
        """GET memberships/ returns status counts and plan distribution."""
        response = self.client.get("/api/v1/dashboard/memberships/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status_counts"]["active"], 1)
        self.assertGreaterEqual(len(response.data["plan_distribution"]), 1)

    def test_trainers_endpoint(self) -> None:
        """GET trainers/ returns the trainer's performance row."""
        response = self.client.get("/api/v1/dashboard/trainers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["revenue"], 5000.0)
        self.assertEqual(row["rating_avg"], 4.8)
        self.assertEqual(row["client_count"], 1)

    def test_tenant_isolation(self) -> None:
        """Tenant B sees none of tenant A's dashboard data."""
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="other@local.test"
        )
        other_owner = create_user(
            tenant=other_tenant,
            email="other-owner@local.test",
            first_name="Other",
            last_name="Owner",
            role=User.Role.GYM_OWNER,
        )
        other_token = issue_token(other_owner, other_tenant)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {other_token.key}"
        )

        response = self.client.get("/api/v1/dashboard/overview/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_members"], 0)
        self.assertEqual(response.data["active_memberships"], 0)
        self.assertEqual(response.data["today_attendance"], 0)
        self.assertEqual(response.data["pending_payments"], 0)

        response = self.client.get("/api/v1/dashboard/revenue/")
        self.assertEqual(response.data["results"], [])

    def test_unauthenticated_denied(self) -> None:
        """Requests without a token are rejected."""
        self.client.credentials()
        response = self.client.get("/api/v1/dashboard/overview/")
        self.assertEqual(response.status_code, 401)
