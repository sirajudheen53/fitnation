"""Tests for the analytics app (FBOS-030)."""

from datetime import date

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.analytics.models import (
    AttendanceHeatmap,
    MembershipFunnel,
    RevenueReport,
    TopCustomer,
)
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_user, issue_token


class AnalyticsModelTests(TestCase):
    """Unit tests for analytics models and tenant isolation."""

    def setUp(self) -> None:
        """Create two isolated tenants."""
        self.tenant_a = provision_tenant(name="Gym A", contact_email="a@local.test")
        self.tenant_b = provision_tenant(name="Gym B", contact_email="b@local.test")

    def test_revenue_report_requires_tenant(self) -> None:
        """Saving a RevenueReport without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            RevenueReport.objects.create(period=date(2026, 8, 1), amount=1000)

    def test_revenue_report_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's revenue reports."""
        RevenueReport.objects.create(tenant=self.tenant_a, period=date(2026, 8, 1), amount=1000)
        self.assertEqual(RevenueReport.objects.for_tenant(self.tenant_a).count(), 1)
        self.assertEqual(RevenueReport.objects.for_tenant(self.tenant_b).count(), 0)

    def test_revenue_report_unique_per_tenant_period(self) -> None:
        """A second report for the same tenant/period raises IntegrityError."""
        from django.db import IntegrityError

        RevenueReport.objects.create(tenant=self.tenant_a, period=date(2026, 8, 1), amount=1000)
        with self.assertRaises(IntegrityError):
            RevenueReport.objects.create(tenant=self.tenant_a, period=date(2026, 8, 1), amount=2000)

    def test_attendance_heatmap_requires_tenant(self) -> None:
        """Saving an AttendanceHeatmap without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            AttendanceHeatmap.objects.create(date=date(2026, 8, 1), count=5)

    def test_attendance_heatmap_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's heatmap rows."""
        AttendanceHeatmap.objects.create(tenant=self.tenant_a, date=date(2026, 8, 1), count=5)
        self.assertEqual(AttendanceHeatmap.objects.for_tenant(self.tenant_a).count(), 1)
        self.assertEqual(AttendanceHeatmap.objects.for_tenant(self.tenant_b).count(), 0)

    def test_membership_funnel_requires_tenant(self) -> None:
        """Saving a MembershipFunnel without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            MembershipFunnel.objects.create(stage=MembershipFunnel.Stage.ACTIVE, count=3)

    def test_membership_funnel_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's funnel rows."""
        MembershipFunnel.objects.create(
            tenant=self.tenant_a,
            stage=MembershipFunnel.Stage.ACTIVE,
            count=3,
        )
        self.assertEqual(MembershipFunnel.objects.for_tenant(self.tenant_a).count(), 1)
        self.assertEqual(MembershipFunnel.objects.for_tenant(self.tenant_b).count(), 0)

    def test_top_customer_requires_tenant(self) -> None:
        """Saving a TopCustomer without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            TopCustomer.objects.create(customer_id=1, total_spent=5000)

    def test_top_customer_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's top customers."""
        TopCustomer.objects.create(tenant=self.tenant_a, customer_id=1, total_spent=5000)
        self.assertEqual(TopCustomer.objects.for_tenant(self.tenant_a).count(), 1)
        self.assertEqual(TopCustomer.objects.for_tenant(self.tenant_b).count(), 0)

    def test_top_customer_ordering(self) -> None:
        """Top customers are ordered by total_spent descending."""
        TopCustomer.objects.create(tenant=self.tenant_a, customer_id=1, total_spent=1000)
        TopCustomer.objects.create(tenant=self.tenant_a, customer_id=2, total_spent=5000)
        rows = list(TopCustomer.objects.for_tenant(self.tenant_a))
        self.assertEqual(rows[0].customer_id, 2)
        self.assertEqual(rows[1].customer_id, 1)

    def test_str_representations(self) -> None:
        """Each model renders a human-readable string."""
        revenue = RevenueReport.objects.create(tenant=self.tenant_a, period=date(2026, 8, 1), amount=1000)
        self.assertIn("2026-08-01", str(revenue))

        heatmap = AttendanceHeatmap.objects.create(tenant=self.tenant_a, date=date(2026, 8, 1), count=5)
        self.assertIn("2026-08-01", str(heatmap))

        funnel = MembershipFunnel.objects.create(
            tenant=self.tenant_a,
            stage=MembershipFunnel.Stage.ACTIVE,
            count=3,
        )
        self.assertIn("active", str(funnel))

        top = TopCustomer.objects.create(tenant=self.tenant_a, customer_id=1, total_spent=5000)
        self.assertIn("1", str(top))


class AnalyticsAPITests(APITestCase):
    """Integration tests for the analytics endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, auth token, and analytics fixtures."""
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

        RevenueReport.objects.create(tenant=self.tenant, period=date(2026, 8, 1), amount=1000)
        RevenueReport.objects.create(tenant=self.tenant, period=date(2026, 8, 2), amount=2000)
        AttendanceHeatmap.objects.create(tenant=self.tenant, date=date(2026, 8, 1), count=5)
        MembershipFunnel.objects.create(
            tenant=self.tenant,
            stage=MembershipFunnel.Stage.ACTIVE,
            count=3,
        )
        TopCustomer.objects.create(tenant=self.tenant, customer_id=1, total_spent=5000)

    def test_revenue_endpoint(self) -> None:
        """GET revenue/ returns paginated revenue reports."""
        response = self.client.get("/api/v1/analytics/revenue/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["results"][0]["amount"], 2000)

    def test_attendance_heatmap_endpoint(self) -> None:
        """GET attendance/heatmap/ returns paginated heatmap rows."""
        response = self.client.get("/api/v1/analytics/attendance/heatmap/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["count"], 5)

    def test_memberships_funnel_endpoint(self) -> None:
        """GET memberships/funnel/ returns paginated funnel rows."""
        response = self.client.get("/api/v1/analytics/memberships/funnel/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["stage"], "active")

    def test_top_customers_endpoint(self) -> None:
        """GET top-customers/ returns paginated top customers."""
        response = self.client.get("/api/v1/analytics/top-customers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["customer_id"], 1)
        self.assertEqual(response.data["results"][0]["total_spent"], 5000)

    def test_tenant_isolation(self) -> None:
        """A user from another tenant sees no analytics data."""
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

        for url in (
            "/api/v1/analytics/revenue/",
            "/api/v1/analytics/attendance/heatmap/",
            "/api/v1/analytics/memberships/funnel/",
            "/api/v1/analytics/top-customers/",
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 0)
            self.assertEqual(response.data["results"], [])

    def test_unauthenticated_denied(self) -> None:
        """Requests without a token are rejected."""
        self.client.credentials()
        response = self.client.get("/api/v1/analytics/revenue/")
        self.assertEqual(response.status_code, 401)
