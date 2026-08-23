"""Tests for the tenants app."""

from django.test import TestCase

from apps.tenants.models import Tenant, TenantSettings
from apps.tenants.services import PLAN_LIMITS, provision_tenant


class TenantModelTests(TestCase):
    """Unit tests for the Tenant and TenantSettings models."""

    def test_create_tenant_defaults(self) -> None:
        """A new tenant defaults to the starter plan and trial status."""
        tenant = Tenant.objects.create(
            name="Iron Peak Gym",
            contact_email="owner@ironpeak.local",
        )

        self.assertEqual(tenant.subscription_plan, Tenant.SubscriptionPlan.STARTER)
        self.assertEqual(tenant.status, Tenant.Status.TRIAL)
        self.assertEqual(tenant.timezone, "Asia/Kolkata")
        self.assertIsNotNone(tenant.uuid)

    def test_tenant_settings_created_by_provisioning(self) -> None:
        """provision_tenant creates a linked TenantSettings record."""
        tenant = provision_tenant(
            name="Peak Fitness",
            contact_email="peak@fitness.local",
            subscription_plan="professional",
        )

        self.assertTrue(hasattr(tenant, "config"))
        self.assertEqual(tenant.config.max_branches, 5)
        self.assertEqual(tenant.config.max_customers, 1000)
        self.assertEqual(tenant.config.max_trainers, 50)
        self.assertFalse(tenant.config.enable_whatsapp)

    def test_tenant_settings_query(self) -> None:
        """TenantSettings can be queried by tenant."""
        tenant_a = Tenant.objects.create(name="A", contact_email="a@local")
        tenant_b = Tenant.objects.create(name="B", contact_email="b@local")

        TenantSettings.objects.create(tenant=tenant_a)
        TenantSettings.objects.create(tenant=tenant_b)

        settings_for_a = TenantSettings.objects.filter(tenant=tenant_a)
        self.assertEqual(settings_for_a.count(), 1)
        self.assertEqual(settings_for_a.first().tenant, tenant_a)


class TenantProvisioningTests(TestCase):
    """Tests for tenant provisioning logic."""

    def test_plan_limits_applied(self) -> None:
        """Each plan code maps to the correct usage limits."""
        for plan_code, expected_limits in PLAN_LIMITS.items():
            tenant = provision_tenant(
                name=f"Gym {plan_code}",
                contact_email=f"{plan_code}@local",
                subscription_plan=plan_code,
            )
            self.assertEqual(
                tenant.config.max_branches, expected_limits["max_branches"]
            )
            self.assertEqual(
                tenant.config.max_customers, expected_limits["max_customers"]
            )
            self.assertEqual(
                tenant.config.max_trainers, expected_limits["max_trainers"]
            )

    def test_unknown_plan_falls_back_to_starter(self) -> None:
        """An unrecognized plan code falls back to starter limits."""
        tenant = provision_tenant(
            name="Unknown Plan Gym",
            contact_email="unknown@local",
            subscription_plan="lifetime",
        )
        self.assertEqual(tenant.config.max_branches, 1)
