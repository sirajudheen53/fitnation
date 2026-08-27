"""Tests for the users app."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.permissions.models import UserRoleAssignment
from apps.tenants.services import provision_tenant
from apps.users.models import Trainer, TrainerCustomerAssignment, TrainerSchedule
from apps.users.services import (
    create_owner_user,
    create_user,
    deactivate_token,
    get_or_create_customer_by_phone,
    get_user_permissions,
    issue_token,
)
from apps.users.trainer_services import (
    assign_customer_to_trainer,
    create_schedule,
    create_trainer,
    unassign_customer_from_trainer,
    update_schedule,
    update_trainer,
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
        self.assertTrue(UserRoleAssignment.objects.filter(user=user, branch=branch).exists())


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


# ── Trainer Model Extension Tests ────────────────────────────────────────────


class TrainerModelExtensionTests(TestCase):
    """Tests for extended Trainer model fields."""

    def setUp(self) -> None:
        """Create tenant and a trainer."""
        self.tenant = provision_tenant(name="Gym", contact_email="gym@local.test")
        self.trainer = create_trainer(
            tenant=self.tenant,
            email="trainer@local.test",
            first_name="John",
            last_name="Doe",
            specialization="Strength Training",
            bio="Certified strength coach.",
            certifications=[
                {"name": "NASM-CPT", "issuer": "NASM", "year": 2020, "expiry": "2025-01-01"},
            ],
            experience_years=5,
            max_clients=30,
            profile_photo="https://cdn.fitnation.com/photos/trainer1.jpg",
        )

    def test_trainer_has_extended_fields(self) -> None:
        """Trainer model stores all extended fields."""
        self.assertEqual(self.trainer.specialization, "Strength Training")
        self.assertEqual(self.trainer.experience_years, 5)
        self.assertEqual(self.trainer.max_clients, 30)
        self.assertEqual(self.trainer.profile_photo, "https://cdn.fitnation.com/photos/trainer1.jpg")
        self.assertEqual(len(self.trainer.certifications), 1)
        self.assertEqual(self.trainer.certifications[0]["name"], "NASM-CPT")

    def test_trainer_defaults(self) -> None:
        """Trainer model has correct default values."""
        trainer2 = create_trainer(
            tenant=self.tenant,
            email="trainer2@local.test",
            first_name="Jane",
            last_name="Smith",
        )
        self.assertEqual(trainer2.experience_years, 0)
        self.assertEqual(trainer2.rating, 0)
        self.assertEqual(trainer2.max_clients, 50)
        self.assertEqual(trainer2.certifications, [])
        self.assertEqual(trainer2.profile_photo, "")

    def test_update_trainer(self) -> None:
        """update_trainer updates fields correctly."""
        updated = update_trainer(self.trainer, bio="Updated bio", experience_years=7)
        self.assertEqual(updated.bio, "Updated bio")
        self.assertEqual(updated.experience_years, 7)


# ── TrainerSchedule Tests ─────────────────────────────────────────────────────


class TrainerScheduleTests(TestCase):
    """Tests for TrainerSchedule model."""

    def setUp(self) -> None:
        """Create tenant and trainer."""
        self.tenant = provision_tenant(name="Gym", contact_email="gym@local.test")
        self.trainer = create_trainer(
            tenant=self.tenant,
            email="trainer@local.test",
            first_name="John",
            last_name="Doe",
        )

    def test_create_schedule(self) -> None:
        """Schedule entries can be created for a trainer."""
        schedule = create_schedule(
            tenant=self.tenant,
            trainer=self.trainer,
            day_of_week="monday",
            start_time="06:00",
            end_time="12:00",
        )
        self.assertEqual(schedule.day_of_week, "monday")
        self.assertTrue(schedule.is_available)
        self.assertEqual(schedule.tenant, self.tenant)

    def test_schedule_requires_tenant(self) -> None:
        """TrainerSchedule enforces tenant_id via TenantModelMixin."""
        with self.assertRaises(ValueError):
            schedule = TrainerSchedule(
                trainer=self.trainer,
                day_of_week="tuesday",
                start_time="08:00",
                end_time="14:00",
            )
            schedule.save()

    def test_update_schedule(self) -> None:
        """update_schedule modifies fields correctly."""
        schedule = create_schedule(
            tenant=self.tenant,
            trainer=self.trainer,
            day_of_week="wednesday",
            start_time="06:00",
            end_time="12:00",
        )
        updated = update_schedule(schedule, is_available=False, end_time="10:00")
        self.assertFalse(updated.is_available)
        self.assertEqual(str(updated.end_time), "10:00")

    def test_unique_day_per_trainer(self) -> None:
        """Duplicate day entries for the same trainer are rejected."""
        create_schedule(
            tenant=self.tenant,
            trainer=self.trainer,
            day_of_week="friday",
            start_time="06:00",
            end_time="12:00",
        )
        with self.assertRaises(Exception):
            create_schedule(
                tenant=self.tenant,
                trainer=self.trainer,
                day_of_week="friday",
                start_time="14:00",
                end_time="18:00",
            )


# ── TrainerCustomerAssignment Tests ──────────────────────────────────────────


class TrainerCustomerAssignmentTests(TestCase):
    """Tests for TrainerCustomerAssignment model."""

    def setUp(self) -> None:
        """Create tenant, trainer, and customer."""
        self.tenant = provision_tenant(name="Gym", contact_email="gym@local.test")
        self.trainer = create_trainer(
            tenant=self.tenant,
            email="trainer@local.test",
            first_name="John",
            last_name="Doe",
        )
        self.customer_user = create_user(
            tenant=self.tenant,
            email="customer@local.test",
            first_name="Cust",
            last_name="One",
            role=User.Role.CUSTOMER,
        )
        self.customer = self.customer_user.customer_profile

    def test_assign_customer_to_trainer(self) -> None:
        """Customer can be assigned to a trainer."""
        assignment = assign_customer_to_trainer(
            tenant=self.tenant,
            trainer=self.trainer,
            customer_id=self.customer.id,
        )
        self.assertTrue(assignment.is_active)
        self.assertEqual(assignment.trainer, self.trainer)
        self.assertEqual(assignment.customer, self.customer)
        self.assertEqual(assignment.tenant, self.tenant)

    def test_assignment_requires_tenant(self) -> None:
        """TrainerCustomerAssignment enforces tenant_id."""
        assignment = TrainerCustomerAssignment(
            trainer=self.trainer,
            customer=self.customer,
        )
        with self.assertRaises(ValueError):
            assignment.save()

    def test_reactivate_assignment(self) -> None:
        """Reassigning reactivates an existing inactive assignment."""
        assignment = assign_customer_to_trainer(
            tenant=self.tenant,
            trainer=self.trainer,
            customer_id=self.customer.id,
        )
        assignment = unassign_customer_from_trainer(assignment)
        self.assertFalse(assignment.is_active)
        self.assertIsNotNone(assignment.unassigned_at)

        # Reassign should reactivate
        reactivated = assign_customer_to_trainer(
            tenant=self.tenant,
            trainer=self.trainer,
            customer_id=self.customer.id,
        )
        self.assertTrue(reactivated.is_active)
        self.assertIsNone(reactivated.unassigned_at)

    def test_unique_assignment(self) -> None:
        """Duplicate trainer-customer assignment is rejected."""
        assign_customer_to_trainer(
            tenant=self.tenant,
            trainer=self.trainer,
            customer_id=self.customer.id,
        )
        with self.assertRaises(Exception):
            TrainerCustomerAssignment.objects.create(
                tenant=self.tenant,
                trainer=self.trainer,
                customer=self.customer,
            )

    def test_unassign_customer(self) -> None:
        """unassign_customer_from_trainer marks assignment inactive."""
        assignment = assign_customer_to_trainer(
            tenant=self.tenant,
            trainer=self.trainer,
            customer_id=self.customer.id,
        )
        result = unassign_customer_from_trainer(assignment)
        self.assertFalse(result.is_active)
        self.assertIsNotNone(result.unassigned_at)


# ── Trainer API Tests ─────────────────────────────────────────────────────────


class TrainerAPITests(APITestCase):
    """Integration tests for trainer management API endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, token, and a trainer."""
        self.tenant = provision_tenant(name="Gym", contact_email="gym@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.trainer = create_trainer(
            tenant=self.tenant,
            email="trainer@local.test",
            first_name="John",
            last_name="Doe",
            specialization="Strength",
            experience_years=5,
        )

    def test_list_trainers(self) -> None:
        """Owners can list trainers."""
        response = self.client.get("/api/v1/users/trainers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["email"], "trainer@local.test")

    def test_list_trainers_filter_active(self) -> None:
        """List trainers with is_active filter."""
        response = self.client.get("/api/v1/users/trainers/?is_active=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_trainers_filter_specialization(self) -> None:
        """List trainers filtered by specialization."""
        response = self.client.get("/api/v1/users/trainers/?specialization=Strength")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_trainers_search(self) -> None:
        """List trainers with search term."""
        response = self.client.get("/api/v1/users/trainers/?search=John")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_trainer(self) -> None:
        """Owners can retrieve a single trainer."""
        response = self.client.get(f"/api/v1/users/trainers/{self.trainer.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "trainer@local.test")
        self.assertEqual(response.data["experience_years"], 5)

    def test_create_trainer(self) -> None:
        """Owners can create a new trainer via API."""
        response = self.client.post(
            "/api/v1/users/trainers/",
            {
                "email": "newtrainer@local.test",
                "first_name": "New",
                "last_name": "Trainer",
                "password": "F1tNati0n!",
                "specialization": "Yoga",
                "bio": "Yoga instructor",
                "experience_years": 3,
                "max_clients": 25,
                "certifications": [
                    {"name": "RYT-200", "issuer": "Yoga Alliance", "year": 2019, "expiry": None},
                ],
                "profile_photo": "https://cdn.fitnation.com/photos/new.jpg",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "newtrainer@local.test")
        self.assertEqual(response.data["specialization"], "Yoga")
        self.assertEqual(response.data["experience_years"], 3)
        self.assertEqual(response.data["max_clients"], 25)
        self.assertEqual(len(response.data["certifications"]), 1)

    def test_partial_update_trainer(self) -> None:
        """Owners can update trainer profiles."""
        response = self.client.patch(
            f"/api/v1/users/trainers/{self.trainer.id}/",
            {"bio": "Updated bio", "experience_years": 10},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bio"], "Updated bio")
        self.assertEqual(response.data["experience_years"], 10)

    def test_trainer_schedule_get(self) -> None:
        """GET trainer schedule returns schedule entries."""
        create_schedule(
            tenant=self.tenant,
            trainer=self.trainer,
            day_of_week="monday",
            start_time="06:00",
            end_time="12:00",
        )
        response = self.client.get(f"/api/v1/users/trainers/{self.trainer.id}/schedule/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["day_of_week"], "monday")

    def test_trainer_schedule_post(self) -> None:
        """POST trainer schedule creates a schedule entry."""
        response = self.client.post(
            f"/api/v1/users/trainers/{self.trainer.id}/schedule/",
            {
                "day_of_week": "tuesday",
                "start_time": "08:00",
                "end_time": "14:00",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["day_of_week"], "tuesday")
        self.assertTrue(response.data["is_available"])

    def test_trainer_schedule_patch(self) -> None:
        """PATCH updates a specific schedule entry."""
        schedule = create_schedule(
            tenant=self.tenant,
            trainer=self.trainer,
            day_of_week="wednesday",
            start_time="06:00",
            end_time="12:00",
        )
        response = self.client.patch(
            f"/api/v1/users/trainers/{self.trainer.id}/schedule/{schedule.id}/",
            {"is_available": False, "end_time": "10:00"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_available"])
        self.assertEqual(str(response.data["end_time"]), "10:00:00")

    def test_assign_customer_to_trainer(self) -> None:
        """POST assign-customer assigns a customer to a trainer."""
        customer_user = create_user(
            tenant=self.tenant,
            email="cust@local.test",
            first_name="Cust",
            last_name="One",
            role=User.Role.CUSTOMER,
        )
        customer = customer_user.customer_profile
        response = self.client.post(
            f"/api/v1/users/trainers/{self.trainer.id}/assign-customer/",
            {"customer_id": customer.id},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_active"])
        self.assertEqual(response.data["customer"], customer.id)

    def test_list_trainer_assignments(self) -> None:
        """GET assignments lists customer assignments for a trainer."""
        customer_user = create_user(
            tenant=self.tenant,
            email="cust@local.test",
            first_name="Cust",
            last_name="One",
            role=User.Role.CUSTOMER,
        )
        customer = customer_user.customer_profile
        assign_customer_to_trainer(
            tenant=self.tenant,
            trainer=self.trainer,
            customer_id=customer.id,
        )
        response = self.client.get(f"/api/v1/users/trainers/{self.trainer.id}/assignments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["customer_name"], "Cust One")

    def test_unassign_customer(self) -> None:
        """POST unassign-customer deactivates an assignment."""
        customer_user = create_user(
            tenant=self.tenant,
            email="cust@local.test",
            first_name="Cust",
            last_name="One",
            role=User.Role.CUSTOMER,
        )
        customer = customer_user.customer_profile
        assignment = assign_customer_to_trainer(
            tenant=self.tenant,
            trainer=self.trainer,
            customer_id=customer.id,
        )
        response = self.client.post(
            f"/api/v1/users/trainers/{self.trainer.id}/unassign-customer/{assignment.id}/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_active"])
        self.assertIsNotNone(response.data["unassigned_at"])

    def test_trainer_metrics(self) -> None:
        """GET metrics returns trainer performance data."""
        # Create 3 customers and assign 2 as active
        for i in range(3):
            cu = create_user(
                tenant=self.tenant,
                email=f"cust{i}@local.test",
                first_name=f"Cust{i}",
                last_name="Test",
                role=User.Role.CUSTOMER,
            )
            assignment = assign_customer_to_trainer(
                tenant=self.tenant,
                trainer=self.trainer,
                customer_id=cu.customer_profile.id,
            )
            if i == 2:
                unassign_customer_from_trainer(assignment)

        response = self.client.get(f"/api/v1/users/trainers/{self.trainer.id}/metrics/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["trainer_id"], self.trainer.id)
        self.assertEqual(response.data["active_clients"], 2)
        self.assertEqual(response.data["total_assignments"], 3)
        self.assertEqual(response.data["max_clients"], 50)
        # utilization = 2/50 * 100 = 4.0
        self.assertAlmostEqual(response.data["utilization"], 4.0)

    def test_trainer_metrics_no_clients(self) -> None:
        """Metrics for trainer with no clients returns zeros."""
        response = self.client.get(f"/api/v1/users/trainers/{self.trainer.id}/metrics/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["active_clients"], 0)
        self.assertEqual(response.data["total_assignments"], 0)
        self.assertEqual(response.data["utilization"], 0.0)

    def test_retrieve_trainer_not_found(self) -> None:
        """Retrieving a non-existent trainer returns 404."""
        response = self.client.get("/api/v1/users/trainers/99999/")
        self.assertEqual(response.status_code, 404)

    def test_schedule_not_found(self) -> None:
        """Patching a non-existent schedule returns 404."""
        response = self.client.patch(
            f"/api/v1/users/trainers/{self.trainer.id}/schedule/99999/",
            {"is_available": False},
        )
        self.assertEqual(response.status_code, 404)

    def test_unassign_not_found(self) -> None:
        """Unassigning a non-existent assignment returns 404."""
        response = self.client.post(
            f"/api/v1/users/trainers/{self.trainer.id}/unassign-customer/99999/",
        )
        self.assertEqual(response.status_code, 404)
