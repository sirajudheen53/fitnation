"""Tests for the vendors app."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.tenants.models import Tenant
from apps.users.services import issue_token
from apps.vendors.models import SubscriptionPlan, VendorRegistration
from apps.vendors.services import (
    complete_onboarding,
    create_vendor_registration,
    select_plan_and_provision,
    verify_registration_email,
)

User = get_user_model()


class SubscriptionPlanTests(TestCase):
    """Tests for the subscription plan model."""

    def test_plan_code_unique(self) -> None:
        """Plan codes must be unique."""
        SubscriptionPlan.objects.create(
            code="starter",
            name="Starter",
            price_monthly=999,
            price_yearly=9990,
            max_branches=1,
            max_customers=100,
            max_trainers=5,
        )
        with self.assertRaises(Exception):
            SubscriptionPlan.objects.create(
                code="starter",
                name="Duplicate",
                price_monthly=1,
                price_yearly=1,
                max_branches=1,
                max_customers=1,
                max_trainers=1,
            )


class VendorRegistrationTests(TestCase):
    """Tests for the vendor registration state machine."""

    def test_registration_defaults_to_started(self) -> None:
        """A new registration starts in the STARTED step."""
        reg = create_vendor_registration(
            business_name="Iron Peak Gym",
            contact_name="Arjun Kumar",
            email="arjun@local.test",
            phone="+919876543210",
            password="F1tNati0n!",
        )
        self.assertEqual(reg.current_step, VendorRegistration.Step.STARTED)
        self.assertIsNotNone(reg.email_verification_token)

    def test_verify_email_advances_step(self) -> None:
        """Email verification advances the registration to EMAIL_VERIFIED."""
        reg = create_vendor_registration(
            business_name="Gym",
            contact_name="Owner",
            email="owner@local.test",
            phone="",
            password="F1tNati0n!",
        )
        verified = verify_registration_email(str(reg.email_verification_token))
        self.assertEqual(verified.current_step, VendorRegistration.Step.EMAIL_VERIFIED)


class VendorSignupFlowTests(APITestCase):
    """End-to-end tests for the vendor signup and provisioning flow."""

    def setUp(self) -> None:
        """Seed a subscription plan used during provisioning."""
        SubscriptionPlan.objects.create(
            code="professional",
            name="Professional",
            price_monthly=2999,
            price_yearly=29990,
            max_branches=5,
            max_customers=1000,
            max_trainers=50,
        )

    def test_signup_returns_registration_id(self) -> None:
        """Signup creates a registration and returns the next step."""
        response = self.client.post(
            "/api/v1/auth/signup/",
            {
                "business_name": "Iron Peak Gym",
                "contact_name": "Arjun Kumar",
                "email": "arjun@local.test",
                "phone": "+919876543210",
                "password": "F1tNati0n!",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("registration_id", response.data)
        self.assertEqual(response.data["next_step"], "verify_email")

    def test_select_plan_provisions_tenant_and_owner(self) -> None:
        """Selecting a plan creates a tenant, owner user, and auth token."""
        reg = create_vendor_registration(
            business_name="Iron Peak Gym",
            contact_name="Arjun Kumar",
            email="arjun@local.test",
            phone="+919876543210",
            password="F1tNati0n!",
        )
        verify_registration_email(str(reg.email_verification_token))

        response = self.client.post(
            "/api/v1/auth/select-plan/",
            {"registration_id": reg.id, "plan_code": "professional"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("auth_token", response.data)
        self.assertIn("tenant", response.data)
        self.assertEqual(response.data["next_step"], "onboarding_wizard")

        reg.refresh_from_db()
        self.assertEqual(reg.current_step, VendorRegistration.Step.PROVISIONED)

        tenant = Tenant.objects.get(id=reg.provisioned_tenant_id)
        self.assertEqual(tenant.subscription_plan, "professional")
        owner = User.objects.get(tenant=tenant, is_owner=True)
        self.assertEqual(owner.role, User.Role.GYM_OWNER)

    def test_onboarding_creates_default_branch(self) -> None:
        """The onboarding endpoint creates the first branch for the tenant."""
        reg = create_vendor_registration(
            business_name="Iron Peak Gym",
            contact_name="Arjun Kumar",
            email="arjun@local.test",
            phone="+919876543210",
            password="F1tNati0n!",
        )
        verify_registration_email(str(reg.email_verification_token))
        result = select_plan_and_provision(reg.id, "professional")
        owner = result["owner"]
        token = issue_token(owner, result["tenant"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.put(
            "/api/v1/auth/onboarding/",
            {
                "business_type": "gym",
                "branches_count": 1,
                "primary_branch_name": "Main Branch",
                "primary_branch_address": "MG Road, Kochi",
                "primary_branch_phone": "+914841234567",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Branch.objects.filter(tenant=result["tenant"], name="Main Branch").exists())
        reg.refresh_from_db()
        self.assertEqual(reg.current_step, VendorRegistration.Step.ONBOARDED)

    def test_subscription_plan_list(self) -> None:
        """The public plans endpoint returns seeded plans."""
        SubscriptionPlan.objects.create(
            code="starter",
            name="Starter",
            price_monthly=999,
            price_yearly=9990,
            max_branches=1,
            max_customers=100,
            max_trainers=5,
        )
        response = self.client.get("/api/v1/subscriptions/plans/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["plans"]), 2)


class OnboardingServiceTests(TestCase):
    """Tests for the onboarding completion service."""

    def test_complete_onboarding_requires_tenant(self) -> None:
        """complete_onboarding raises when the user has no tenant."""
        admin_user = User.objects.create_superuser(
            email="admin@local.test",
            password="F1tNati0n!",
            first_name="Admin",
            last_name="User",
        )
        with self.assertRaises(ValueError):
            complete_onboarding(
                user=admin_user,
                business_type="gym",
                branches_count=1,
                primary_branch_name="Main",
                primary_branch_address="MG Road",
            )
