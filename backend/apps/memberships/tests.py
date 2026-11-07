"""Tests for the memberships app."""

from datetime import date, timedelta
from typing import ClassVar
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.memberships.models import Coupon, Membership, MembershipPlan
from apps.memberships.services import MEMBERSHIP_OVERLAP_CODE
from apps.memberships.views import MembershipViewSet
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


def _offset_day(offset: int) -> date:
    """Return today shifted by ``offset`` days (naive local test date)."""
    return date.today() + timedelta(days=offset)  # noqa: DTZ011 — naive local test date


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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
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
            start_date=date.today(),  # noqa: DTZ011 — naive local test date
            end_date=date.today() + timedelta(days=30),  # noqa: DTZ011 — naive local test date
        )
        self.assertEqual(membership.status, Membership.Status.ACTIVE)

    def test_membership_status_expired_when_end_date_passed(self) -> None:
        """A membership whose end_date has passed becomes expired."""
        membership = Membership(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=date.today() - timedelta(days=60),  # noqa: DTZ011 — naive local test date
            end_date=date.today() - timedelta(days=30),  # noqa: DTZ011 — naive local test date
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
            start_date=date.today() - timedelta(days=60),  # noqa: DTZ011 — naive local test date
            end_date=date.today() - timedelta(days=30),  # noqa: DTZ011 — naive local test date
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
            start_date=date.today(),  # noqa: DTZ011 — naive local test date
            end_date=date.today() + timedelta(days=30),  # noqa: DTZ011 — naive local test date
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
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
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
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
                "start_date": date.today().isoformat(),  # noqa: DTZ011 — naive local test date
                "end_date": (date.today() + timedelta(days=30)).isoformat(),  # noqa: DTZ011 — naive local test date
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
                "start_date": date.today().isoformat(),  # noqa: DTZ011 — naive local test date
                "end_date": date.today().isoformat(),  # noqa: DTZ011 — naive local test date
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
            start_date=date.today(),  # noqa: DTZ011 — naive local test date
            end_date=date.today() + timedelta(days=30),  # noqa: DTZ011 — naive local test date
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
            start_date=date.today() - timedelta(days=40),  # noqa: DTZ011 — naive local test date
            end_date=date.today() - timedelta(days=10),  # noqa: DTZ011 — naive local test date
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
            start_date=date.today() - timedelta(days=40),  # noqa: DTZ011 — naive local test date
            end_date=date.today() - timedelta(days=10),  # noqa: DTZ011 — naive local test date
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

        retrieve_response = self.client.get(f"/api/v1/memberships/coupons/{coupon_id}/")
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
            start_date=date.today(),  # noqa: DTZ011 — naive local test date
            end_date=date.today() + timedelta(days=30),  # noqa: DTZ011 — naive local test date
        )
        response = self.client.get(f"/api/v1/memberships/memberships/{other_membership.id}/")
        self.assertEqual(response.status_code, 404)


