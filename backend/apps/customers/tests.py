"""Tests for the customers app."""

import io
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APITestCase

from PIL import Image, features

from apps.attendance.models import AttendanceRecord
from apps.branches.models import Branch
from apps.customers.models import (
    BodyMeasurement,
    Customer,
    FitnessGoal,
    HealthProfile,
    ProgressPhoto,
)
from apps.customers.serializers import MAX_PROFILE_PHOTO_BYTES
from apps.diet.models import DietAssignment, DietPlan
from apps.memberships.models import Membership, MembershipPlan
from apps.notifications.models import NotificationLog
from apps.payments.models import Invoice, Payment
from apps.tenants.services import provision_tenant
from apps.trainers.models import TrainerAssignment, TrainerSession
from apps.users.models import Trainer
from apps.users.services import create_owner_user, delete_customer_account, issue_token
from apps.workouts.models import WorkoutAssignment, WorkoutPlan

User = get_user_model()


class CustomerModelTests(TestCase):
    """Unit tests for customer models."""

    def setUp(self) -> None:
        """Create a tenant for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")

    def _create_user(self, email: str, tenant=None) -> User:
        """Create a user without auto-creating a customer profile."""
        return User.objects.create_user(
            email=email,
            password="F1tNati0n!",
            first_name="Test",
            last_name="User",
            role=User.Role.CUSTOMER,
            tenant=tenant or self.tenant,
        )

    def test_customer_requires_tenant(self) -> None:
        """Saving a customer without a tenant raises ValueError."""
        orphan_user = User.objects.create_user(
            email="orphan@local.test",
            password="F1tNati0n!",
            first_name="Orphan",
            last_name="User",
            role=User.Role.CUSTOMER,
        )
        with self.assertRaises(ValueError):
            Customer.objects.create(
                user=orphan_user,
                name="Orphan Customer",
                email="orphan@local.test",
            )

    def test_customer_email_unique_within_tenant(self) -> None:
        """Customer emails are unique within a tenant but reusable across tenants."""
        user_a = self._create_user("a@local.test")
        Customer.objects.create(
            tenant=self.tenant,
            user=user_a,
            name="Customer A",
            email="a@local.test",
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        user_b = self._create_user("b@local.test", tenant=other_tenant)
        Customer.objects.create(
            tenant=other_tenant,
            user=user_b,
            name="Customer B",
            email="a@local.test",
        )
        user_dup = self._create_user("dup@local.test")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.create(
                tenant=self.tenant,
                user=user_dup,
                name="Duplicate Customer",
                email="a@local.test",
            )

    def test_null_emails_unique_within_tenant(self) -> None:
        """Multiple emailless customers per tenant are allowed (NULLs distinct)."""
        user_a = self._create_user("null-a@local.test")
        customer_a = Customer.objects.create(
            tenant=self.tenant,
            user=user_a,
            name="Customer A",
            email=None,
        )
        user_b = self._create_user("null-b@local.test")
        customer_b = Customer.objects.create(
            tenant=self.tenant,
            user=user_b,
            name="Customer B",
            email=None,
        )
        self.assertNotEqual(customer_a.id, customer_b.id)
        self.assertEqual(Customer.objects.for_tenant(self.tenant).filter(email__isnull=True).count(), 2)

    def test_health_profile_bmi_auto_calc(self) -> None:
        """BMI is auto-calculated when height and weight are set."""
        user = self._create_user("bmi@local.test")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Customer One",
            email="bmi@local.test",
        )
        profile = HealthProfile.objects.create(
            tenant=self.tenant,
            customer=customer,
            height_cm="170.00",
            weight_kg="70.00",
        )
        expected_bmi = round(70.0 / (1.70 * 1.70), 2)
        self.assertEqual(float(profile.bmi), expected_bmi)

    def test_health_profile_bmi_blank_when_height_missing(self) -> None:
        """BMI is left blank when height or weight is missing."""
        user = self._create_user("bmi2@local.test")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Customer Two",
            email="bmi2@local.test",
        )
        profile = HealthProfile(
            tenant=self.tenant,
            customer=customer,
            height_cm="0.00",
            weight_kg="70.00",
        )
        self.assertIsNone(profile.bmi)

    def test_customer_tenant_isolation(self) -> None:
        """Customers are scoped to their tenant."""
        user = self._create_user("iso@local.test")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Tenant Customer",
            email="iso@local.test",
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(
            Customer.objects.for_tenant(self.tenant).first().id,
            customer.id,
        )
        self.assertEqual(Customer.objects.for_tenant(other_tenant).count(), 0)


class CustomerAPITests(APITestCase):
    """Integration tests for customer management endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, branch, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _create_raw_customer_user(self, email: str) -> User:
        """Create a customer user without an auto-generated profile."""
        return User.objects.create_user(
            email=email,
            password="F1tNati0n!",
            first_name="Customer",
            last_name="User",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def test_list_customers(self) -> None:
        """Owners can list customers in their tenant."""
        user = self._create_raw_customer_user("c1@example.com")
        Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Customer One",
            email="c1@example.com",
        )
        response = self.client.get("/api/v1/customers/customers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_customer(self) -> None:
        """Owners can create a customer."""
        user = self._create_raw_customer_user("c2@example.com")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {
                "user": user.id,
                "branch": self.branch.id,
                "name": "Customer Two",
                "email": "c2@example.com",
                "phone": "+919876543210",
                "date_of_birth": "1990-01-01",
                "gender": "male",
                "emergency_contact_name": "Contact",
                "emergency_contact_phone": "+919876543211",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Customer Two")
        self.assertEqual(response.data["branch"], self.branch.id)

    def test_retrieve_update_customer(self) -> None:
        """Owners can retrieve and update a customer."""
        user = self._create_raw_customer_user("c3@example.com")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Customer Three",
            email="c3@example.com",
        )
        response = self.client.get(
            f"/api/v1/customers/customers/{customer.id}/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Customer Three")

        response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {"name": "Customer Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        customer.refresh_from_db()
        self.assertEqual(customer.name, "Customer Updated")

    def test_customer_health_profile_action(self) -> None:
        """Owners can update and retrieve a customer's health profile."""
        user = self._create_raw_customer_user("c4@example.com")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Customer Four",
            email="c4@example.com",
        )
        response = self.client.put(
            f"/api/v1/customers/customers/{customer.id}/health-profile/",
            {
                "customer": customer.id,
                "height_cm": "175.00",
                "weight_kg": "75.00",
                "injuries": "None",
                "medical_info": {},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        expected_bmi = round(75.0 / (1.75 * 1.75), 2)
        self.assertEqual(float(response.data["bmi"]), expected_bmi)

        response = self.client.get(
            f"/api/v1/customers/customers/{customer.id}/health-profile/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("height_cm", response.data)
        self.assertEqual(float(response.data["bmi"]), expected_bmi)

    def test_customer_measurements_action(self) -> None:
        """Owners can list and create body measurements for a customer."""
        user = self._create_raw_customer_user("c5@example.com")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Customer Five",
            email="c5@example.com",
        )
        response = self.client.post(
            f"/api/v1/customers/customers/{customer.id}/measurements/",
            {
                "customer": customer.id,
                "weight_kg": "72.00",
                "chest_cm": "100.00",
                "waist_cm": "85.00",
                "notes": "First log",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.get(
            f"/api/v1/customers/customers/{customer.id}/measurements/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(float(response.data[0]["weight_kg"]), 72.00)

    def test_customer_fitness_goals_action(self) -> None:
        """Owners can list and create fitness goals for a customer."""
        user = self._create_raw_customer_user("c6@example.com")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Customer Six",
            email="c6@example.com",
        )
        response = self.client.post(
            f"/api/v1/customers/customers/{customer.id}/fitness-goals/",
            {
                "customer": customer.id,
                "goal_type": "lose_weight",
                "target_value": "5",
                "target_unit": "kg",
                "notes": "In 3 months",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.get(
            f"/api/v1/customers/customers/{customer.id}/fitness-goals/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["goal_type"], "lose_weight")

    def test_tenant_isolation_for_customers_api(self) -> None:
        """A customer in another tenant is not accessible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        create_owner_user(
            tenant=other_tenant,
            email="other-owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        other_user = User.objects.create_user(
            email="other-customer@example.com",
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
            email="other-customer@example.com",
        )

        response = self.client.get(
            f"/api/v1/customers/customers/{other_customer.id}/",
        )
        self.assertEqual(response.status_code, 404)

    def test_create_customer_duplicate_email_same_tenant(self) -> None:
        """Duplicate customer emails in the same tenant are rejected."""
        user1 = self._create_raw_customer_user("dup-api@example.com")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {
                "user": user1.id,
                "name": "First",
                "email": "dup-api@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user2 = self._create_raw_customer_user("dup-api2@example.com")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {
                "user": user2.id,
                "name": "Second",
                "email": "dup-api@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class FitnessGoalModelTests(TestCase):
    """Model tests for fitness goals."""

    def setUp(self) -> None:
        """Create a tenant and customer."""
        self.tenant = provision_tenant(name="Goal Gym", contact_email="owner@local.test")
        self.user = User.objects.create_user(
            email="goal@local.test",
            password="F1tNati0n!",
            first_name="Goal",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Goal Customer",
            email="goal@local.test",
        )

    def test_create_fitness_goal(self) -> None:
        """A fitness goal can be created for a customer."""
        goal = FitnessGoal.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            goal_type=FitnessGoal.GoalType.BUILD_MUSCLE,
            target_value="3",
            target_unit="kg muscle",
            current_value="1.5",
        )
        self.assertEqual(goal.customer, self.customer)
        self.assertEqual(goal.goal_type, "build_muscle")
        self.assertEqual(goal.target_unit, "kg muscle")


class BodyMeasurementModelTests(TestCase):
    """Model tests for body measurements."""

    def setUp(self) -> None:
        """Create a tenant and customer."""
        self.tenant = provision_tenant(name="Measure Gym", contact_email="owner@local.test")
        self.user = User.objects.create_user(
            email="measure@local.test",
            password="F1tNati0n!",
            first_name="Measure",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Measure Customer",
            email="measure@local.test",
        )

    def test_measurement_ordering(self) -> None:
        """Measurements are ordered by most recent date first."""
        m1 = BodyMeasurement.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            weight_kg="70.00",
        )
        m2 = BodyMeasurement.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            weight_kg="69.00",
        )
        measurements = list(BodyMeasurement.objects.for_tenant(self.tenant))
        self.assertEqual(measurements[0].id, m2.id)
        self.assertEqual(measurements[1].id, m1.id)


class CustomerModelExtensionTests(TestCase):
    """Tests for new Customer model fields."""

    def setUp(self) -> None:
        """Create a tenant and customer."""
        self.tenant = provision_tenant(name="Ext Gym", contact_email="owner@local.test")
        self.user = User.objects.create_user(
            email="ext@local.test",
            password="F1tNati0n!",
            first_name="Ext",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Ext Customer",
            email="ext@local.test",
        )

    def test_customer_status_defaults_to_active(self) -> None:
        """Customer status defaults to active."""
        self.assertEqual(self.customer.status, Customer.Status.ACTIVE)

    def test_customer_status_choices(self) -> None:
        """Customer status can be set to inactive or suspended."""
        self.customer.status = Customer.Status.INACTIVE
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, "inactive")

        self.customer.status = Customer.Status.SUSPENDED
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, "suspended")

    def test_customer_address_fields(self) -> None:
        """Customer address fields can be set."""
        self.customer.address_street = "123 MG Road"
        self.customer.address_city = "Bengaluru"
        self.customer.address_state = "Karnataka"
        self.customer.address_postal_code = "560001"
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.address_street, "123 MG Road")
        self.assertEqual(self.customer.address_city, "Bengaluru")
        self.assertEqual(self.customer.address_state, "Karnataka")
        self.assertEqual(self.customer.address_postal_code, "560001")

    def test_customer_notes_field(self) -> None:
        """Customer notes field can be set and defaults to blank."""
        self.assertEqual(self.customer.notes, "")
        self.customer.notes = "Prefers morning sessions"
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.notes, "Prefers morning sessions")

    def test_customer_profile_photo_blank_by_default(self) -> None:
        """Customer profile_photo is blank/null by default."""
        self.assertFalse(self.customer.profile_photo)


class HealthProfileExtensionTests(TestCase):
    """Tests for new HealthProfile JSON fields."""

    def setUp(self) -> None:
        """Create a tenant, user, customer, and health profile."""
        self.tenant = provision_tenant(name="Health Gym", contact_email="owner@local.test")
        self.user = User.objects.create_user(
            email="health@local.test",
            password="F1tNati0n!",
            first_name="Health",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Health Customer",
            email="health@local.test",
        )
        self.profile = HealthProfile.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            height_cm="180.00",
            weight_kg="80.00",
        )

    def test_medical_conditions_default_empty_list(self) -> None:
        """medical_conditions defaults to an empty list."""
        self.assertEqual(self.profile.medical_conditions, [])

    def test_allergies_default_empty_list(self) -> None:
        """allergies defaults to an empty list."""
        self.assertEqual(self.profile.allergies, [])

    def test_medications_default_empty_list(self) -> None:
        """medications defaults to an empty list."""
        self.assertEqual(self.profile.medications, [])

    def test_medical_conditions_can_be_set(self) -> None:
        """medical_conditions can be set to a list of conditions."""
        self.profile.medical_conditions = ["diabetes", "hypertension"]
        self.profile.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.medical_conditions, ["diabetes", "hypertension"])

    def test_allergies_can_be_set(self) -> None:
        """allergies can be set to a list of allergies."""
        self.profile.allergies = ["peanuts", "latex"]
        self.profile.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.allergies, ["peanuts", "latex"])

    def test_medications_can_be_set(self) -> None:
        """medications can be set to a list of medications."""
        self.profile.medications = ["metformin 500mg", "lisinopril 10mg"]
        self.profile.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.medications, ["metformin 500mg", "lisinopril 10mg"])


class ProgressPhotoModelTests(TestCase):
    """Tests for the ProgressPhoto model."""

    def setUp(self) -> None:
        """Create a tenant and customer."""
        self.tenant = provision_tenant(name="Photo Gym", contact_email="owner@local.test")
        self.user = User.objects.create_user(
            email="photo@local.test",
            password="F1tNati0n!",
            first_name="Photo",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Photo Customer",
            email="photo@local.test",
        )

    def test_progress_photo_requires_tenant(self) -> None:
        """Saving a progress photo without a tenant raises ValueError."""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from PIL import Image

        img = Image.new("RGB", (1, 1), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        photo = ProgressPhoto(
            customer=self.customer,
            image=SimpleUploadedFile(
                name="test.jpg",
                content=img_bytes.read(),
                content_type="image/jpeg",
            ),
        )
        with self.assertRaises(ValueError):
            photo.save()

    def test_progress_photo_tenant_isolation(self) -> None:
        """Progress photos are scoped to their tenant."""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from PIL import Image

        img = Image.new("RGB", (1, 1), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        ProgressPhoto.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            image=SimpleUploadedFile(
                name="test.jpg",
                content=img_bytes.read(),
                content_type="image/jpeg",
            ),
            caption="Day 1",
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(ProgressPhoto.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(ProgressPhoto.objects.for_tenant(other_tenant).count(), 0)

    def test_progress_photo_ordering(self) -> None:
        """Progress photos are ordered by most recent taken_at first."""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from PIL import Image

        def make_image(name: str) -> SimpleUploadedFile:
            img = Image.new("RGB", (1, 1), color="red")
            img_bytes = BytesIO()
            img.save(img_bytes, format="JPEG")
            img_bytes.seek(0)
            return SimpleUploadedFile(
                name=name,
                content=img_bytes.read(),
                content_type="image/jpeg",
            )

        photo1 = ProgressPhoto.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            image=make_image("test1.jpg"),
            caption="First",
        )
        photo2 = ProgressPhoto.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            image=make_image("test2.jpg"),
            caption="Second",
        )
        photos = list(ProgressPhoto.objects.for_tenant(self.tenant))
        # Both have auto_now_add so photo2 is created later -> comes first
        self.assertEqual(photos[0].id, photo2.id)
        self.assertEqual(photos[1].id, photo1.id)

    def test_progress_photo_str(self) -> None:
        """ProgressPhoto __str__ includes customer name."""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from PIL import Image

        img = Image.new("RGB", (1, 1), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        photo = ProgressPhoto.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            image=SimpleUploadedFile(
                name="test.jpg",
                content=img_bytes.read(),
                content_type="image/jpeg",
            ),
            caption="Progress",
        )
        self.assertIn("Photo Customer", str(photo))


class CustomerFilterAPITests(APITestCase):
    """Tests for customer filtering, search, and pagination."""

    def setUp(self) -> None:
        """Create tenant, owner, branch, and multiple customers."""
        self.tenant = provision_tenant(name="Filter Gym", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.branch2 = Branch.objects.create(
            tenant=self.tenant,
            name="Branch Two",
            address_line1="Brigade Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        # Create multiple customers for filtering
        self.user1 = User.objects.create_user(
            email="alice@local.test",
            password="F1tNati0n!",
            first_name="Alice",
            last_name="Wonder",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer1 = Customer.objects.create(
            tenant=self.tenant,
            user=self.user1,
            name="Alice Wonder",
            email="alice@local.test",
            phone="1111111111",
            gender=Customer.Gender.FEMALE,
            status=Customer.Status.ACTIVE,
            branch=self.branch,
        )

        self.user2 = User.objects.create_user(
            email="bob@local.test",
            password="F1tNati0n!",
            first_name="Bob",
            last_name="Builder",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer2 = Customer.objects.create(
            tenant=self.tenant,
            user=self.user2,
            name="Bob Builder",
            email="bob@local.test",
            phone="2222222222",
            gender=Customer.Gender.MALE,
            status=Customer.Status.INACTIVE,
            branch=self.branch2,
        )

        self.user3 = User.objects.create_user(
            email="carol@local.test",
            password="F1tNati0n!",
            first_name="Carol",
            last_name="Singer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer3 = Customer.objects.create(
            tenant=self.tenant,
            user=self.user3,
            name="Carol Singer",
            email="carol@local.test",
            phone="3333333333",
            gender=Customer.Gender.OTHER,
            status=Customer.Status.SUSPENDED,
            branch=self.branch,
        )

    def test_filter_by_branch(self) -> None:
        """Customers can be filtered by branch."""
        response = self.client.get(f"/api/v1/customers/customers/?branch={self.branch.id}")
        self.assertEqual(response.status_code, 200)
        names = [r["name"] for r in response.data["results"]]
        self.assertIn("Alice Wonder", names)
        self.assertIn("Carol Singer", names)
        self.assertNotIn("Bob Builder", names)

    def test_filter_by_status(self) -> None:
        """Customers can be filtered by status."""
        response = self.client.get("/api/v1/customers/customers/?status=inactive")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Bob Builder")

    def test_filter_by_gender(self) -> None:
        """Customers can be filtered by gender."""
        response = self.client.get("/api/v1/customers/customers/?gender=female")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Alice Wonder")

    def test_search_by_name(self) -> None:
        """Customers can be searched by name."""
        response = self.client.get("/api/v1/customers/customers/?search=Bob")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Bob Builder")

    def test_search_by_phone(self) -> None:
        """Customers can be searched by phone."""
        response = self.client.get("/api/v1/customers/customers/?search=3333333333")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Carol Singer")

    def test_search_by_email(self) -> None:
        """Customers can be searched by email."""
        response = self.client.get("/api/v1/customers/customers/?search=alice@local.test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Alice Wonder")

    def test_pagination_page_size(self) -> None:
        """Customer list is paginated with page_size=20."""
        # Create 20+ customers to test pagination
        for i in range(20, 40):
            user = User.objects.create_user(
                email=f"extra{i}@local.test",
                password="F1tNati0n!",
                first_name=f"Extra{i}",
                last_name="User",
                role=User.Role.CUSTOMER,
                tenant=self.tenant,
            )
            Customer.objects.create(
                tenant=self.tenant,
                user=user,
                name=f"Extra Customer {i}",
                email=f"extra{i}@local.test",
            )
        response = self.client.get("/api/v1/customers/customers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIn("next", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(response.data["count"], 23)  # 3 original + 20 new


class CustomerPlanAssignmentFilterAPITests(APITestCase):
    """Issue #90: customers list filtered by active workout/diet assignments."""

    def setUp(self) -> None:
        """Create a tenant with customers holding varied assignment states."""
        self.tenant = provision_tenant(name="Plan Filter Gym", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.workout_plan = WorkoutPlan.objects.create(tenant=self.tenant, name="Strength Plan")
        self.diet_plan = DietPlan.objects.create(tenant=self.tenant, name="Bulk Plan")

        def _customer(email: str, name: str) -> Customer:
            """Create a customer with portal identity for the tenant."""
            user = User.objects.create_user(
                email=email,
                password="F1tNati0n!",
                first_name=name.split()[0],
                last_name=name.split()[-1],
                role=User.Role.CUSTOMER,
                tenant=self.tenant,
            )
            return Customer.objects.create(
                tenant=self.tenant,
                user=user,
                name=name,
                email=email,
            )

        self.both_plans = _customer("both@local.test", "Both Plans")
        self.workout_only = _customer("workout@local.test", "Workout Only")
        self.no_plans = _customer("none@local.test", "No Plans")

        # Active workout + diet assignments for `both_plans`.
        WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.both_plans,
            workout_plan=self.workout_plan,
        )
        DietAssignment.objects.create(
            tenant=self.tenant,
            customer=self.both_plans,
            diet_plan=self.diet_plan,
        )
        # Ended workout history for `workout_only` — must NOT count as active.
        WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=self.workout_only,
            workout_plan=self.workout_plan,
            is_active=False,
        )

        # Another tenant with its own assigned customer — must never leak in.
        self.other_tenant = provision_tenant("Other Gym", contact_email="owner2@local.test")
        other_plan = WorkoutPlan.objects.create(tenant=self.other_tenant, name="Other Plan")
        WorkoutAssignment.objects.create(
            tenant=self.other_tenant,
            customer=Customer.objects.create(tenant=self.other_tenant, name="Outsider"),
            workout_plan=other_plan,
        )

    def _customer_names(self, query: str) -> list[str]:
        """GET the customers list with the query and return result names."""
        response = self.client.get(f"/api/v1/customers/customers/{query}")
        self.assertEqual(response.status_code, 200)
        return [row["name"] for row in response.data["results"]]

    def test_filter_assigned_workout_any(self) -> None:
        """assigned_workout_plan=any returns only customers with an active workout plan."""
        names = self._customer_names("?assigned_workout_plan=any")
        self.assertEqual(names, ["Both Plans"])

    def test_filter_assigned_workout_none(self) -> None:
        """assigned_workout_plan=none excludes active assignments but keeps history."""
        names = self._customer_names("?assigned_workout_plan=none")
        self.assertIn("Workout Only", names)
        self.assertIn("No Plans", names)
        self.assertNotIn("Both Plans", names)

    def test_filter_by_specific_workout_plan(self) -> None:
        """assigned_workout_plan=<id> returns customers actively on that plan."""
        names = self._customer_names(f"?assigned_workout_plan={self.workout_plan.id}")
        self.assertEqual(names, ["Both Plans"])

    def test_filter_assigned_diet_any(self) -> None:
        """assigned_diet_plan=any returns only customers with an active diet plan."""
        names = self._customer_names("?assigned_diet_plan=any")
        self.assertEqual(names, ["Both Plans"])

    def test_filter_assigned_diet_none(self) -> None:
        """assigned_diet_plan=none returns everyone without an active diet plan."""
        names = self._customer_names("?assigned_diet_plan=none")
        self.assertIn("Workout Only", names)
        self.assertIn("No Plans", names)
        self.assertNotIn("Both Plans", names)

    def test_filter_combined_workout_and_diet(self) -> None:
        """Both filters combine with AND semantics."""
        names = self._customer_names("?assigned_workout_plan=any&assigned_diet_plan=any")
        self.assertEqual(names, ["Both Plans"])
        names = self._customer_names(
            f"?assigned_workout_plan={self.workout_plan.id}&assigned_diet_plan=none",
        )
        self.assertEqual(names, [])

    def test_filter_invalid_value_returns_400(self) -> None:
        """A non-id, non any/none value is a validation error."""
        response = self.client.get("/api/v1/customers/customers/?assigned_workout_plan=bogus")
        self.assertEqual(response.status_code, 400)

    def test_filter_never_returns_other_tenants(self) -> None:
        """No assignment filter combination leaks other tenants' customers."""
        for query in (
            "?assigned_workout_plan=any",
            "?assigned_workout_plan=none",
            f"?assigned_workout_plan={self.workout_plan.id}",
        ):
            with self.subTest(query=query):
                self.assertNotIn("Outsider", self._customer_names(query))


class CustomerExtendedFieldsAPITests(APITestCase):
    """Tests for new customer fields via the API."""

    def setUp(self) -> None:
        """Create tenant, owner, and auth token."""
        self.tenant = provision_tenant(name="Ext API Gym", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _create_raw_customer_user(self, email: str) -> User:
        """Create a customer user without an auto-generated profile."""
        return User.objects.create_user(
            email=email,
            password="F1tNati0n!",
            first_name="Customer",
            last_name="User",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def test_create_customer_with_extended_fields(self) -> None:
        """A customer can be created with address, status, and notes fields."""
        user = self._create_raw_customer_user("ext-create@local.test")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {
                "user": user.id,
                "branch": self.branch.id,
                "name": "Extended Customer",
                "email": "ext-create@local.test",
                "phone": "+919876543210",
                "date_of_birth": "1995-05-15",
                "gender": "other",
                "emergency_contact_name": "Guardian",
                "emergency_contact_phone": "+919876543211",
                "address_street": "456 Park Street",
                "address_city": "Mumbai",
                "address_state": "Maharashtra",
                "address_postal_code": "400001",
                "status": "active",
                "notes": "VIP customer",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["address_street"], "456 Park Street")
        self.assertEqual(response.data["address_city"], "Mumbai")
        self.assertEqual(response.data["address_state"], "Maharashtra")
        self.assertEqual(response.data["address_postal_code"], "400001")
        self.assertEqual(response.data["status"], "active")
        self.assertEqual(response.data["notes"], "VIP customer")

    def test_update_customer_status(self) -> None:
        """Customer status can be updated via PATCH."""
        user = self._create_raw_customer_user("status-update@local.test")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Status Customer",
            email="status-update@local.test",
        )
        response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {"status": "suspended"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        customer.refresh_from_db()
        self.assertEqual(customer.status, "suspended")

    def test_update_customer_address(self) -> None:
        """Customer address fields can be updated via PATCH."""
        user = self._create_raw_customer_user("addr-update@local.test")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Address Customer",
            email="addr-update@local.test",
        )
        response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {
                "address_street": "789 New Road",
                "address_city": "Delhi",
                "address_state": "Delhi",
                "address_postal_code": "110001",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        customer.refresh_from_db()
        self.assertEqual(customer.address_street, "789 New Road")
        self.assertEqual(customer.address_city, "Delhi")

    def test_update_customer_notes(self) -> None:
        """Customer notes can be updated via PATCH."""
        user = self._create_raw_customer_user("notes-update@local.test")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Notes Customer",
            email="notes-update@local.test",
        )
        response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {"notes": "Has knee injury, avoid squats"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        customer.refresh_from_db()
        self.assertEqual(customer.notes, "Has knee injury, avoid squats")

    def test_health_profile_with_extended_json_fields(self) -> None:
        """Health profile can be created with medical_conditions, allergies, medications."""
        user = self._create_raw_customer_user("hp-ext@local.test")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="HP Ext Customer",
            email="hp-ext@local.test",
        )
        response = self.client.put(
            f"/api/v1/customers/customers/{customer.id}/health-profile/",
            {
                "customer": customer.id,
                "height_cm": "170.00",
                "weight_kg": "65.00",
                "injuries": "Left knee meniscus tear",
                "medical_info": {"blood_group": "O+"},
                "medical_conditions": ["asthma", "hypertension"],
                "allergies": ["penicillin", "pollen"],
                "medications": ["inhaler", "amlodipine 5mg"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["medical_conditions"], ["asthma", "hypertension"])
        self.assertEqual(response.data["allergies"], ["penicillin", "pollen"])
        self.assertEqual(response.data["medications"], ["inhaler", "amlodipine 5mg"])


class ProgressPhotoAPITests(APITestCase):
    """Tests for progress photo endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, customer, and auth token."""
        self.tenant = provision_tenant(name="Photo API Gym", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.user = User.objects.create_user(
            email="photo-api@local.test",
            password="F1tNati0n!",
            first_name="Photo",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Photo API Customer",
            email="photo-api@local.test",
        )

    def test_list_progress_photos_empty(self) -> None:
        """Listing progress photos returns empty list when none exist."""
        response = self.client.get(f"/api/v1/customers/customers/{self.customer.id}/progress-photos/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_create_progress_photo(self) -> None:
        """A progress photo can be created for a customer."""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from PIL import Image

        # Create a minimal valid image
        img = Image.new("RGB", (1, 1), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        photo = SimpleUploadedFile(
            name="progress1.jpg",
            content=img_bytes.read(),
            content_type="image/jpeg",
        )
        response = self.client.post(
            f"/api/v1/customers/customers/{self.customer.id}/progress-photos/",
            {"image": photo, "caption": "Month 1 progress"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["caption"], "Month 1 progress")
        self.assertIn("image", response.data)

    def test_list_progress_photos_after_create(self) -> None:
        """Listing progress photos returns photos after creation."""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from PIL import Image

        # Create minimal valid images
        def make_image(name: str) -> SimpleUploadedFile:
            img = Image.new("RGB", (1, 1), color="blue")
            img_bytes = BytesIO()
            img.save(img_bytes, format="JPEG")
            img_bytes.seek(0)
            return SimpleUploadedFile(
                name=name,
                content=img_bytes.read(),
                content_type="image/jpeg",
            )

        self.client.post(
            f"/api/v1/customers/customers/{self.customer.id}/progress-photos/",
            {"image": make_image("p1.jpg"), "caption": "Photo 1"},
            format="multipart",
        )
        self.client.post(
            f"/api/v1/customers/customers/{self.customer.id}/progress-photos/",
            {"image": make_image("p2.jpg"), "caption": "Photo 2"},
            format="multipart",
        )
        response = self.client.get(f"/api/v1/customers/customers/{self.customer.id}/progress-photos/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_progress_photos_tenant_isolation(self) -> None:
        """Progress photos for another tenant's customer are not accessible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        create_owner_user(
            tenant=other_tenant,
            email="other-owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        other_user = User.objects.create_user(
            email="other-photo@local.test",
            password="F1tNati0n!",
            first_name="Other",
            last_name="Photo",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        other_customer = Customer.objects.create(
            tenant=other_tenant,
            user=other_user,
            name="Other Photo Customer",
            email="other-photo@local.test",
        )
        response = self.client.get(f"/api/v1/customers/customers/{other_customer.id}/progress-photos/")
        self.assertEqual(response.status_code, 404)


class FitnessGoalEnhancementTests(TestCase):
    """Tests for enhanced FitnessGoal fields."""

    def setUp(self) -> None:
        """Create a tenant, user, and customer."""
        self.tenant = provision_tenant(name="Goal Gym", contact_email="owner@local.test")
        self.user = User.objects.create_user(
            email="goal2@local.test",
            password="***",
            first_name="Goal",
            last_name="Two",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Goal Two",
            email="goal2@local.test",
        )

    def test_progress_percentage_computed(self) -> None:
        """Progress percentage is computed from current vs target value."""
        goal = FitnessGoal.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            goal_type=FitnessGoal.GoalType.LOSE_WEIGHT,
            target_value="10",
            current_value="5",
        )
        self.assertEqual(goal.progress_percentage, 50.0)

    def test_progress_percentage_clamped(self) -> None:
        """Progress percentage is clamped to 100."""
        goal = FitnessGoal.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            goal_type=FitnessGoal.GoalType.LOSE_WEIGHT,
            target_value="10",
            current_value="15",
        )
        self.assertEqual(goal.progress_percentage, 100.0)

    def test_progress_percentage_none_without_target(self) -> None:
        """Progress percentage is None when there is no target value."""
        goal = FitnessGoal.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            goal_type=FitnessGoal.GoalType.LOSE_WEIGHT,
        )
        self.assertIsNone(goal.progress_percentage)

    def test_status_and_sport_specific_goal_type(self) -> None:
        """Goals support achieved/abandoned status and sport_specific type."""
        goal = FitnessGoal.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            goal_type=FitnessGoal.GoalType.SPORT_SPECIFIC,
            status=FitnessGoal.Status.ACHIEVED,
        )
        self.assertEqual(goal.goal_type, "sport_specific")
        self.assertEqual(goal.status, "achieved")


class BodyMeasurementEnhancementTests(TestCase):
    """Tests for enhanced BodyMeasurement BMI auto-calc."""

    def setUp(self) -> None:
        """Create a tenant, user, and customer."""
        self.tenant = provision_tenant(name="Measure Gym", contact_email="owner@local.test")
        self.user = User.objects.create_user(
            email="measure@local.test",
            password="***",
            first_name="Measure",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Measure Customer",
            email="measure@local.test",
        )

    def test_bmi_auto_calc_from_measurement_height(self) -> None:
        """BMI is computed from the measurement's own height and weight."""
        measurement = BodyMeasurement.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            weight_kg="70",
            height_cm="175",
        )
        # 70 / (1.75^2) = 22.86
        self.assertEqual(float(measurement.bmi), 22.86)

    def test_bmi_fallback_to_health_profile_height(self) -> None:
        """BMI falls back to the health profile height when not on the measurement."""
        HealthProfile.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            height_cm="180",
            weight_kg="80",
        )
        measurement = BodyMeasurement.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            weight_kg="80",
        )
        # 80 / (1.8^2) = 24.69
        self.assertEqual(float(measurement.bmi), 24.69)

    def test_bmi_none_without_height(self) -> None:
        """BMI is None when no height is available."""
        measurement = BodyMeasurement.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            weight_kg="70",
        )
        self.assertIsNone(measurement.bmi)

    def test_measurement_extra_fields(self) -> None:
        """Measurements store biceps, thighs, neck, and body fat percentage."""
        measurement = BodyMeasurement.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            weight_kg="70",
            height_cm="175",
            biceps_cm="35",
            thighs_cm="55",
            neck_cm="38",
            body_fat_percentage="18",
        )
        self.assertEqual(float(measurement.biceps_cm), 35.0)
        self.assertEqual(float(measurement.thighs_cm), 55.0)
        self.assertEqual(float(measurement.neck_cm), 38.0)
        self.assertEqual(float(measurement.body_fat_percentage), 18.0)


class HealthProfileEnhancementTests(TestCase):
    """Tests for enhanced HealthProfile fields."""

    def setUp(self) -> None:
        """Create a tenant, user, and customer."""
        self.tenant = provision_tenant(name="Health Gym", contact_email="owner@local.test")
        self.user = User.objects.create_user(
            email="health@local.test",
            password="***",
            first_name="Health",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Health Customer",
            email="health@local.test",
        )

    def test_blood_group_and_enhanced_fields(self) -> None:
        """Health profile supports blood group, dietary, and injury fields."""
        profile = HealthProfile.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            height_cm="170",
            weight_kg="65",
            blood_group=HealthProfile.BloodGroup.O_POS,
            dietary_restrictions=["vegetarian"],
            food_allergies=["peanuts"],
            current_injuries=["knee sprain"],
            past_injuries=["ankle fracture"],
        )
        self.assertEqual(profile.blood_group, "O+")
        self.assertEqual(profile.dietary_restrictions, ["vegetarian"])
        self.assertEqual(profile.food_allergies, ["peanuts"])
        self.assertEqual(profile.current_injuries, ["knee sprain"])
        self.assertEqual(profile.past_injuries, ["ankle fracture"])

    def test_blood_group_default_unknown(self) -> None:
        """Blood group defaults to unknown."""
        profile = HealthProfile.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            height_cm="170",
            weight_kg="65",
        )
        self.assertEqual(profile.blood_group, "unknown")


class ProgressSummaryAPITests(APITestCase):
    """Tests for the progress-summary endpoint."""

    def setUp(self) -> None:
        """Create a tenant, owner, and customer with data."""
        self.tenant = provision_tenant(name="Progress Gym", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.user = User.objects.create_user(
            email="progress@local.test",
            password="***",
            first_name="Progress",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Progress Customer",
            email="progress@local.test",
        )

    def test_progress_summary_empty(self) -> None:
        """An empty progress summary returns nulls and empty lists."""
        response = self.client.get(f"/api/v1/customers/customers/{self.customer.id}/progress-summary/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["health_profile"])
        self.assertIsNone(response.data["latest_measurement"])
        self.assertEqual(response.data["weight_trend"], [])
        self.assertEqual(response.data["fitness_goals"], [])
        self.assertEqual(response.data["progress_photo_count"], 0)

    def test_progress_summary_with_data(self) -> None:
        """The progress summary aggregates profile, measurements, and goals."""
        HealthProfile.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            height_cm="175",
            weight_kg="70",
        )
        BodyMeasurement.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            weight_kg="70",
            height_cm="175",
        )
        FitnessGoal.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            goal_type=FitnessGoal.GoalType.LOSE_WEIGHT,
            target_value="10",
            current_value="5",
        )
        response = self.client.get(f"/api/v1/customers/customers/{self.customer.id}/progress-summary/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["health_profile"])
        self.assertIsNotNone(response.data["latest_measurement"])
        self.assertEqual(len(response.data["weight_trend"]), 1)
        self.assertEqual(len(response.data["fitness_goals"]), 1)
        self.assertEqual(response.data["fitness_goals"][0]["progress_percentage"], 50.0)

    def test_progress_summary_tenant_isolation(self) -> None:
        """Another tenant's customer is not accessible via progress-summary."""
        other = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_user = User.objects.create_user(
            email="other-progress@local.test",
            password="***",
            first_name="Other",
            last_name="Progress",
            role=User.Role.CUSTOMER,
            tenant=other,
        )
        other_customer = Customer.objects.create(
            tenant=other,
            user=other_user,
            name="Other Progress",
            email="other-progress@local.test",
        )
        response = self.client.get(f"/api/v1/customers/customers/{other_customer.id}/progress-summary/")
        self.assertEqual(response.status_code, 404)

    def test_fitness_goal_serializer_exposes_progress(self) -> None:
        """The fitness goals endpoint exposes progress_percentage."""
        FitnessGoal.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            goal_type=FitnessGoal.GoalType.BUILD_MUSCLE,
            target_value="5",
            current_value="2.5",
            target_unit="kg",
        )
        response = self.client.get(f"/api/v1/customers/customers/{self.customer.id}/fitness-goals/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["progress_percentage"], 50.0)
        self.assertEqual(response.data[0]["target_unit"], "kg")


class CustomerPhotoUploadAPITests(APITestCase):
    """FBOS-026 part 1 — customer profile photo upload validation.

    Covers: upload on create, replace on update, invalid/oversized rejection,
    optional-field behavior, WebP support and tenant isolation.
    """

    def setUp(self) -> None:
        """Isolated MEDIA_ROOT, tenant, owner, branch, and auth token."""
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=self.media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)

        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _create_raw_customer_user(self, email: str) -> User:
        """Create a customer user without an auto-generated profile."""
        return User.objects.create_user(
            email=email,
            password="F1tNati0n!",
            first_name="Photo",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    @staticmethod
    def _photo(name: str = "photo.jpg", fmt: str = "JPEG", size: tuple[int, int] = (8, 8)) -> SimpleUploadedFile:
        """Build an in-memory image upload for the given format."""
        content_types = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
            "GIF": "image/gif",
        }
        extensions = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}
        buffer = io.BytesIO()
        Image.new("RGB", size, color=(180, 60, 30)).save(buffer, format=fmt)
        buffer.seek(0)
        return SimpleUploadedFile(
            f"photo.{extensions[fmt]}",
            buffer.getvalue(),
            content_type=content_types[fmt],
        )

    def _payload(self, email: str, user: User) -> dict:
        """Minimal valid customer payload."""
        return {
            "user": user.id,
            "branch": self.branch.id,
            "name": "Photo Customer",
            "email": email,
            "phone": "+919876543210",
            "date_of_birth": "1995-01-01",
            "gender": "male",
            "emergency_contact_name": "Contact",
            "emergency_contact_phone": "+919876543211",
            "is_active": True,
        }

    def test_upload_photo_on_create(self) -> None:
        """Multipart create persists the photo and returns a usable media URL."""
        user = self._create_raw_customer_user("photo@example.com")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {**self._payload("photo@example.com", user), "profile_photo": self._photo("photo.jpg")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

        customer = Customer.objects.get(email="photo@example.com")
        self.assertTrue(customer.profile_photo)
        self.assertTrue(customer.profile_photo.name.startswith("customer-photos/"))
        self.assertTrue(default_storage.exists(customer.profile_photo.name))

        url = response.data["profile_photo"]
        self.assertIn("media/customer-photos/", url)
        with default_storage.open(customer.profile_photo.name) as stored:
            self.assertEqual(Image.open(stored).format, "JPEG")

    def test_replace_photo_on_update(self) -> None:
        """PATCH with a new image replaces the stored photo reference."""
        user = self._create_raw_customer_user("replace@example.com")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Replace Customer",
            email="replace@example.com",
        )
        response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {"profile_photo": self._photo("updated.png", fmt="PNG")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        customer.refresh_from_db()
        self.assertTrue(customer.profile_photo.name.endswith(".png"))
        self.assertTrue(default_storage.exists(customer.profile_photo.name))
        self.assertIn("media/customer-photos/", response.data["profile_photo"])

    def test_invalid_format_rejected(self) -> None:
        """GIF uploads are rejected with a format error."""
        user = self._create_raw_customer_user("gif@example.com")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {**self._payload("gif@example.com", user), "profile_photo": self._photo("bad.gif", fmt="GIF")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("JPEG, PNG or WebP", str(response.data))

    def test_non_image_rejected(self) -> None:
        """Corrupt/plain-text payloads are rejected as invalid images.

        DRF's ImageField decodes the upload first, so its own message fires
        before the serializer's format allow-list.
        """
        user = self._create_raw_customer_user("text@example.com")
        bogus = SimpleUploadedFile("photo.jpg", b"definitely not an image", content_type="image/jpeg")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {**self._payload("text@example.com", user), "profile_photo": bogus},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("profile_photo", response.data)
        self.assertIn("not an image", str(response.data))

    def test_oversized_photo_rejected(self) -> None:
        """A valid image larger than 5 MB is rejected by the size check."""
        import os

        user = self._create_raw_customer_user("big@example.com")
        # Valid PNG of pure noise — ~1500x1500x3 bytes, far above the limit.
        buffer = io.BytesIO()
        Image.frombytes("RGB", (1500, 1500), os.urandom(1500 * 1500 * 3)).save(buffer, format="PNG")
        self.assertGreater(buffer.getbuffer().nbytes, MAX_PROFILE_PHOTO_BYTES)
        oversized = SimpleUploadedFile("big.png", buffer.getvalue(), content_type="image/png")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {**self._payload("big@example.com", user), "profile_photo": oversized},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("5 MB", str(response.data))
        self.assertEqual(Customer.objects.filter(email="big@example.com").count(), 0)

    def test_create_without_photo_still_works(self) -> None:
        """The photo field remains optional."""
        user = self._create_raw_customer_user("nophoto@example.com")
        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("nophoto@example.com", user),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["profile_photo"])

    def test_webp_photo_accepted(self) -> None:
        """WebP uploads are accepted when Pillow supports WebP."""
        if not features.check("webp"):
            self.skipTest("Pillow built without WebP support")
        user = self._create_raw_customer_user("webp@example.com")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {**self._payload("webp@example.com", user), "profile_photo": self._photo("valid.webp", fmt="WEBP")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("customer-photos/", response.data["profile_photo"])

    def test_tenant_isolation_unchanged(self) -> None:
        """Another tenant's owner cannot touch this customer's photo."""
        user = self._create_raw_customer_user("isolated@example.com")
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Isolated Customer",
            email="isolated@example.com",
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_owner = create_owner_user(
            tenant=other_tenant,
            email="other-owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        other_token = issue_token(other_owner, other_tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")

        response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {"profile_photo": self._photo("intruder.png", fmt="PNG")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)
        customer.refresh_from_db()
        self.assertFalse(customer.profile_photo)
        self.assertEqual(Customer.objects.for_tenant(other_tenant).count(), 0)


class BodyMeasurementFilterAPITests(APITestCase):
    """FBOS-025 companion — ?customer= filter + customer-role self-filter.

    Staff/owners may narrow the list with ?customer={id}; customer-role
    tokens always resolve to their own rows regardless of the param.
    """

    def setUp(self) -> None:
        """Tenant, owner, two customers with measurements, and tokens."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.owner_token = issue_token(self.owner, self.tenant)

        self.customer_a_user = self._create_customer_user("cust-a@local.test")
        self.customer_a = Customer.objects.create(
            tenant=self.tenant,
            user=self.customer_a_user,
            name="Customer A",
            email="cust-a@local.test",
        )
        self.customer_b_user = self._create_customer_user("cust-b@local.test")
        self.customer_b = Customer.objects.create(
            tenant=self.tenant,
            user=self.customer_b_user,
            name="Customer B",
            email="cust-b@local.test",
        )
        for weight in (70, 75):
            BodyMeasurement.objects.create(
                tenant=self.tenant,
                customer=self.customer_a,
                weight_kg=weight,
                height_cm="175",
            )
        BodyMeasurement.objects.create(
            tenant=self.tenant,
            customer=self.customer_b,
            weight_kg=60,
            height_cm="160",
        )

    def _create_customer_user(self, email: str) -> User:
        """Create a raw customer user without an auto profile."""
        return User.objects.create_user(
            email=email,
            password="F1tNati0n!",
            first_name="Cust",
            last_name="User",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    @staticmethod
    def _rows(response):
        """Normalize paginated/bare list responses to the row list."""
        data = response.data
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def test_owner_filter_by_customer_param(self) -> None:
        """?customer={id} narrows staff/owner results to that customer."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(f"/api/v1/customers/body-measurements/?customer={self.customer_a.id}")
        self.assertEqual(response.status_code, 200)
        rows = self._rows(response)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["customer"], self.customer_a.id)

    def test_owner_without_param_returns_tenant_wide(self) -> None:
        """Without the param, staff/owner results stay tenant-wide."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get("/api/v1/customers/body-measurements/")
        self.assertEqual(response.status_code, 200)
        rows = self._rows(response)
        self.assertEqual(len(rows), 3)

    def test_customer_role_ignores_customer_param(self) -> None:
        """Customer tokens always resolve to their own rows (?customer= ignored)."""
        customer_token = issue_token(self.customer_a_user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {customer_token.key}")
        response = self.client.get(f"/api/v1/customers/body-measurements/?customer={self.customer_b.id}")
        self.assertEqual(response.status_code, 200)
        rows = self._rows(response)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["customer"], self.customer_a.id)

    def test_invalid_customer_param_rejected(self) -> None:
        """A non-integer ?customer= value is rejected with a field error."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get("/api/v1/customers/body-measurements/?customer=abc")
        self.assertEqual(response.status_code, 400)


class CustomerCreationContractTests(APITestCase):
    """Arch-blessed customer creation contract (FBOS-026 companion).

    The create payload carries first_name/last_name/email (+branch); the
    linked customer-role portal User is auto-provisioned from the email with
    an unusable password (OTP login path) and starts verified.
    """

    def setUp(self) -> None:
        """Tenant, owner, branch, and owner auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.owner_token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

    def _payload(self, email: str, **overrides) -> dict:
        """Minimal frontend-shaped create payload (no user, no name)."""
        payload = {
            "email": email,
            "first_name": "Asha",
            "last_name": "Nair",
            "phone": "+919999000001",
            "branch": self.branch.id,
        }
        payload.update(overrides)
        return {k: v for k, v in payload.items() if v is not None}

    def test_create_composes_name_and_provisions_user(self) -> None:
        """first/last compose the name; the portal user is auto-provisioned."""
        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("asha@local.test"),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Asha Nair")

        customer = Customer.objects.get(email="asha@local.test")
        user = customer.user
        self.assertIsNotNone(user)
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(user.tenant, self.tenant)
        self.assertFalse(user.has_usable_password())  # OTP login path
        self.assertTrue(user.is_email_verified)
        self.assertEqual(customer.name, "Asha Nair")

        # Response shape unchanged — write-only parts never leak.
        self.assertNotIn("first_name", response.data)
        self.assertNotIn("last_name", response.data)

    def test_composition_precedence_over_name(self) -> None:
        """first/last win over a provided name when either is present."""
        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("prec@local.test", name="Ignored Name"),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Asha Nair")

    def test_branch_persisted_when_sent(self) -> None:
        """A customer created with `branch` persists the branch link."""
        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("branchy@local.test"),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        customer = Customer.objects.get(email="branchy@local.test")
        self.assertEqual(customer.branch, self.branch)

    def test_email_conflict_returns_400_field_error(self) -> None:
        """A user-email collision (cross-tenant) surfaces as a 400 field error."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        User.objects.create_user(
            email="taken@local.test",
            password="F1tNati0n!",
            first_name="Taken",
            last_name="Elsewhere",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("taken@local.test"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)
        self.assertEqual(Customer.objects.filter(email="taken@local.test").count(), 0)

    @override_settings(DEBUG=True, OTP_SENDER="stub")  # stub requires DEBUG (FBOS-011 §4.3)
    def test_otp_login_for_auto_created_user(self) -> None:
        """The auto-provisioned CUSTOMER-role user authenticates via OTP."""
        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("otp@local.test", phone="+919999000001"),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        Customer.objects.get(email="otp@local.test")

        request_response = self.client.post(
            "/api/v1/users/auth/otp/request/",
            {"phone": "+919999000001", "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)

        otp_code = request_response.data["otp"]  # stub sender echoes the code
        verify_response = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "+919999000001", "otp": otp_code},
            format="json",
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertIsNotNone(verify_response.data.get("token"))
        # The OTP flow is phone-keyed (get_or_create_customer_by_phone) and
        # provisions CUSTOMER-role users with synthetic emails — the
        # email-provisioned account vs phone-OTP identity merge is a known
        # product question (ticketed for Arch), so we assert the OTP flow
        # issues a working token for a customer-role user.
        self.assertEqual(
            verify_response.data.get("user", {}).get("role"),
            "customer",
        )

    def test_update_composes_name(self) -> None:
        """PATCH with name parts recomposes the name (parts win)."""
        user = User.objects.create_user(
            email="upd@local.test",
            password="F1tNati0n!",
            first_name="Upd",
            last_name="User",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=user,
            name="Old Name",
            email="upd@local.test",
        )
        response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {"first_name": "Meera", "last_name": "Kapoor"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        customer.refresh_from_db()
        self.assertEqual(customer.name, "Meera Kapoor")


class MediaStorageConfigTests(TestCase):
    """P0 media-storage fix — storage backends per environment.

    QA/prod (cloudrun.py) must pin media to the GCS bucket (signed URLs);
    test settings must pin FileSystemStorage so tests never touch GCS.
    """

    def test_test_settings_pin_filesystem_storage(self) -> None:
        """Test settings never touch GCS (uploads stay on local disk)."""
        from django.conf import settings

        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )

    def test_cloudrun_pins_gcs_media_storage(self) -> None:
        """cloudrun settings route media to the PO-provisioned GCS bucket."""
        import os

        os.environ.setdefault("DATABASE_URL", "postgres://u:p@localhost:5432/configcheck")
        from config.settings import cloudrun

        self.assertEqual(
            cloudrun.STORAGES["default"]["BACKEND"],
            "storages.backends.gcloud.GoogleCloudStorage",
        )
        # static serving stays on whitenoise (Cloud Run has no nginx)
        self.assertEqual(
            cloudrun.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
        self.assertEqual(cloudrun.GS_BUCKET_NAME, "yougetfitwithus-media")
        self.assertEqual(cloudrun.GS_PROJECT_ID, "yougetfitwithus")
        self.assertTrue(cloudrun.GS_QUERYSTRING_AUTH)  # private objects
        # Cloud Run compute creds are token-only → sign via IAM signBlob.
        self.assertTrue(cloudrun.GS_IAM_SIGN_BLOB)
        self.assertEqual(
            cloudrun.GS_SA_EMAIL,
            "35318880783-compute@developer.gserviceaccount.com",
        )
        self.assertEqual(cloudrun.GS_EXPIRATION, 3600)  # ~1h signed-URL TTL
        self.assertFalse(hasattr(cloudrun, "GS_EXPIRE"))  # dead setting removed


class StubSignedStorage(FileSystemStorage):
    """Mimics the GCS backend's signed-URL shape without GCS credentials."""

    def url(self, name, parameters=None, **kwargs):
        return "https://storage.googleapis.com/yougetfitwithus-media/" + name + "?Expires=1900000000&Signature=stub"


class GCSUrlContractTests(APITestCase):
    """Regression: the response carries the storage URL, never None.

    DRF's ImageField.to_representation swallows AttributeError from
    storage.url via getattr — the fix makes .url WORK (IAM signBlob), and
    this pins the pass-through with a stub signed-URL storage.
    """

    def setUp(self) -> None:
        """Isolated MEDIA_ROOT + stub GCS-style storage + owner token."""
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=self.media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)
        storage_override = override_settings(
            STORAGES={
                "default": {"BACKEND": "apps.customers.tests.StubSignedStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            }
        )
        storage_override.enable()
        self.addCleanup(storage_override.disable)

        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.owner_token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

    def test_serializer_returns_signed_style_url_not_none(self) -> None:
        """Uploads return the storage URL, never None (no silent swallow)."""
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), color=(120, 40, 200)).save(buffer, format="JPEG")
        buffer.seek(0)
        photo = SimpleUploadedFile("signed.jpg", buffer.getvalue(), content_type="image/jpeg")
        response = self.client.post(
            "/api/v1/customers/customers/",
            {
                "email": "signed@example.com",
                "first_name": "Signed",
                "last_name": "Photo",
                "branch": self.branch.id,
                "profile_photo": photo,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, str(response.data))
        url = response.data["profile_photo"]
        self.assertIsNotNone(url, "profile_photo must never be None (silent swallow)")
        self.assertTrue(url.startswith("https://storage.googleapis.com/"))
        self.assertIn("Expires=", url)


class ADR002CustomerIdentityTests(APITestCase):
    """ADR-002 customer identity model — phone is the canonical key.

    Convergence at write time in BOTH directions: owner-create links/400s on
    phone matches; OTP login reuses owner-created users; email-only customers
    are non-loginable until a phone is set (update provisions the same user).
    """

    def setUp(self) -> None:
        """Tenant, owner, branch, and owner auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.owner_token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

    def _payload(self, email: str, **overrides) -> dict:
        """Frontend-shaped create payload (no user, no name)."""
        payload = {
            "email": email,
            "first_name": "Asha",
            "last_name": "Nair",
            "phone": "+919999000001",
            "branch": self.branch.id,
        }
        payload.update(overrides)
        return {k: v for k, v in payload.items() if v is not None}

    def test_create_links_synthetic_otp_user(self) -> None:
        """A phone matching a synthetic OTP user links it + adopts the email."""
        from apps.users.services import get_or_create_customer_by_phone

        synthetic_user = get_or_create_customer_by_phone("+919999000001", self.tenant)
        users_before = User.objects.count()

        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("asha@local.test", phone="+919999000001"),
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        customer = Customer.objects.get(email="asha@local.test")
        self.assertEqual(customer.user.id, synthetic_user.id)  # LINKED, no second user
        self.assertEqual(User.objects.count(), users_before)  # no new identity provisioned
        # Synthetic email replaced by the real one (converge at write time).
        synthetic_user.refresh_from_db()
        self.assertEqual(synthetic_user.email, "asha@local.test")
        self.assertEqual(customer.name, "Asha Nair")

    def test_create_phone_conflict_returns_400(self) -> None:
        """A phone held by a user with a different REAL email → 400, no mutation."""

        other = User.objects.create_user(
            email="real@elsewhere.test",
            password="***",
            first_name="Real",
            last_name="Identity",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+919999000001",
        )
        before_email = other.email
        users_before = User.objects.count()

        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("different@local.test", phone="+919999000001"),
            format="json",
        )
        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("different@local.test", phone="+919999000001"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.data)
        self.assertEqual(User.objects.count(), users_before)  # no second identity
        other.refresh_from_db()
        self.assertEqual(other.email, before_email)  # never silently mutated

    @override_settings(DEBUG=True, OTP_SENDER="stub")  # stub requires DEBUG (FBOS-011 §4.3)
    def test_otp_login_reuses_owner_created_user(self) -> None:
        """OTP verify reuses the owner-created customer user (rule 2)."""
        create_response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("owner-made@local.test", phone="+919999000002"),
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        created_user_id = create_response.data["user"]

        self.client.credentials()  # OTP endpoints are anonymous
        request_response = self.client.post(
            "/api/v1/users/auth/otp/request/",
            {"phone": "+919999000002", "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)
        otp_code = request_response.data["otp"]  # stub sender echoes the code
        verify_response = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "+919999000002", "otp": otp_code},
            format="json",
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertIsNotNone(verify_response.data.get("token"))
        self.assertEqual(
            verify_response.data.get("user", {}).get("id"),
            created_user_id,  # SAME user — no synthetic second identity
        )
        self.assertEqual(User.objects.count(), 2)  # owner + the one customer

    def test_email_only_customer_otp_request_clean_400(self) -> None:
        """An email-only customer hitting OTP request gets a clean 4xx."""
        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("emailonly@local.test", phone=None),
            format="json",
        )
        self.assertEqual(response.status_code, 201, str(response.data))  # email-only allowed

        self.client.credentials()  # OTP endpoints are anonymous
        otp_response = self.client.post(
            "/api/v1/users/auth/otp/request/",
            {},
            format="json",
        )
        self.assertEqual(otp_response.status_code, 400)
        self.assertIn("phone", otp_response.data)  # clean field error, no crash

    @override_settings(DEBUG=True, OTP_SENDER="stub")  # stub requires DEBUG (FBOS-011 §4.3)
    def test_update_phone_provisions_otp_capability(self) -> None:
        """PATCH phone provisions OTP capability on the SAME user (rule 3)."""
        response = self.client.post(
            "/api/v1/customers/customers/",
            self._payload("emailonly2@local.test", phone=None),
            format="json",
        )
        self.assertEqual(response.status_code, 201, str(response.data))
        customer = Customer.objects.get(email="emailonly2@local.test")
        self.assertEqual(customer.user.phone, "")  # email-only start

        patch_response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {"phone": "+919999000099", "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        customer.refresh_from_db()
        self.assertEqual(customer.phone, "+919999000099")
        customer.user.refresh_from_db()
        self.assertEqual(customer.user.phone, "+919999000099")

        # Convergence: the same user now authenticates via OTP.
        self.client.credentials()
        request_response = self.client.post(
            "/api/v1/users/auth/otp/request/",
            {"phone": "+919999000099", "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)
        otp_code = request_response.data["otp"]  # stub sender echoes the code
        verify_response = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "+919999000099", "otp": otp_code},
            format="json",
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertIsNotNone(verify_response.data.get("token"))
        self.assertEqual(
            verify_response.data.get("user", {}).get("id"),
            customer.user.id,  # SAME user — never a second identity
        )


class PostDeleteReAddCustomerTests(APITestCase):
    """Issue #72: add-customer must work after a customer was deleted.

    The ERP delete is ``DELETE /customers/{id}/`` (DRF destroy). Before the
    fix it hard-deleted the Customer row but left the linked portal User —
    its globally-unique email and phone then broke the re-add: a phone-only
    payload collided on the deterministic synthetic email (``400 email``),
    and a real-email identity tripped the ADR-002 ``phone_already_registered``
    guard (``400 phone``).
    """

    def setUp(self) -> None:
        """Tenant, owner, branch, and owner auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _add_customer(self, **payload) -> Response:
        """POST the ERP add-customer shape (no ``user``, no ``name``)."""
        payload.setdefault("first_name", "Asha")
        payload.setdefault("last_name", "Nair")
        payload.setdefault("branch", self.branch.id)
        return self.client.post("/api/v1/customers/customers/", payload, format="json")

    def _delete_customer(self, customer_id: int) -> Response:
        """The ERP delete path — DRF destroy on the customer viewset."""
        return self.client.delete(f"/api/v1/customers/customers/{customer_id}/")

    def test_delete_removes_linked_portal_user(self) -> None:
        """Deleting a customer also removes its customer-role portal user.

        Issue #81 re-baseline: the portal user is still deleted (its email +
        phone must be freed for re-add), but the Customer row itself now
        SURVIVES as a soft-deleted, PII-scrubbed marker for the history that
        still references it.
        """
        create_response = self._add_customer(phone="+919999000001", email="asha@local.test")
        self.assertEqual(create_response.status_code, 201, str(create_response.data))
        customer_id = create_response.data["id"]
        user_id = create_response.data["user"]

        delete_response = self._delete_customer(customer_id)
        self.assertEqual(delete_response.status_code, 204)

        self.assertFalse(User.objects.filter(pk=user_id).exists())
        # The phone is freed — no identity left holding it.
        self.assertFalse(User.objects.filter(tenant=self.tenant, phone="+919999000001").exists())
        # The row stays (soft delete), anonymized to the display marker.
        row = Customer.objects.get(pk=customer_id)
        self.assertIsNotNone(row.deleted_at)
        self.assertIsNone(row.user)
        self.assertEqual(row.name, "Deleted user")
        self.assertIsNone(row.email)
        self.assertEqual(row.phone, "")

    def test_readd_same_phone_with_email_after_delete(self) -> None:
        """Delete, then re-add the SAME phone with an email → 201."""
        create_response = self._add_customer(phone="+919999000002", email="asha@local.test")
        self.assertEqual(create_response.status_code, 201, str(create_response.data))
        self.assertEqual(self._delete_customer(create_response.data["id"]).status_code, 204)

        readd_response = self._add_customer(phone="+919999000002", email="asha@local.test")
        self.assertEqual(readd_response.status_code, 201, str(readd_response.data))
        self.assertEqual(readd_response.data["phone"], "+919999000002")
        self.assertEqual(Customer.objects.filter(tenant=self.tenant, phone="+919999000002").count(), 1)

    def test_readd_same_phone_phone_only_after_delete(self) -> None:
        """Delete, then re-add the SAME phone with no email → 201.

        Regression for the exact Siju report: the phone-only payload used to
        collide on the deterministic synthetic email of the orphaned user.
        """
        create_response = self._add_customer(phone="+919999000003")
        self.assertEqual(create_response.status_code, 201, str(create_response.data))
        self.assertEqual(self._delete_customer(create_response.data["id"]).status_code, 204)

        readd_response = self._add_customer(phone="+919999000003")
        self.assertEqual(readd_response.status_code, 201, str(readd_response.data))
        self.assertEqual(readd_response.data["email"], None)  # phone-only shape
        self.assertEqual(Customer.objects.filter(tenant=self.tenant, phone="+919999000003").count(), 1)

    def test_readd_different_phone_after_delete(self) -> None:
        """Delete, then add a DIFFERENT phone → 201 (control, was already OK)."""
        create_response = self._add_customer(phone="+919999000004")
        self.assertEqual(create_response.status_code, 201, str(create_response.data))
        self.assertEqual(self._delete_customer(create_response.data["id"]).status_code, 204)

        other_response = self._add_customer(phone="+919999000005", email="other@local.test")
        self.assertEqual(other_response.status_code, 201, str(other_response.data))

    def test_delete_keeps_non_customer_user_linked_to_profile(self) -> None:
        """A profile deliberately linked to a staff user: the user survives.

        Issue #81: the profile row is soft-deleted either way — only the
        portal-user removal is conditional on the customer role.
        """
        manager = User.objects.create_user(
            email="manager@local.test",
            password="F1tNati0n!",
            first_name="Manny",
            last_name="Ger",
            role=User.Role.MANAGER,
            tenant=self.tenant,
            phone="+919999000006",
        )
        customer = Customer.objects.create(
            tenant=self.tenant,
            user=manager,
            name="Manny Ger",
            phone="+919999000006",
        )

        delete_response = self._delete_customer(customer.id)
        self.assertEqual(delete_response.status_code, 204)
        manager.refresh_from_db()
        self.assertIsNotNone(User.objects.filter(pk=manager.pk).first())  # staff stays
        row = Customer.objects.get(pk=customer.id)  # soft-deleted, not removed
        self.assertIsNotNone(row.deleted_at)
        self.assertEqual(row.name, "Deleted user")

    def test_readd_adopts_orphaned_synthetic_identity(self) -> None:
        """A pre-fix orphan (synthetic user, no customer row) is re-linked.

        Production rows created before the delete fix keep their orphaned
        portal users; re-adding the same phone must LINK that identity (no
        second user, no synthetic-email IntegrityError).
        """
        from apps.users.services import synthetic_otp_email

        orphan = User.objects.create_user(
            email=synthetic_otp_email("+919999000007", self.tenant),
            password=None,
            first_name="Customer",
            last_name="+919999000007",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+919999000007",
        )
        users_before = User.objects.count()

        readd_response = self._add_customer(phone="+919999000007")
        self.assertEqual(readd_response.status_code, 201, str(readd_response.data))
        self.assertEqual(readd_response.data["user"], orphan.id)  # SAME identity
        self.assertEqual(User.objects.count(), users_before)  # no second user
        self.assertTrue(Customer.objects.filter(user=orphan, tenant=self.tenant).exists())

    def test_readd_adopts_orphaned_real_email_identity(self) -> None:
        """A pre-fix orphan holding a REAL email is re-linked for its owner.

        An orphaned customer-role identity has no live account behind it, so
        the phone is adoptable — unlike a live account, which still 400s
        (covered by ``ADR002CustomerIdentityTests``).
        """
        orphan = User.objects.create_user(
            email="orphan@local.test",
            password=None,
            first_name="Orphan",
            last_name="Ash",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+919999000008",
        )

        readd_response = self._add_customer(phone="+919999000008", email="orphan@local.test")
        self.assertEqual(readd_response.status_code, 201, str(readd_response.data))
        self.assertEqual(readd_response.data["user"], orphan.id)  # SAME identity
        self.assertTrue(Customer.objects.filter(user=orphan, tenant=self.tenant).exists())

    def test_orphan_contradicting_email_still_400(self) -> None:
        """An orphan is NOT adopted when the payload contradicts its email.

        A different real email on a phone match stays a manual-resolution
        case — the orphan's email is never silently replaced.
        """
        User.objects.create_user(
            email="orphan2@local.test",
            password=None,
            first_name="Orphan",
            last_name="Two",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+919999000010",
        )

        readd_response = self._add_customer(phone="+919999000010", email="someoneelse@local.test")
        self.assertEqual(readd_response.status_code, 400)
        self.assertIn("phone", readd_response.data)
        self.assertEqual(User.objects.filter(email="someoneelse@local.test").count(), 0)  # no mutation

    def test_orphaned_phone_with_staff_role_still_400(self) -> None:
        """A phone held by a NON-customer user without a profile still 400s."""
        trainer_user = User.objects.create_user(
            email="staff@local.test",
            password="F1tNati0n!",
            first_name="Staft",
            last_name="User",
            role=User.Role.TRAINER,
            tenant=self.tenant,
            phone="+919999000009",
        )

        readd_response = self._add_customer(phone="+919999000009")
        self.assertEqual(readd_response.status_code, 400)
        self.assertIn("phone", readd_response.data)
        trainer_user.refresh_from_db()
        self.assertEqual(trainer_user.phone, "+919999000009")  # never mutated


class SoftDeleteDeletedUserTests(APITestCase):
    """Issue #81: a deleted customer's references all render "Deleted user".

    The ERP delete soft-deletes the row (PII scrubbed, portal identity freed
    per #72) instead of removing it. Every surface that still references the
    member keeps its history row and renders the marker — backed by the
    scrubbed ``customer.name`` plus an explicit ``*_is_deleted`` flag.
    """

    def setUp(self) -> None:
        """Tenant, owner, branch, and owner auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _make_customer(
        self,
        phone: str,
        name: str = "Asha Nair",
        email: str | None = None,
    ) -> Customer:
        """Create a live customer with full PII directly in the tenant."""
        user = User.objects.create_user(
            email=email or f"cust{phone}@local.test",
            password=None,
            first_name=name.split(" ")[0],
            last_name=name.split(" ", 1)[1] if " " in name else "",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone=phone,
        )
        return Customer.objects.create(
            tenant=self.tenant,
            user=user,
            branch=self.branch,
            name=name,
            email=email,
            phone=phone,
            date_of_birth="1995-04-01",
            emergency_contact_name="Devan Nair",
            emergency_contact_phone="+919999999999",
            address_street="12 Lake View",
            address_city="Kochi",
            address_state="Kerala",
            address_postal_code="682001",
            notes="Prefers evening batches",
        )

    def _add_payment(self, customer: Customer, amount: str = "1499.00") -> Payment:
        """A completed membership payment referencing the customer."""
        return Payment.objects.create(
            tenant=self.tenant,
            customer=customer,
            amount=Decimal(amount),
            payment_method=Payment.PaymentMethod.UPI,
            status=Payment.Status.COMPLETED,
        )

    def _delete_customer(self, customer_id: int) -> Response:
        """The ERP delete path — DRF destroy on the customer viewset."""
        return self.client.delete(f"/api/v1/customers/customers/{customer_id}/")

    @staticmethod
    def _rows(response: Response) -> list:
        """List rows across paginated (``results``) and plain-list endpoints."""
        data = response.data
        return data["results"] if isinstance(data, dict) else data

    # ── the marker itself ────────────────────────────────────────────────

    def test_delete_soft_deletes_and_scrubs_all_pii(self) -> None:
        """DELETE keeps the row but wipes every personal field on it."""
        customer = self._make_customer("+918888000001", email="asha@local.test")
        user_id = customer.user_id

        self.assertEqual(self._delete_customer(customer.id).status_code, 204)

        row = Customer.objects.get(pk=customer.id)
        self.assertIsNotNone(row.deleted_at)
        self.assertEqual(row.name, "Deleted user")
        self.assertIsNone(row.email)
        self.assertEqual(row.phone, "")
        self.assertIsNone(row.date_of_birth)
        self.assertEqual(row.gender, Customer.Gender.PREFER_NOT_TO_SAY)
        self.assertIsNone(row.emergency_contact_name)
        self.assertIsNone(row.emergency_contact_phone)
        self.assertEqual(row.address_street, "")
        self.assertEqual(row.address_city, "")
        self.assertEqual(row.address_state, "")
        self.assertEqual(row.address_postal_code, "")
        self.assertEqual(row.notes, "")
        self.assertEqual(row.status, Customer.Status.INACTIVE)
        self.assertFalse(row.is_active)
        self.assertIsNone(row.user)
        self.assertFalse(User.objects.filter(pk=user_id).exists())  # #72 semantics

    def test_deleted_customer_hidden_from_list_search_and_detail(self) -> None:
        """The member list, its search, and the detail endpoint skip deleted."""
        customer = self._make_customer("+918888000002")
        self.assertEqual(self._delete_customer(customer.id).status_code, 204)

        list_response = self.client.get("/api/v1/customers/customers/")
        self.assertEqual(list_response.status_code, 200)
        ids = [row["id"] for row in self._rows(list_response)]
        self.assertNotIn(customer.id, ids)

        search_response = self.client.get("/api/v1/customers/customers/?search=%2B918888000002")
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual([row["id"] for row in self._rows(search_response)], [])

        detail_response = self.client.get(f"/api/v1/customers/customers/{customer.id}/")
        self.assertEqual(detail_response.status_code, 404)

        # The detail actions (health-profile etc.) bypass get_queryset with an
        # explicit tenant scope — deleted customers are excluded there too.
        health_response = self.client.get(f"/api/v1/customers/customers/{customer.id}/health-profile/")
        self.assertEqual(health_response.status_code, 404)

    def test_delete_twice_is_idempotent_404(self) -> None:
        """A second DELETE 404s (row excluded) — never a 500 on marked rows."""
        customer = self._make_customer("+918888000003")
        self.assertEqual(self._delete_customer(customer.id).status_code, 204)
        self.assertEqual(self._delete_customer(customer.id).status_code, 404)

    # ── surfaces that reference the deleted member ───────────────────────

    def test_payments_survive_and_render_deleted_user(self) -> None:
        """Payment history keeps its row; name + flag mark the member gone."""
        customer = self._make_customer("+918888000010")
        payment = self._add_payment(customer)

        self.assertEqual(self._delete_customer(customer.id).status_code, 204)
        self.assertTrue(Payment.objects.filter(pk=payment.pk).exists())

        response = self.client.get("/api/v1/payments/")
        self.assertEqual(response.status_code, 200)
        row = next(p for p in self._rows(response) if p["id"] == payment.id)
        self.assertEqual(row["customer_name"], "Deleted user")
        self.assertTrue(row["customer_is_deleted"])
        self.assertEqual(row["customer_id"], customer.id)  # reference intact

    def test_invoices_survive_and_render_deleted_user(self) -> None:
        """Invoices keep their row and name the deleted member correctly."""
        customer = self._make_customer("+918888000011")
        payment = self._add_payment(customer)
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            customer=customer,
            payment=payment,
            subtotal=Decimal("1499.00"),
            total=Decimal("1499.00"),
        )

        self.assertEqual(self._delete_customer(customer.id).status_code, 204)

        response = self.client.get("/api/v1/invoices/")
        self.assertEqual(response.status_code, 200)
        row = next(i for i in self._rows(response) if i["id"] == invoice.id)
        self.assertEqual(row["customer_name"], "Deleted user")
        self.assertTrue(row["customer_is_deleted"])

    def test_attendance_punches_survive_and_render_deleted_user(self) -> None:
        """Attendance history keeps its punches, person_* carries the marker."""
        customer = self._make_customer("+918888000012")
        record = AttendanceRecord.objects.create(
            tenant=self.tenant,
            customer=customer,
            branch=self.branch,
            check_in_time=timezone.now(),
            method=AttendanceRecord.Method.MANUAL,
        )

        self.assertEqual(self._delete_customer(customer.id).status_code, 204)
        self.assertTrue(AttendanceRecord.objects.filter(pk=record.pk).exists())

        response = self.client.get("/api/v1/attendance/attendance/")
        self.assertEqual(response.status_code, 200)
        row = next(r for r in self._rows(response) if r["id"] == record.id)
        self.assertEqual(row["person_name"], "Deleted user")
        self.assertTrue(row["person_is_deleted"])
        self.assertEqual(row["person_id"], customer.id)

    def test_memberships_survive_and_render_deleted_user(self) -> None:
        """Membership history keeps its rows; list carries the marker."""
        customer = self._make_customer("+918888000013")
        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Quarterly GTL",
            price=Decimal("3999.00"),
            duration_days=90,
        )
        membership = Membership.objects.create(
            tenant=self.tenant,
            customer=customer,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=90),
        )

        self.assertEqual(self._delete_customer(customer.id).status_code, 204)
        self.assertTrue(Membership.objects.filter(pk=membership.pk).exists())

        response = self.client.get("/api/v1/memberships/memberships/")
        self.assertEqual(response.status_code, 200)
        row = next(m for m in self._rows(response) if m["id"] == membership.id)
        self.assertEqual(row["customer_name"], "Deleted user")
        self.assertTrue(row["customer_is_deleted"])

    def test_trainer_assignment_and_session_survive_and_render_deleted_user(self) -> None:
        """PT assignment + session history survive with the marker."""
        customer = self._make_customer("+918888000014")
        trainer_user = User.objects.create_user(
            email="coach@local.test",
            password="F1tNati0n!",
            first_name="Coach",
            last_name="One",
            role=User.Role.TRAINER,
            tenant=self.tenant,
        )
        trainer = Trainer.objects.create(user=trainer_user)
        assignment = TrainerAssignment.objects.create(
            tenant=self.tenant,
            trainer=trainer,
            customer=customer,
            branch=self.branch,
        )
        session = TrainerSession.objects.create(
            tenant=self.tenant,
            trainer=trainer,
            customer=customer,
            branch=self.branch,
            scheduled_at=timezone.now() + timedelta(days=1),
            duration_minutes=60,
        )

        self.assertEqual(self._delete_customer(customer.id).status_code, 204)
        self.assertTrue(TrainerAssignment.objects.filter(pk=assignment.pk).exists())
        self.assertTrue(TrainerSession.objects.filter(pk=session.pk).exists())

        assignments = self.client.get("/api/v1/trainer-assignments/")
        self.assertEqual(assignments.status_code, 200)
        row = next(a for a in self._rows(assignments) if a["id"] == assignment.id)
        self.assertEqual(row["customer_name"], "Deleted user")
        self.assertTrue(row["customer_is_deleted"])

        sessions = self.client.get("/api/v1/trainer-sessions/")
        self.assertEqual(sessions.status_code, 200)
        row = next(s for s in self._rows(sessions) if s["id"] == session.id)
        self.assertEqual(row["customer_name"], "Deleted user")
        self.assertTrue(row["customer_is_deleted"])

    def test_workout_and_diet_assignments_survive_and_render_deleted_user(self) -> None:
        """Workout/diet plan assignments survive with the marker."""
        customer = self._make_customer("+918888000015")
        workout_plan = WorkoutPlan.objects.create(tenant=self.tenant, name="Beginner Cut")
        diet_plan = DietPlan.objects.create(tenant=self.tenant, name="Lean Bulk")
        workout = WorkoutAssignment.objects.create(
            tenant=self.tenant,
            customer=customer,
            workout_plan=workout_plan,
        )
        diet = DietAssignment.objects.create(
            tenant=self.tenant,
            customer=customer,
            diet_plan=diet_plan,
        )

        self.assertEqual(self._delete_customer(customer.id).status_code, 204)

        workouts = self.client.get("/api/v1/workouts/workout-assignments/")
        self.assertEqual(workouts.status_code, 200)
        row = next(a for a in self._rows(workouts) if a["id"] == workout.id)
        self.assertEqual(row["customer_name"], "Deleted user")
        self.assertTrue(row["customer_is_deleted"])

        diets = self.client.get("/api/v1/diet-assignments/")
        self.assertEqual(diets.status_code, 200)
        row = next(a for a in self._rows(diets) if a["id"] == diet.id)
        self.assertEqual(row["customer_name"], "Deleted user")
        self.assertTrue(row["customer_is_deleted"])

    def test_notification_logs_survive_and_render_deleted_user(self) -> None:
        """WhatsApp/notification history keeps its rows with the marker."""
        customer = self._make_customer("+918888000016")
        log = NotificationLog.objects.create(
            tenant=self.tenant,
            customer=customer,
            notification_type=NotificationLog.NotificationType.CHECK_IN,
            status=NotificationLog.Status.SENT,
            channel="whatsapp",
        )

        self.assertEqual(self._delete_customer(customer.id).status_code, 204)
        self.assertTrue(NotificationLog.objects.filter(pk=log.pk).exists())

        response = self.client.get("/api/v1/notifications/logs/")
        self.assertEqual(response.status_code, 200)
        row = next(n for n in self._rows(response) if n["id"] == log.id)
        self.assertEqual(row["customer_name"], "Deleted user")
        self.assertTrue(row["customer_is_deleted"])

    # ── invariants ────────────────────────────────────────────────────────

    def test_hard_delete_of_customer_with_history_is_protected(self) -> None:
        """A direct ``.delete()`` on a referenced customer raises loudly.

        Belt-and-suspenders behind the soft delete: no code path can
        silently destroy payment/attendance history anymore (issue #81).
        """
        customer = self._make_customer("+918888000017")
        self._add_payment(customer)

        with self.assertRaises(ProtectedError):
            customer.delete()

    def test_readd_creates_fresh_row_and_old_reference_stays_deleted(self) -> None:
        """Same-phone re-add: new live member, old history still marked.

        The #72 re-add contract under #81 semantics — the new row is a
        normal member; the deleted row's payment reference still renders
        "Deleted user" (it keeps pointing at the old, marked row).
        """
        customer = self._make_customer("+918888000018", email="asha@local.test")
        payment = self._add_payment(customer)
        self.assertEqual(self._delete_customer(customer.id).status_code, 204)

        readd = self.client.post(
            "/api/v1/customers/customers/",
            {"first_name": "Asha", "last_name": "Nair", "phone": "+918888000018", "email": "asha@local.test"},
            format="json",
        )
        self.assertEqual(readd.status_code, 201, str(readd.data))
        new_id = readd.data["id"]
        self.assertNotEqual(new_id, customer.id)

        # Old reference stays deleted even though the member is back.
        payments = self.client.get("/api/v1/payments/")
        row = next(p for p in self._rows(payments) if p["id"] == payment.id)
        self.assertEqual(row["customer_name"], "Deleted user")
        self.assertTrue(row["customer_is_deleted"])

        # The new member is live and searchable.
        members = self.client.get("/api/v1/customers/customers/")
        ids = [c["id"] for c in self._rows(members)]
        self.assertIn(new_id, ids)
        self.assertNotIn(customer.id, ids)

    def test_gdpr_self_deletion_sets_marker_and_surfaces_render_label(self) -> None:
        """The in-app GDPR deletion marks ``deleted_at``; surfaces agree.

        Stored name stays the §8 B8 "Deleted member #pk" fallback, but every
        serializer surface renders the unified "Deleted user" label (the
        CustomerSerializer normalizes from the marker).
        """
        customer = self._make_customer("+918888000019", email="gdpr@local.test")
        payment = self._add_payment(customer)

        returned = delete_customer_account(customer.user, self.tenant)
        self.assertIsNotNone(returned)
        row = Customer.objects.get(pk=customer.pk)
        self.assertIsNotNone(row.deleted_at)
        self.assertEqual(row.name, "Deleted user")  # same label as the ERP delete
        self.assertFalse(row.user.is_active)  # portal account anonymized, alive

        payments = self.client.get("/api/v1/payments/")
        payload = next(p for p in self._rows(payments) if p["id"] == payment.id)
        self.assertEqual(payload["customer_name"], "Deleted user")
        self.assertTrue(payload["customer_is_deleted"])


class OptionalContactCustomerTests(APITestCase):
    """Optional email/last-name customers (msg 2438) — phone-keyed identity.

    A customer needs a first name and an email OR a phone. Phone-only creates
    provision the portal user under the synthetic OTP email with a NULL
    customer email; adding a real email later adopts it onto the same user;
    the phone-OTP login path reuses the same identity (no duplicate rows).
    """

    def setUp(self) -> None:
        """Tenant, owner, branch, and owner auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.owner_token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

    def test_phone_only_create_provisions_synthetic_identity(self) -> None:
        """No email + phone → user keyed on the synthetic OTP email, NULL customer email."""
        response = self.client.post(
            "/api/v1/customers/customers/",
            {
                "first_name": "Ravi",
                "last_name": "Kumar",
                "phone": "+919999000101",
                "branch": self.branch.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, str(response.data))
        self.assertIsNone(response.data["email"])

        customer = Customer.objects.get(phone="+919999000101")
        self.assertIsNone(customer.email)
        self.assertEqual(customer.name, "Ravi Kumar")
        user = customer.user
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertTrue(user.email.endswith("@fitnation.local"))  # synthetic (tenant-scoped)
        self.assertEqual(user.phone, "+919999000101")
        self.assertTrue(user.is_email_verified)  # owner vouches
        self.assertFalse(user.has_usable_password())  # OTP login path

    def test_last_name_optional(self) -> None:
        """first_name alone composes the name; last_name may be omitted."""
        response = self.client.post(
            "/api/v1/customers/customers/",
            {
                "email": "single@local.test",
                "first_name": "Meera",
                "phone": "+919999000102",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, str(response.data))
        self.assertEqual(response.data["name"], "Meera")

    def test_both_email_and_phone_empty_returns_400(self) -> None:
        """Creating with neither email nor phone is a clean 400."""
        response = self.client.post(
            "/api/v1/customers/customers/",
            {"first_name": "No", "last_name": "Contact"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Provide an email or a phone number.", str(response.data["detail"]))
        self.assertEqual(Customer.objects.count(), 0)

    @override_settings(DEBUG=True, OTP_SENDER="stub")  # stub requires DEBUG (FBOS-011 §4.3)
    def test_otp_verify_reuses_phone_only_customer(self) -> None:
        """OTP verify after a phone-only create logs in the SAME user/profile."""
        create_response = self.client.post(
            "/api/v1/customers/customers/",
            {
                "first_name": "Ravi",
                "phone": "+919999000103",
                "branch": self.branch.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201, str(create_response.data))
        created_user_id = create_response.data["user"]
        customers_before = Customer.objects.count()

        self.client.credentials()  # OTP endpoints are anonymous
        request_response = self.client.post(
            "/api/v1/users/auth/otp/request/",
            {"phone": "+919999000103", "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)
        otp_code = request_response.data["otp"]  # stub sender echoes the code
        verify_response = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "+919999000103", "otp": otp_code},
            format="json",
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertIsNotNone(verify_response.data.get("token"))
        self.assertEqual(
            verify_response.data.get("user", {}).get("id"),
            created_user_id,  # SAME user — rule 2 reuse, no synthetic second identity
        )
        self.assertEqual(User.objects.count(), 2)  # owner + the one customer
        self.assertEqual(Customer.objects.count(), customers_before)  # no duplicate profile

    def test_patch_adopts_real_email_on_synthetic_customer(self) -> None:
        """Adding a real email to a phone-only customer adopts it on the SAME user."""
        create_response = self.client.post(
            "/api/v1/customers/customers/",
            {"first_name": "Ravi", "phone": "+919999000104"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        customer = Customer.objects.get(phone="+919999000104")

        patch_response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {"email": "ravi@local.test"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200, str(patch_response.data))
        customer.refresh_from_db()
        self.assertEqual(customer.email, "ravi@local.test")
        user = customer.user
        user.refresh_from_db()
        self.assertEqual(user.email, "ravi@local.test")  # SAME user, adopted email
        self.assertTrue(user.is_email_verified)  # owner vouches

    def test_patch_email_conflict_returns_400_and_mutates_nothing(self) -> None:
        """Adopting an email held by another user → 400; nothing is written."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        User.objects.create_user(
            email="taken@local.test",
            password="F1tNati0n!",
            first_name="Taken",
            last_name="Elsewhere",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        create_response = self.client.post(
            "/api/v1/customers/customers/",
            {"first_name": "Ravi", "phone": "+919999000105"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        customer = Customer.objects.get(phone="+919999000105")
        user_email_before = customer.user.email

        patch_response = self.client.patch(
            f"/api/v1/customers/customers/{customer.id}/",
            {"email": "taken@local.test"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 400)
        self.assertIn("email", patch_response.data)
        customer.refresh_from_db()
        self.assertIsNone(customer.email)  # customer email untouched
        customer.user.refresh_from_db()
        self.assertEqual(customer.user.email, user_email_before)  # synthetic email untouched

    def test_phone_only_create_links_existing_synthetic_otp_user(self) -> None:
        """A phone-only create matching an OTP synthetic user links it — no dup rows."""
        from apps.users.services import get_or_create_customer_by_phone

        synthetic_user = get_or_create_customer_by_phone("+919999000106", self.tenant)
        users_before = User.objects.count()

        response = self.client.post(
            "/api/v1/customers/customers/",
            {"first_name": "Ravi", "last_name": "Kumar", "phone": "+919999000106"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, str(response.data))
        self.assertIsNone(response.data["email"])

        customer = Customer.objects.get(phone="+919999000106")
        self.assertEqual(customer.user.id, synthetic_user.id)  # LINKED, no second user
        self.assertEqual(User.objects.count(), users_before)
        self.assertEqual(Customer.objects.filter(user=synthetic_user).count(), 1)  # OTP profile adopted
        self.assertIsNone(customer.email)  # nothing to adopt — synthetic email kept
        synthetic_user.refresh_from_db()
        self.assertTrue(synthetic_user.email.endswith("@fitnation.local"))  # untouched synthetic
        self.assertEqual(customer.name, "Ravi Kumar")


class AppInviteStatusPrefetchTests(APITestCase):
    """Issue #82: ``app_invite_status`` must not cost a query per row.

    The member list (and the reviews/feedback lists that nest the customer
    serializer) render each member's latest app-invite state. A filtered
    prefetch on the serving queryset feeds the serializer; these tests pin
    both the payload semantics and the query budget.
    """

    def setUp(self) -> None:
        """Create tenant, owner, two customers, and the auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.invited = Customer.objects.create(tenant=self.tenant, name="Invited", email="invited@local.test")
        self.never_invited = Customer.objects.create(tenant=self.tenant, name="Fresh", email="fresh@local.test")

    def _invite_log(self, customer, created_at, status="sent"):
        """Create an app_invite notification log at a specific moment."""
        return NotificationLog.objects.create(
            tenant=self.tenant,
            customer=customer,
            notification_type=NotificationLog.NotificationType.APP_INVITE,
            status=status,
            channel="whatsapp",
            error_message="boom" if status == "failed" else "",
            created_at=created_at,
        )

    def test_list_reports_latest_invite(self) -> None:
        """The newest invite log wins, payload shape unchanged."""
        older = self._invite_log(self.invited, timezone.now() - timedelta(days=2), status="failed")
        newer = self._invite_log(self.invited, timezone.now() - timedelta(days=1))

        response = self.client.get("/api/v1/customers/customers/")
        self.assertEqual(response.status_code, 200)
        rows = {row["name"]: row for row in response.data["results"]}
        self.assertEqual(
            rows["Invited"]["app_invite_status"],
            {
                "status": newer.status,
                "channel": newer.channel,
                "sent_at": newer.created_at,
                "error_message": None,
            },
        )
        self.assertGreater(newer.created_at, older.created_at)
        self.assertIsNone(rows["Fresh"]["app_invite_status"])

    def test_customers_list_query_budget(self) -> None:
        """25 members with mixed notification logs list in single-digit queries."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        now = timezone.now()
        for i in range(25):
            customer = Customer.objects.create(tenant=self.tenant, name=f"Member {i}", email=f"m{i}@local.test")
            NotificationLog.objects.create(
                tenant=self.tenant,
                customer=customer,
                notification_type=NotificationLog.NotificationType.CHECK_IN,
                status=NotificationLog.Status.SENT,
                created_at=now,
            )
            self._invite_log(customer, now - timedelta(minutes=i))

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/api/v1/customers/customers/")
        self.assertEqual(response.status_code, 200)
        # Auth + count + page + one filtered prefetch; an N+1 regression
        # lands at ~50 queries with 25 members.
        self.assertLessEqual(len(ctx.captured_queries), 8, f"customers list issued {len(ctx.captured_queries)}")

    def test_reviews_list_query_budget_with_nested_customers(self) -> None:
        """/reviews/ renders nested customer payloads without an N+1 (#82)."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.reviews.models import Review

        branch = Branch.objects.create(tenant=self.tenant, name="Main", address_line1="MG Road")
        now = timezone.now()
        for i in range(20):
            customer = Customer.objects.create(tenant=self.tenant, name=f"Reviewer {i}", email=f"rev{i}@local.test")
            self._invite_log(customer, now - timedelta(minutes=i))
            Review.objects.create(
                tenant=self.tenant,
                customer=customer,
                branch=branch,
                rating=4,
                text="Great equipment",
            )

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/api/v1/reviews/")
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(ctx.captured_queries), 8, f"reviews list issued {len(ctx.captured_queries)}")
        row = response.data["results"][0]
        self.assertIsNotNone(row["customer_detail"]["app_invite_status"])
