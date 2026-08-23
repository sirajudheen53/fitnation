"""Tests for the memberships app."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.memberships.models import Coupon, Membership, MembershipPlan
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


class MembershipPlanModelTests(TestCase):
    """Unit tests for the MembershipPlan model."""

    def setUp(self) -> None:
        """Create a tenant for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")

    def test_plan_requires_tenant(self) -> None:
        """Saving a plan without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            MembershipPlan.objects.create(
                name="Monthly",
                plan_type=MembershipPlan.PlanType.MONTHLY,
                price="1500.00",
                duration_days=30,
            )

    def test_plan_name_unique_within_tenant(self) -> None:
        """Plan names are unique within a tenant but reusable across tenants."""
        MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly",
            price="1500.00",
            duration_days=30,
        )
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="other@local.test"
        )
        MembershipPlan.objects.create(
            tenant=other_tenant,
            name="Monthly",
            price="2000.00",
            duration_days=30,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MembershipPlan.objects.create(
                tenant=self.tenant,
                name="Monthly",
                price="1800.00",
                duration_days=30,
            )

    def test_plan_tenant_isolation(self) -> None:
        """Plans are scoped to their tenant."""
        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Yearly",
            price="15000.00",
            duration_days=365,
        )
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="other@local.test"
        )
        self.assertEqual(
            MembershipPlan.objects.for_tenant(self.tenant).first().id,
            plan.id,
        )
        self.assertEqual(MembershipPlan.objects.for_tenant(other_tenant).count(), 0)


class MembershipModelTests(TestCase):
    """Unit tests for the Membership model."""

    def setUp(self) -> None:
        """Create tenant, plan, user, and customer."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly",
            price="1500.00",
            duration_days=30,
        )
        self.user = User.objects.create_user(
            email="cust@local.test",
            password="F1tNati0n!",
            first_name="Cust",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Cust Customer",
            email="cust@local.test",
        )

    def test_membership_status_auto_computed_on_create(self) -> None:
        """A membership with a future end_date is active."""
        membership = Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )
        self.assertEqual(membership.status, Membership.Status.ACTIVE)

    def test_membership_status_expired_when_end_date_passed(self) -> None:
        """A membership whose end_date has passed becomes expired."""
        membership = Membership(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=date.today() - timedelta(days=60),
            end_date=date.today() - timedelta(days=30),
            status=Membership.Status.ACTIVE,
        )
        membership.save()
        membership.refresh_from_db()
        self.assertEqual(membership.status, Membership.Status.EXPIRED)

    def test_membership_cancelled_stays_cancelled(self) -> None:
        """A cancelled membership stays cancelled even after end_date passes."""
        membership = Membership(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=date.today() - timedelta(days=60),
            end_date=date.today() - timedelta(days=30),
            status=Membership.Status.CANCELLED,
        )
        membership.save()
        membership.refresh_from_db()
        self.assertEqual(membership.status, Membership.Status.CANCELLED)

    def test_membership_tenant_isolation(self) -> None:
        """Memberships are scoped to their tenant."""
        membership = Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="other@local.test"
        )
        self.assertEqual(
            Membership.objects.for_tenant(self.tenant).first().id,
            membership.id,
        )
        self.assertEqual(Membership.objects.for_tenant(other_tenant).count(), 0)


class CouponModelTests(TestCase):
    """Unit tests for the Coupon model."""

    def setUp(self) -> None:
        """Create a tenant for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")

    def test_coupon_requires_tenant(self) -> None:
        """Saving a coupon without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            Coupon.objects.create(code="SAVE10", discount_percent="10.00")

    def test_coupon_code_unique_within_tenant(self) -> None:
        """Coupon codes are unique within a tenant but reusable across tenants."""
        Coupon.objects.create(
            tenant=self.tenant,
            code="SAVE10",
            discount_percent="10.00",
        )
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="other@local.test"
        )
        Coupon.objects.create(
            tenant=other_tenant,
            code="SAVE10",
            discount_percent="15.00",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Coupon.objects.create(
                tenant=self.tenant,
                code="SAVE10",
                discount_percent="20.00",
            )

    def test_coupon_tenant_isolation(self) -> None:
        """Coupons are scoped to their tenant."""
        coupon = Coupon.objects.create(
            tenant=self.tenant,
            code="WELCOME",
            discount_percent="5.00",
        )
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="other@local.test"
        )
        self.assertEqual(
            Coupon.objects.for_tenant(self.tenant).first().id,
            coupon.id,
        )
        self.assertEqual(Coupon.objects.for_tenant(other_tenant).count(), 0)


