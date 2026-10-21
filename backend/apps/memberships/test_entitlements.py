"""Entitlement engine tests (FBOS-011 §1 / ADR-003) — the five-state matrix."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.memberships.selectors import EntitlementStatus, get_app_entitlement, get_latest_membership
from apps.tenants.services import provision_tenant
from apps.users.models import User

FLAG_ON = {"app_access": True}


class EntitlementTestBase(TestCase):
    """Shared fixtures: a flagged-on tenant, a plan, and a member."""

    def setUp(self) -> None:
        """One tenant with the rollout flag on + an app-including plan."""
        self.tenant = provision_tenant(name="Hash Fit", contact_email="hash@local.test", features=FLAG_ON)
        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly Unlimited",
            plan_type=MembershipPlan.PlanType.MONTHLY,
            price=2500,
            duration_days=30,
        )

    def create_customer(self, phone: str = "+919900010001") -> Customer:
        """Create a customer profile with a phone-keyed user."""
        user = User.objects.create_user(
            email=f"{phone.replace('+', '')}@fitnation.local",
            password="x",
            first_name="Asha",
            last_name="Nair",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone=phone,
        )
        return Customer.objects.create(tenant=self.tenant, user=user, name="Asha Nair", phone=phone)

    def create_membership(
        self,
        customer: Customer,
        *,
        start_offset: int = -10,
        end_offset: int = 20,
        status: str = Membership.Status.ACTIVE,
        plan: MembershipPlan | None = None,
    ) -> Membership:
        """Create a membership relative to today."""
        today = timezone.localdate()
        return Membership.objects.create(
            tenant=self.tenant,
            customer=customer,
            plan=plan or self.plan,
            start_date=today + timedelta(days=start_offset),
            end_date=today + timedelta(days=end_offset),
            status=status,
        )


class EntitlementMatrixTests(EntitlementTestBase):
    """Every state of get_app_entitlement."""

    def test_active_membership_is_entitled(self) -> None:
        """Active membership on an app-including plan → active, full access."""
        customer = self.create_customer()
        membership = self.create_membership(customer)
        entitlement = get_app_entitlement(customer, tenant=self.tenant)
        self.assertEqual(entitlement.status, EntitlementStatus.ACTIVE)
        self.assertFalse(entitlement.read_only)
        self.assertTrue(entitlement.entitled)
        self.assertEqual(entitlement.membership_id, membership.pk)
        self.assertEqual(entitlement.plan_name, "Monthly Unlimited")
        self.assertIsNone(entitlement.grace_end_date)

    def test_expired_within_grace_is_read_only(self) -> None:
        """Membership ended 3 days ago → grace, read-only, grace date set."""
        customer = self.create_customer()
        membership = self.create_membership(customer, end_offset=-3)
        entitlement = get_app_entitlement(customer, tenant=self.tenant)
        self.assertEqual(entitlement.status, EntitlementStatus.GRACE)
        self.assertTrue(entitlement.read_only)
        self.assertTrue(entitlement.entitled)
        self.assertEqual(entitlement.end_date, membership.end_date)
        self.assertEqual(entitlement.grace_end_date, membership.end_date + timedelta(days=7))

    def test_expired_on_last_grace_day_is_still_grace(self) -> None:
        """end_date + APP_ACCESS_GRACE_DAYS is INCLUSIVE (grace day 7)."""
        customer = self.create_customer()
        self.create_membership(customer, end_offset=-7)
        entitlement = get_app_entitlement(customer, tenant=self.tenant)
        self.assertEqual(entitlement.status, EntitlementStatus.GRACE)

    def test_expired_outside_grace_gates_out(self) -> None:
        """Membership ended 8+ days ago → expired, no access."""
        customer = self.create_customer()
        self.create_membership(customer, end_offset=-8)
        entitlement = get_app_entitlement(customer, tenant=self.tenant)
        self.assertEqual(entitlement.status, EntitlementStatus.EXPIRED)
        self.assertFalse(entitlement.read_only)
        self.assertFalse(entitlement.entitled)

    def test_no_membership_is_none(self) -> None:
        """A customer who never bought anything → none (same gate as expired)."""
        customer = self.create_customer()
        entitlement = get_app_entitlement(customer, tenant=self.tenant)
        self.assertEqual(entitlement.status, EntitlementStatus.NONE)
        self.assertFalse(entitlement.entitled)
        self.assertIsNone(entitlement.plan_name)

    def test_plan_without_app_access_is_none(self) -> None:
        """A plan that excludes the app → none even while ACTIVE."""
        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Gym Only",
            price=1000,
            duration_days=30,
            includes_app_access=False,
        )
        customer = self.create_customer()
        membership = self.create_membership(customer, plan=plan)
        entitlement = get_app_entitlement(customer, tenant=self.tenant)
        self.assertEqual(entitlement.status, EntitlementStatus.NONE)
        self.assertEqual(entitlement.membership_id, membership.pk)
        self.assertFalse(entitlement.plan_includes_app_access)

    def test_cancelled_membership_gets_no_grace(self) -> None:
        """Cancellation is a business act — immediate revoke, no grace."""
        customer = self.create_customer()
        self.create_membership(customer, end_offset=-1, status=Membership.Status.CANCELLED)
        entitlement = get_app_entitlement(customer, tenant=self.tenant)
        self.assertEqual(entitlement.status, EntitlementStatus.NONE)

    def test_tenant_flag_off_disables_the_engine(self) -> None:
        """Rollout flag off → none for everyone (legacy tenants unaffected)."""
        unflagged = provision_tenant(name="Legacy Gym", contact_email="legacy@local.test")
        plan = MembershipPlan.objects.create(tenant=unflagged, name="M", price=100, duration_days=30)
        user = User.objects.create_user(
            email="flag@fitnation.local",
            password="x",
            first_name="F",
            last_name="L",
            role=User.Role.CUSTOMER,
            tenant=unflagged,
        )
        customer = Customer.objects.create(tenant=unflagged, user=user, name="Flag Less")
        Membership.objects.create(
            tenant=unflagged,
            customer=customer,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=20),
        )
        entitlement = get_app_entitlement(customer, tenant=unflagged)
        self.assertEqual(entitlement.status, EntitlementStatus.NONE)

    def test_max_end_date_selection_ignores_history_rows(self) -> None:
        """Several rows → the non-cancelled one with the max end_date wins."""
        customer = self.create_customer()
        self.create_membership(customer, end_offset=-40)  # old history row
        self.create_membership(customer, end_offset=-2, status=Membership.Status.CANCELLED)
        current = self.create_membership(customer, end_offset=15)
        self.assertEqual(get_latest_membership(customer).pk, current.pk)
        self.assertEqual(get_app_entitlement(customer, tenant=self.tenant).status, EntitlementStatus.ACTIVE)

    def test_as_payload_shape(self) -> None:
        """The mobile contract: status + read_only + plan copy, ISO dates."""
        customer = self.create_customer()
        self.create_membership(customer)
        payload = get_app_entitlement(customer, tenant=self.tenant).as_payload()
        self.assertEqual(
            sorted(payload.keys()),
            ["end_date", "grace_end_date", "plan_name", "read_only", "status"],
        )
        self.assertEqual(payload["status"], "active")
        self.assertFalse(payload["read_only"])
        self.assertEqual(payload["plan_name"], "Monthly Unlimited")


class MembershipPlanFieldTests(EntitlementTestBase):
    """B1 acceptance: plan CRUD round-trips the flag; default True backfill."""

    def test_default_is_true(self) -> None:
        """New plans default to including app access (launch decision D1)."""
        plan = MembershipPlan.objects.create(tenant=self.tenant, name="Quarterly", price=6000, duration_days=90)
        self.assertTrue(plan.includes_app_access)

    def test_serializer_round_trips_flag(self) -> None:
        """The serializer exposes the flag for the ERP plan form toggle."""
        from apps.memberships.serializers import MembershipPlanSerializer  # noqa: PLC0415

        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="No App",
            price=100,
            duration_days=30,
            includes_app_access=False,
        )
        data = MembershipPlanSerializer(plan).data
        self.assertIn("includes_app_access", data)
        self.assertFalse(data["includes_app_access"])