class MembershipRenewalPlanSwapAPITests(APITestCase):
    """Renewal with an optional plan_id moves the membership to that plan (#68)."""

    def setUp(self) -> None:
        """Create tenant, owner token, two plans, a foreign plan, and a member."""
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
        self.other_plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Quarterly",
            price="4000.00",
            duration_days=90,
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.foreign_plan = MembershipPlan.objects.create(
            tenant=other_tenant,
            name="Foreign Plan",
            price="1000.00",
            duration_days=60,
        )
        self.user = User.objects.create_user(
            email="swap-cust@local.test",
            password="F1tNati0n!",
            first_name="Swap",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Swap Customer",
            email="swap-cust@local.test",
        )

    def _membership(self) -> Membership:
        """Create an expired-on-dates membership ending 10 days ago."""
        return Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=date.today() - timedelta(days=40),  # noqa: DTZ011 — naive local test date
            end_date=date.today() - timedelta(days=10),  # noqa: DTZ011 — naive local test date
            status=Membership.Status.ACTIVE,
        )

    def _renewal_url(self, membership: Membership) -> str:
        """Return the renewal action URL for a membership."""
        return f"/api/v1/memberships/memberships/{membership.id}/renewal/"

    def test_renewal_with_plan_id_swaps_plan_and_uses_new_plan_duration(self) -> None:
        """plan_id without days switches the plan; default days = new plan's duration."""
        membership = self._membership()
        original_end = membership.end_date
        response = self.client.post(
            self._renewal_url(membership),
            {"plan_id": self.other_plan.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["plan"], self.other_plan.id)
        self.assertEqual(response.data["plan_name"], "Quarterly")
        self.assertEqual(
            date.fromisoformat(response.data["end_date"]),
            original_end + timedelta(days=90),
        )
        membership.refresh_from_db()
        self.assertEqual(membership.plan_id, self.other_plan.id)
        self.assertEqual(membership.status, Membership.Status.ACTIVE)
        # Same membership row is renewed — no new record is created.
        self.assertEqual(Membership.objects.for_tenant(self.tenant).count(), 1)

    def test_renewal_with_plan_id_and_explicit_days_prefers_days(self) -> None:
        """An explicit days wins over the new plan's duration."""
        membership = self._membership()
        original_end = membership.end_date
        response = self.client.post(
            self._renewal_url(membership),
            {"plan_id": self.other_plan.id, "days": 7},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["plan"], self.other_plan.id)
        self.assertEqual(
            date.fromisoformat(response.data["end_date"]),
            original_end + timedelta(days=7),
        )

    def test_renewal_rejects_foreign_tenant_plan(self) -> None:
        """A plan belonging to another tenant is rejected and changes nothing."""
        membership = self._membership()
        response = self.client.post(
            self._renewal_url(membership),
            {"plan_id": self.foreign_plan.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("plan_id", response.data)
        membership.refresh_from_db()
        self.assertEqual(membership.plan_id, self.plan.id)
        self.assertEqual(
            membership.end_date,
            date.today() - timedelta(days=10),  # noqa: DTZ011 — naive local test date
        )

    def test_renewal_rejects_unknown_plan(self) -> None:
        """A plan id that does not exist is rejected with a helpful detail."""
        membership = self._membership()
        response = self.client.post(
            self._renewal_url(membership),
            {"plan_id": 999999},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("plan_id", response.data)

    def test_renewal_rejects_non_integer_plan_id(self) -> None:
        """A non-integer plan id is rejected with a helpful detail."""
        membership = self._membership()
        response = self.client.post(
            self._renewal_url(membership),
            {"plan_id": "not-a-number"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("plan_id", response.data)

    def test_days_only_renewal_keeps_current_plan(self) -> None:
        """Legacy days-only renewal still extends the same plan."""
        membership = self._membership()
        original_end = membership.end_date
        response = self.client.post(
            self._renewal_url(membership),
            {"days": 30},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["plan"], self.plan.id)
        membership.refresh_from_db()
        self.assertEqual(membership.plan_id, self.plan.id)
        self.assertEqual(membership.end_date, original_end + timedelta(days=30))

    def test_plan_swap_renewal_propagates_access_change(self) -> None:
        """A plan-swap renewal still pushes the access change downstream."""
        membership = self._membership()
        with mock.patch.object(MembershipViewSet, "_propagate_access_change") as propagate:
            response = self.client.post(
                self._renewal_url(membership),
                {"plan_id": self.other_plan.id},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(propagate.call_count, 1)
        self.assertEqual(propagate.call_args.args[0].plan_id, self.other_plan.id)

    def test_days_only_renewal_propagates_access_change(self) -> None:
        """A legacy days-only renewal keeps propagating the access change."""
        membership = self._membership()
        with mock.patch.object(MembershipViewSet, "_propagate_access_change") as propagate:
            response = self.client.post(
                self._renewal_url(membership),
                {"days": 30},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(propagate.call_count, 1)


class MembershipPlanPlanTypeAPITests(APITestCase):
    """Integration tests for plan_type values on the plan endpoints."""

    plan_types: ClassVar[list[str]] = ["quarterly", "half_yearly", "pt", "trial"]

    def setUp(self) -> None:
        """Create tenant, owner, auth token, and an editable plan."""
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

    def test_create_plan_with_each_plan_type(self) -> None:
        """Owners can create plans with quarterly, half_yearly, pt, and trial."""
        for plan_type in self.plan_types:
            with self.subTest(plan_type=plan_type):
                response = self.client.post(
                    "/api/v1/memberships/membership-plans/",
                    {
                        "name": f"Plan {plan_type}",
                        "plan_type": plan_type,
                        "price": "1000.00",
                        "duration_days": 90,
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.data["plan_type"], plan_type)
                self.assertTrue(
                    MembershipPlan.objects.filter(
                        tenant=self.tenant,
                        name=f"Plan {plan_type}",
                        plan_type=plan_type,
                    ).exists(),
                )

    def test_update_plan_with_each_plan_type(self) -> None:
        """PUT accepts every supported plan_type on an existing plan."""
        for plan_type in self.plan_types:
            with self.subTest(plan_type=plan_type):
                response = self.client.put(
                    f"/api/v1/memberships/membership-plans/{self.plan.id}/",
                    {
                        "name": "Monthly",
                        "plan_type": plan_type,
                        "price": "1500.00",
                        "duration_days": 30,
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["plan_type"], plan_type)
                self.plan.refresh_from_db()
                self.assertEqual(self.plan.plan_type, plan_type)

    def test_partial_update_plan_with_each_plan_type(self) -> None:
        """PATCH accepts every supported plan_type on an existing plan."""
        for plan_type in self.plan_types:
            with self.subTest(plan_type=plan_type):
                response = self.client.patch(
                    f"/api/v1/memberships/membership-plans/{self.plan.id}/",
                    {"plan_type": plan_type},
                    format="json",
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["plan_type"], plan_type)
                self.plan.refresh_from_db()
                self.assertEqual(self.plan.plan_type, plan_type)

    def test_create_plan_invalid_plan_type(self) -> None:
        """Creating a plan with an unsupported plan_type is rejected."""
        response = self.client.post(
            "/api/v1/memberships/membership-plans/",
            {
                "name": "Weekly",
                "plan_type": "weekly",
                "price": "500.00",
                "duration_days": 7,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("plan_type", response.data)

    def test_update_plan_invalid_plan_type(self) -> None:
        """Updating a plan with an unsupported plan_type is rejected."""
        response = self.client.patch(
            f"/api/v1/memberships/membership-plans/{self.plan.id}/",
            {"plan_type": "weekly"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("plan_type", response.data)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.plan_type, "monthly")


class MembershipOverlapGuardAPITests(APITestCase):
    """Overlap guard on membership writes (#104).

    Owner decision on the issue: BLOCK the overlapping membership — no
    auto-supersede. A member never holds two ACTIVE memberships whose
    periods overlap; the 400 names the conflicting row (id, plan, period).
    Cancelled/expired rows don't count, and a renewal extending its own row
    is never a self-overlap.
    """

    def setUp(self) -> None:
        """Create tenant, owner token, two plans, and a member."""
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
        self.quarterly_plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Quarterly",
            price="4000.00",
            duration_days=90,
        )
        self.user = User.objects.create_user(
            email="overlap-cust@local.test",
            password="F1tNati0n!",
            first_name="Overlap",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Overlap Customer",
            email="overlap-cust@local.test",
        )

    def _create_membership(
        self,
        *,
        start_offset: int,
        end_offset: int,
        plan: MembershipPlan | None = None,
        status: str = Membership.Status.ACTIVE,
        customer: Customer | None = None,
    ) -> Membership:
        """Persist a membership row; ``save()`` syncs status from dates."""
        return Membership.objects.create(
            tenant=self.tenant,
            customer=customer or self.customer,
            plan=plan or self.plan,
            start_date=_offset_day(start_offset),
            end_date=_offset_day(end_offset),
            status=status,
        )

    def _post_membership(self, start: date, end: date, **extra: object):
        """POST a create payload covering ``[start, end]`` for the member."""
        payload = {
            "customer": self.customer.id,
            "plan": self.plan.id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            **extra,
        }
        return self.client.post("/api/v1/memberships/memberships/", payload, format="json")

    def test_create_overlapping_active_membership_blocked(self) -> None:
        """A create overlapping an ACTIVE membership is rejected with the overlap code."""
        existing = self._create_membership(start_offset=0, end_offset=30)
        response = self._post_membership(_offset_day(10), _offset_day(40))
        self.assertEqual(response.status_code, 400)
        error = response.data["non_field_errors"][0]
        self.assertEqual(error.code, MEMBERSHIP_OVERLAP_CODE)
        self.assertEqual(Membership.objects.for_tenant(self.tenant).count(), 1)
        # The rejection is the existing row — nothing was superseded.
        self.assertIn(f"#{existing.id}", str(error))

    def test_create_contained_within_active_membership_blocked(self) -> None:
        """A period fully inside an ACTIVE membership overlaps."""
        self._create_membership(start_offset=0, end_offset=30)
        response = self._post_membership(_offset_day(5), _offset_day(10))
        self.assertEqual(response.status_code, 400)
        self.assertIn("non_field_errors", response.data)

    def test_create_error_names_plan_and_period_of_conflicting_row(self) -> None:
        """The message cites the conflicting membership's plan and period."""
        existing = self._create_membership(start_offset=0, end_offset=30)
        response = self._post_membership(_offset_day(5), _offset_day(20))
        self.assertEqual(response.status_code, 400)
        message = str(response.data["non_field_errors"][0])
        self.assertIn(f"#{existing.id}", message)
        self.assertIn("Monthly", message)
        self.assertIn(_offset_day(0).isoformat(), message)
        self.assertIn(_offset_day(30).isoformat(), message)

    def test_create_starting_on_active_end_date_blocked(self) -> None:
        """Boundary dates are inclusive: starting on the active end_date shares that day."""
        self._create_membership(start_offset=0, end_offset=30)
        response = self._post_membership(_offset_day(30), _offset_day(60))
        self.assertEqual(response.status_code, 400)

    def test_create_starting_day_after_active_end_allowed(self) -> None:
        """A successor starting the day after the active end_date does not overlap."""
        self._create_membership(start_offset=0, end_offset=30)
        response = self._post_membership(_offset_day(31), _offset_day(60))
        self.assertEqual(response.status_code, 201)

    def test_create_against_expired_membership_allowed(self) -> None:
        """Expired rows don't count — a new period overlapping an expired one is fine."""
        self._create_membership(start_offset=-60, end_offset=-30)  # save() stores EXPIRED
        response = self._post_membership(_offset_day(-40), _offset_day(5))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "active")

    def test_create_against_cancelled_membership_allowed(self) -> None:
        """Cancelled rows don't count as conflicts."""
        self._create_membership(start_offset=0, end_offset=30, status=Membership.Status.CANCELLED)
        response = self._post_membership(_offset_day(10), _offset_day(40))
        self.assertEqual(response.status_code, 201)

    def test_create_backfill_ending_in_past_overlapping_active_allowed(self) -> None:
        """A backfill ending before today is born expired — it can never hold ACTIVE."""
        self._create_membership(start_offset=-5, end_offset=30)
        response = self._post_membership(_offset_day(-10), _offset_day(-1))
        self.assertEqual(response.status_code, 201)
        created = Membership.objects.for_tenant(self.tenant).order_by("id").last()
        assert created is not None
        self.assertEqual(created.status, Membership.Status.EXPIRED)

    def test_create_same_period_for_different_customer_allowed(self) -> None:
        """The guard is per member — another customer's identical period is fine."""
        self._create_membership(start_offset=0, end_offset=30)
        other_user = User.objects.create_user(
            email="overlap-other@local.test",
            password="F1tNati0n!",
            first_name="Other",
            last_name="Member",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        other_customer = Customer.objects.create(
            tenant=self.tenant,
            user=other_user,
            name="Other Member",
            email="overlap-other@local.test",
        )
        payload = {
            "customer": other_customer.id,
            "plan": self.plan.id,
            "start_date": _offset_day(0).isoformat(),
            "end_date": _offset_day(30).isoformat(),
        }
        response = self.client.post("/api/v1/memberships/memberships/", payload, format="json")
        self.assertEqual(response.status_code, 201)

    def test_patch_dates_into_active_overlap_blocked(self) -> None:
        """An edit that moves a row onto an ACTIVE neighbour's period is rejected."""
        self._create_membership(start_offset=0, end_offset=30)
        target = self._create_membership(start_offset=40, end_offset=70)
        response = self.client.patch(
            f"/api/v1/memberships/memberships/{target.id}/",
            {"start_date": _offset_day(20).isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["non_field_errors"][0].code, MEMBERSHIP_OVERLAP_CODE)
        target.refresh_from_db()
        self.assertEqual(target.start_date, _offset_day(40))

    def test_patch_dates_up_to_adjacent_allowed(self) -> None:
        """An edit stopping the day before the neighbour's start is accepted."""
        self._create_membership(start_offset=0, end_offset=30)
        target = self._create_membership(start_offset=40, end_offset=70)
        response = self.client.patch(
            f"/api/v1/memberships/memberships/{target.id}/",
            {"start_date": _offset_day(31).isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_patch_plan_change_without_date_change_allowed(self) -> None:
        """A plan swap on a non-overlapping active row passes the guard."""
        target = self._create_membership(start_offset=0, end_offset=30)
        response = self.client.patch(
            f"/api/v1/memberships/memberships/{target.id}/",
            {"plan": self.quarterly_plan.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.plan_id, self.quarterly_plan.id)

    def test_patch_cancelled_membership_dates_over_active_allowed(self) -> None:
        """A cancelled row keeps that status regardless of dates — never a conflict."""
        self._create_membership(start_offset=0, end_offset=30)
        cancelled = self._create_membership(start_offset=-10, end_offset=5, status=Membership.Status.CANCELLED)
        response = self.client.patch(
            f"/api/v1/memberships/memberships/{cancelled.id}/",
            {
                "start_date": _offset_day(10).isoformat(),
                "end_date": _offset_day(40).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        cancelled.refresh_from_db()
        self.assertEqual(cancelled.status, Membership.Status.CANCELLED)


class MembershipRenewalOverlapGuardAPITests(APITestCase):
    """Renewal extension may not reach into another ACTIVE membership (#104).

    The renewed row itself is excluded — extending the same membership is
    never a self-overlap — but an extension (with or without a plan swap)
    that would overlap a different active membership is blocked with a 400
    naming that row, before anything is mutated.
    """

    def setUp(self) -> None:
        """Create tenant, owner token, two plans, and a member."""
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
        self.quarterly_plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Quarterly",
            price="4000.00",
            duration_days=90,
        )
        self.user = User.objects.create_user(
            email="renewal-overlap-cust@local.test",
            password="F1tNati0n!",
            first_name="Renewal",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Renewal Customer",
            email="renewal-overlap-cust@local.test",
        )

    def _create_membership(
        self,
        *,
        start_offset: int,
        end_offset: int,
        plan: MembershipPlan | None = None,
        status: str = Membership.Status.ACTIVE,
    ) -> Membership:
        """Persist a membership row; ``save()`` syncs status from dates."""
        return Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=plan or self.plan,
            start_date=_offset_day(start_offset),
            end_date=_offset_day(end_offset),
            status=status,
        )

    def _renewal_response(self, membership: Membership, payload: dict):
        """POST the renewal action for a membership."""
        return self.client.post(
            f"/api/v1/memberships/memberships/{membership.id}/renewal/",
            payload,
            format="json",
        )

    def test_renewal_extending_into_active_membership_blocked(self) -> None:
        """An extension reaching into a later ACTIVE membership is rejected, row untouched."""
        target = self._create_membership(start_offset=-40, end_offset=-10)  # stored EXPIRED
        later = self._create_membership(start_offset=5, end_offset=35)
        response = self._renewal_response(target, {"days": 20})  # new end = today+10
        self.assertEqual(response.status_code, 400)
        error = response.data["non_field_errors"][0]
        self.assertEqual(error.code, MEMBERSHIP_OVERLAP_CODE)
        self.assertIn(f"#{later.id}", str(error))
        target.refresh_from_db()
        self.assertEqual(target.end_date, _offset_day(-10))
        self.assertEqual(target.status, Membership.Status.EXPIRED)

    def test_renewal_plan_swap_into_active_membership_blocked(self) -> None:
        """A plan-swap renewal whose extension overlaps is rejected before mutation."""
        target = self._create_membership(start_offset=-40, end_offset=-10)
        later = self._create_membership(start_offset=5, end_offset=35)
        response = self._renewal_response(target, {"plan_id": self.quarterly_plan.id, "days": 20})
        self.assertEqual(response.status_code, 400)
        self.assertIn(f"#{later.id}", str(response.data["non_field_errors"][0]))
        target.refresh_from_db()
        self.assertEqual(target.plan_id, self.plan.id)
        self.assertEqual(target.end_date, _offset_day(-10))

    def test_renewal_extension_stopping_before_active_membership_allowed(self) -> None:
        """An extension ending the day before the next membership starts is accepted."""
        target = self._create_membership(start_offset=-40, end_offset=-10)
        self._create_membership(start_offset=25, end_offset=55)
        response = self._renewal_response(target, {"days": 30})  # new end = today+20
        self.assertEqual(response.status_code, 200)
        self.assertEqual(date.fromisoformat(response.data["end_date"]), _offset_day(20))

    def test_renewal_of_own_row_is_not_an_overlap(self) -> None:
        """Extending the same membership never conflicts with itself (#104 edge case)."""
        target = self._create_membership(start_offset=-40, end_offset=-10)
        response = self._renewal_response(target, {"days": 30})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "active")
        self.assertEqual(date.fromisoformat(response.data["end_date"]), _offset_day(20))
        self.assertEqual(Membership.objects.for_tenant(self.tenant).count(), 1)