class MembershipAPITests(APITestCase):
    """Integration tests for membership endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, branch, plan, customer, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly",
            price="1500.00",
            duration_days=30,
        )
        self.user = User.objects.create_user(
            email="api-cust@local.test",
            password="F1tNati0n!",
            first_name="API",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="API Customer",
            email="api-cust@local.test",
        )

    def test_list_plans(self) -> None:
        """Owners can list membership plans."""
        response = self.client.get("/api/v1/memberships/membership-plans/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_plan(self) -> None:
        """Owners can create a membership plan."""
        response = self.client.post(
            "/api/v1/memberships/membership-plans/",
            {
                "name": "Yearly",
                "plan_type": "yearly",
                "price": "15000.00",
                "duration_days": 365,
                "description": "Annual membership",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Yearly")

    def test_create_membership(self) -> None:
        """Owners can create a membership with valid dates."""
        response = self.client.post(
            "/api/v1/memberships/memberships/",
            {
                "customer": self.customer.id,
                "plan": self.plan.id,
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=30)).isoformat(),
                "auto_renew": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "active")
        self.assertEqual(response.data["auto_renew"], True)

    def test_create_membership_invalid_dates(self) -> None:
        """Creating a membership with end_date <= start_date is rejected."""
        response = self.client.post(
            "/api/v1/memberships/memberships/",
            {
                "customer": self.customer.id,
                "plan": self.plan.id,
                "start_date": date.today().isoformat(),
                "end_date": date.today().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_list_memberships(self) -> None:
        """Owners can list memberships."""
        Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )
        response = self.client.get("/api/v1/memberships/memberships/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_renewal_action(self) -> None:
        """The renewal action extends end_date and updates status."""
        membership = Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=date.today() - timedelta(days=40),
            end_date=date.today() - timedelta(days=10),
            status=Membership.Status.ACTIVE,
        )
        original_end = membership.end_date
        response = self.client.post(
            f"/api/v1/memberships/memberships/{membership.id}/renewal/",
            {"days": 30},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "active")
        self.assertEqual(
            date.fromisoformat(response.data["end_date"]),
            original_end + timedelta(days=30),
        )

    def test_renewal_uses_plan_duration_when_days_omitted(self) -> None:
        """The renewal action falls back to the plan duration when days omitted."""
        membership = Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=date.today() - timedelta(days=40),
            end_date=date.today() - timedelta(days=10),
            status=Membership.Status.ACTIVE,
        )
        original_end = membership.end_date
        response = self.client.post(
            f"/api/v1/memberships/memberships/{membership.id}/renewal/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            date.fromisoformat(response.data["end_date"]),
            original_end + timedelta(days=30),
        )

    def test_coupon_crud(self) -> None:
        """Owners can create, list, retrieve, and update coupons."""
        create_response = self.client.post(
            "/api/v1/memberships/coupons/",
            {
                "code": "SAVE10",
                "discount_percent": "10.00",
                "max_uses": 100,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        coupon_id = create_response.data["id"]

        list_response = self.client.get("/api/v1/memberships/coupons/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data["results"]), 1)

        retrieve_response = self.client.get(
            f"/api/v1/memberships/coupons/{coupon_id}/"
        )
        self.assertEqual(retrieve_response.status_code, 200)
        self.assertEqual(retrieve_response.data["code"], "SAVE10")

        update_response = self.client.patch(
            f"/api/v1/memberships/coupons/{coupon_id}/",
            {"discount_percent": "15.00"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(float(update_response.data["discount_percent"]), 15.00)

    def test_membership_tenant_isolation(self) -> None:
        """A membership from another tenant is not accessible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        create_owner_user(
            tenant=other_tenant,
            email="other-owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        other_plan = MembershipPlan.objects.create(
            tenant=other_tenant,
            name="Other Plan",
            price="1000.00",
            duration_days=30,
        )
        other_user = User.objects.create_user(
            email="other-cust@local.test",
            password="F1tNati0n!",
            first_name="Other",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        other_customer = Customer.objects.create(
            tenant=other_tenant,
            user=other_user,
            name="Other Customer",
            email="other-cust@local.test",
        )
        other_membership = Membership.objects.create(
            tenant=other_tenant,
            customer=other_customer,
            plan=other_plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )
        response = self.client.get(
            f"/api/v1/memberships/memberships/{other_membership.id}/"
        )
        self.assertEqual(response.status_code, 404)
