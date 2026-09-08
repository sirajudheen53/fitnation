"""Tests for the core app shared utilities."""

from io import StringIO

from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.utils import timezone as dj_timezone
from rest_framework.test import APITestCase

from apps.core.qa_seed.common import PASSWORDS
from apps.customers.models import Customer
from apps.diet.models import DietPlan, FoodItem
from apps.exercises.models import Exercise
from apps.memberships.models import Membership
from apps.permissions.models import Role
from apps.tenants.models import Tenant
from apps.users.models import User
from apps.workouts.models import WorkoutPlan


class HealthCheckTests(APITestCase):
    """Tests for the liveness/readiness health endpoint."""

    def test_health_endpoint_returns_healthy(self) -> None:
        """The health endpoint reports database and cache status."""
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["db"], "ok")


def _run_seed_qa(*args: str) -> StringIO:
    """Run the seed_qa command, capturing output."""
    out = StringIO()
    call_command("seed_qa", *args, stdout=out)
    return out


class SeedQACommandTests(APITestCase):
    """Tests for the unified ``seed_qa`` management command."""

    def test_core_seed_is_idempotent(self) -> None:
        """Default run creates the QA inventory; a second run changes nothing."""
        _run_seed_qa()
        _run_seed_qa()

        # Platform admin
        admin = User.objects.get(email="admin@fitnation.test")
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, "platform_admin")
        self.assertEqual(admin.tenant.name, "FitNation Test Gym")
        self.assertTrue(check_password(PASSWORDS["admin"], admin.password))

        # FitGym A / B tenants are ACTIVE with their owners + customers
        for tenant_name, owner_email, customer_email in [
            ("FitGym A", "owner_a@fitgyma.qa", "customer_a@fitgyma.qa"),
            ("FitGym B", "owner_b@fitgymb.qa", "customer_b@fitgymb.qa"),
        ]:
            tenant = Tenant.objects.get(name=tenant_name)
            self.assertEqual(tenant.status, Tenant.Status.ACTIVE)
            owner = User.objects.get(email=owner_email)
            self.assertEqual(owner.tenant, tenant)
            self.assertEqual(owner.role, "gym_owner")
            self.assertTrue(check_password(PASSWORDS["tenant_ab"], owner.password))
            customer = User.objects.get(email=customer_email)
            self.assertEqual(customer.tenant, tenant)
            self.assertEqual(customer.role, "customer")
            self.assertTrue(Customer.objects.filter(user=customer).exists())

        # Tenant-1 staff + IronHouse staff
        owner_t1 = User.objects.get(email="owner@fitnation.test")
        self.assertEqual(owner_t1.tenant.name, "FitNation Test Gym")
        self.assertEqual(owner_t1.role, "gym_owner")
        self.assertTrue(check_password(PASSWORDS["tenant1_staff"], owner_t1.password))
        owner_iron = User.objects.get(email="owner.iron@fitnation.test")
        self.assertEqual(owner_iron.tenant.name, "IronHouse Fitness")
        self.assertTrue(check_password(PASSWORDS["tenant2_staff"], owner_iron.password))

        # Idempotency: re-running did not duplicate anything
        self.assertEqual(User.objects.filter(email__endswith="fitgyma.qa").count(), 2)
        # FitNation Test Gym + FitGym A + FitGym B + IronHouse Fitness
        self.assertEqual(Tenant.objects.count(), 4)

        # Catalogs seeded
        t1 = Tenant.objects.get(name="FitNation Test Gym")
        iron = Tenant.objects.get(name="IronHouse Fitness")
        self.assertTrue(Exercise.objects.filter(tenant=t1).exists())
        self.assertTrue(Exercise.objects.filter(tenant=iron).exists())
        self.assertTrue(FoodItem.objects.exists())
        self.assertTrue(Role.objects.exists())

        # All QA users can actually authenticate (documented passwords)
        for email, password in [
            ("admin@fitnation.test", PASSWORDS["admin"]),
            ("owner_a@fitgyma.qa", PASSWORDS["tenant_ab"]),
            ("owner@fitnation.test", PASSWORDS["tenant1_staff"]),
            ("owner.iron@fitnation.test", PASSWORDS["tenant2_staff"]),
        ]:
            user = User.objects.get(email=email)
            self.assertTrue(check_password(password, user.password), f"{email} password broken")

    def test_realistic_flag_seeds_full_dataset(self) -> None:
        """--realistic adds customers, memberships, diet and workout plans."""
        _run_seed_qa("--realistic")

        self.assertGreaterEqual(Customer.objects.count(), 20 + 14)
        self.assertTrue(Membership.objects.exists())
        self.assertTrue(DietPlan.objects.exists())
        self.assertTrue(WorkoutPlan.objects.exists())

        # Idempotent on the realistic path too
        before = Customer.objects.count()
        _run_seed_qa("--realistic")
        self.assertEqual(Customer.objects.count(), before)

    def test_password_alignment_and_no_reset_flag(self) -> None:
        """Pre-existing accounts get the documented password (or not, with flag)."""
        drifted = User.objects.create(
            tenant=Tenant.objects.create(name="Drift Gym", contact_email="d@x.test"),
            email="owner@fitnation.test",
            first_name="Rahul",
            last_name="Sharma",
            role="gym_owner",
        )
        drifted.set_password("OldPassword!1")
        drifted.save()

        _run_seed_qa("--skip-catalogs")
        drifted.refresh_from_db()
        self.assertTrue(check_password(PASSWORDS["tenant1_staff"], drifted.password))

        # --no-reset-passwords leaves mismatching passwords alone
        drifted.set_password("AnotherPass!1")
        drifted.save()
        _run_seed_qa("--skip-catalogs", "--no-reset-passwords")
        drifted.refresh_from_db()
        self.assertTrue(check_password("AnotherPass!1", drifted.password))

    def test_backfill_paid_at_helper(self) -> None:
        """_backfill_paid_at dates legacy NULL-paid_at payments (idempotent)."""
        import datetime as dt

        from apps.core.qa_seed.tenant_ab import _backfill_paid_at
        from apps.memberships.models import MembershipPlan
        from apps.payments.models import Payment

        tenant = Tenant.objects.create(name="Backfill Gym", contact_email="bf@x.test")
        plan = MembershipPlan.objects.create(tenant=tenant, name="Legacy Plan", price="2000.00", duration_days=30)
        user = User.objects.create(
            tenant=tenant,
            email="legacy@x.test",
            first_name="L",
            last_name="U",
            role=User.Role.CUSTOMER,
        )
        customer = Customer.objects.create(tenant=tenant, user=user, email=user.email)
        membership = Membership.objects.create(
            tenant=tenant,
            customer=customer,
            plan=plan,
            start_date=dt.date(2026, 6, 1),
            end_date=dt.date(2026, 6, 30),
            status=Membership.Status.ACTIVE,
        )
        payment = Payment.objects.create(
            tenant=tenant,
            customer=customer,
            membership=membership,
            amount="2000.00",
            status=Payment.Status.COMPLETED,  # paid_at NULL
        )
        self.assertIsNone(payment.paid_at)

        _backfill_paid_at(payment, fallback_date=dt.date(2026, 6, 1))
        payment.refresh_from_db()
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(dj_timezone.localdate(payment.paid_at), dt.date(2026, 6, 1))

        # Idempotent: a second run does not move the date.
        _backfill_paid_at(payment, fallback_date=dt.date(2026, 7, 1))
        payment.refresh_from_db()
        self.assertEqual(dj_timezone.localdate(payment.paid_at), dt.date(2026, 6, 1))
