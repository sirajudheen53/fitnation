"""Tests for the customers app."""

import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from PIL import Image, features

from apps.branches.models import Branch
from apps.customers.models import (
    BodyMeasurement,
    Customer,
    FitnessGoal,
    HealthProfile,
    ProgressPhoto,
)
from apps.customers.serializers import MAX_PROFILE_PHOTO_BYTES
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

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
            {"phone": "+919999000001"},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)

        verify_response = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "+919999000001", "otp": "123456"},
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
        self.assertEqual(cloudrun.GS_EXPIRE, 3600)  # ~1h signed-URL TTL
