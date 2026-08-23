"""Tests for the users app."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.permissions.models import UserRoleAssignment
from apps.tenants.services import provision_tenant
from apps.users.models import Trainer
from apps.users.services import (
    create_owner_user,
    create_user,
    deactivate_token,
    get_or_create_customer_by_phone,
    get_user_permissions,
    issue_token,
)

User = get_user_model()


class UserModelTests(TestCase):
    """Unit tests for the custom User model."""

    def test_create_user_with_email(self) -> None:
        """Users are identified by email instead of username."""
        user = User.objects.create_user(
            email="trainer@gym.local",
            password="F1tNati0n!",
            first_name="Rahul",
            last_name="Sharma",
        )
        self.assertIsNone(getattr(user, "username", None))
        self.assertEqual(user.email, "trainer@gym.local")
        self.assertTrue(user.check_password("F1tNati0n!"))

    def test_email_unique_globally(self) -> None:
        """The same email cannot be reused anywhere in the platform."""
        User.objects.create_user(
            email="dup@local.test",
            password="F1tNati0n!",
            first_name="A",
            last_name="B",
        )

        with self.assertRaises(Exception):
            User.objects.create_user(
                email="dup@local.test",
                password="F1tNati0n!",
                first_name="C",
                last_name="D",
            )


class TrainerAndCustomerProfileTests(TestCase):
    """Tests for profile creation linked to users."""

    def setUp(self) -> None:
        """Create a tenant for profile tests."""
        self.tenant = provision_tenant(name="Gym", contact_email="gym@local.test")

    def test_create_user_makes_trainer_profile(self) -> None:
        """Creating a trainer user also creates a Trainer profile."""
        user = create_user(
            tenant=self.tenant,
            email="trainer@gym.local",
            first_name="Trainer",
            last_name="One",
            role=User.Role.TRAINER,
        )
        self.assertTrue(hasattr(user, "trainer_profile"))
        self.assertIsInstance(user.trainer_profile, Trainer)

    def test_create_user_makes_customer_profile(self) -> None:
        """Creating a customer user also creates a Customer profile."""
        user = create_user(
            tenant=self.tenant,
            email="customer@gym.local",
            first_name="Customer",
            last_name="One",
            role=User.Role.CUSTOMER,
        )
        self.assertTrue(hasattr(user, "customer_profile"))
        self.assertIsInstance(user.customer_profile, Customer)


class OwnerCreationTests(TestCase):
    """Tests for vendor owner user creation."""

    def test_create_owner_user(self) -> None:
        """Owner users are gym owners and flagged as owner."""
        tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        owner = create_owner_user(
            tenant=tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Arjun Kumar",
            phone="+919876543210",
        )
        self.assertEqual(owner.role, User.Role.GYM_OWNER)
        self.assertTrue(owner.is_owner)
        self.assertEqual(owner.first_name, "Arjun")
        self.assertEqual(owner.last_name, "Kumar")


class TokenTests(TestCase):
    """Tests for the custom AuthToken model and authentication backend."""

    def setUp(self) -> None:
        """Create tenant and owner for token tests."""
        self.tenant = provision_tenant(name="Gym", contact_email="gym@local.test")
        self.user = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner",
        )

    def test_issue_token_generates_key(self) -> None:
        """issue_token creates a random 64-character key."""
        token = issue_token(self.user, self.tenant)
        self.assertEqual(len(token.key), 64)
        self.assertTrue(token.is_active)

    def test_deactivate_token(self) -> None:
        """deactivate_token marks the token inactive."""
        token = issue_token(self.user, self.tenant)
        self.assertTrue(deactivate_token(token.key))
        token.refresh_from_db()
        self.assertFalse(token.is_active)

    def test_authenticate_valid_token(self) -> None:
        """TenantTokenAuthentication returns user and token."""
        token = issue_token(self.user, self.tenant)
        from apps.users.authentication import TenantTokenAuthentication

        real_backend = TenantTokenAuthentication()
        request = type(
            "Request",
            (),
            {"META": {"HTTP_AUTHORIZATION": f"Token {token.key}"}},
        )()
        user, auth_token = real_backend.authenticate(request)
        self.assertEqual(user.id, self.user.id)
        self.assertEqual(auth_token.id, token.id)
        self.assertEqual(user._tenant_from_token, self.tenant)

    def test_authenticate_invalid_token(self) -> None:
        """An invalid token raises AuthenticationFailed."""
        from apps.users.authentication import TenantTokenAuthentication

        real_backend = TenantTokenAuthentication()
        request = type(
            "Request",
            (),
            {"META": {"HTTP_AUTHORIZATION": "Token invalid"}},
        )()
        with self.assertRaises(Exception):
            real_backend.authenticate(request)

    def test_expired_token_rejected(self) -> None:
        """A token with a past expiry is rejected."""
        token = issue_token(self.user, self.tenant)
        token.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        token.save()
        from apps.users.authentication import TenantTokenAuthentication

        real_backend = TenantTokenAuthentication()
        request = type(
            "Request",
            (),
            {"META": {"HTTP_AUTHORIZATION": f"Token {token.key}"}},
        )()
        with self.assertRaises(Exception):
            real_backend.authenticate(request)


class PermissionListTests(TestCase):
    """Tests for role-based permission lookups."""

    def test_gym_owner_has_wildcard(self) -> None:
        """Gym owners receive a wildcard permission list."""
        tenant = provision_tenant(name="Gym", contact_email="gym@local.test")
        owner = create_owner_user(
            tenant=tenant,
            email="owner@local.test",
            password_hash="hashed",
            contact_name="Owner",
        )
        self.assertEqual(get_user_permissions(owner), ["*"])

    def test_customer_has_self_service_permissions(self) -> None:
        """Customers receive only self-service permissions."""
        user = User.objects.create_user(
            email="customer@local.test",
            password="F1tNati0n!",
            first_name="C",
            last_name="D",
            role=User.Role.CUSTOMER,
        )
        perms = get_user_permissions(user)
        self.assertIn("memberships.view_membership", perms)
        self.assertIn("payments.view_payment", perms)
        self.assertNotIn("branches.view_branch", perms)


class UserAPITests(APITestCase):
    """Integration tests for user management API endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, and auth token for API tests."""
        self.tenant = provision_tenant(name="Gym", contact_email="gym@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_list_users(self) -> None:
        """Owners can list users in their tenant."""
        create_user(
            tenant=self.tenant,
            email="manager@local.test",
            first_name="Manager",
            last_name="One",
            role=User.Role.MANAGER,
        )
        response = self.client.get("/api/v1/users/users/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_create_user(self) -> None:
        """Owners can create a manager user."""
        response = self.client.post(
            "/api/v1/users/users/",
            {
                "email": "manager@local.test",
                "first_name": "Manager",
                "last_name": "One",
                "role": "manager",
                "password": "F1tNati0n!",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["role"], "manager")

    def test_assign_branch(self) -> None:
        """Owners can assign a user to a branch."""
        user = create_user(
            tenant=self.tenant,
            email="manager@local.test",
            first_name="Manager",
            last_name="One",
            role=User.Role.MANAGER,
        )
        branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        response = self.client.post(
            f"/api/v1/users/users/{user.id}/assign-branch/",
            {"branch_id": branch.id, "role_at_branch": "manager"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            UserRoleAssignment.objects.filter(user=user, branch=branch).exists()
        )


class CustomerByPhoneTests(TestCase):
    """Tests for OTP-driven customer lookup."""

    def setUp(self) -> None:
        """Create a tenant for phone lookup tests."""
        self.tenant = provision_tenant(name="Gym", contact_email="gym@local.test")

    def test_get_or_create_customer_by_phone(self) -> None:
        """The helper creates a customer user derived from the phone number."""
        user = get_or_create_customer_by_phone("+919876543210", self.tenant)
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertTrue(user.email.startswith("+919876543210"))
        self.assertTrue(hasattr(user, "customer_profile"))
