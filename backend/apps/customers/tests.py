"""Tests for the customers app."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.customers.models import (
    BodyMeasurement,
    Customer,
    FitnessGoal,
    HealthProfile,
    ProgressPhoto,
)
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
                "target_value": "5 kg",
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
            target_value="+3 kg muscle",
        )
        self.assertEqual(goal.customer, self.customer)
        self.assertEqual(goal.goal_type, "build_muscle")


class BodyMeasurementModelTests(TestCase):
    """Model tests for body measurements."""

    def setUp(self) -> None:
        """Create a tenant and customer."""
        self.tenant = provision_tenant(
            name="Measure Gym", contact_email="owner@local.test"
        )
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
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
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
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
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
            caption="Day 1",
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(ProgressPhoto.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(ProgressPhoto.objects.for_tenant(other_tenant).count(), 0)

    def test_progress_photo_ordering(self) -> None:
        """Progress photos are ordered by most recent taken_at first."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
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
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
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
        response = self.client.get(
            f"/api/v1/customers/customers/?branch={self.branch.id}"
        )
        self.assertEqual(response.status_code, 200)
        names = [r["name"] for r in response.data["results"]]
        self.assertIn("Alice Wonder", names)
        self.assertIn("Carol Singer", names)
        self.assertNotIn("Bob Builder", names)

    def test_filter_by_status(self) -> None:
        """Customers can be filtered by status."""
        response = self.client.get(
            "/api/v1/customers/customers/?status=inactive"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Bob Builder")

    def test_filter_by_gender(self) -> None:
        """Customers can be filtered by gender."""
        response = self.client.get(
            "/api/v1/customers/customers/?gender=female"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Alice Wonder")

    def test_search_by_name(self) -> None:
        """Customers can be searched by name."""
        response = self.client.get(
            "/api/v1/customers/customers/?search=Bob"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Bob Builder")

    def test_search_by_phone(self) -> None:
        """Customers can be searched by phone."""
        response = self.client.get(
            "/api/v1/customers/customers/?search=3333333333"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Carol Singer")

    def test_search_by_email(self) -> None:
        """Customers can be searched by email."""
        response = self.client.get(
            "/api/v1/customers/customers/?search=alice@local.test"
        )
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
        response = self.client.get(
            f"/api/v1/customers/customers/{self.customer.id}/progress-photos/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_create_progress_photo(self) -> None:
        """A progress photo can be created for a customer."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
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
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
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
        response = self.client.get(
            f"/api/v1/customers/customers/{self.customer.id}/progress-photos/"
        )
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
        response = self.client.get(
            f"/api/v1/customers/customers/{other_customer.id}/progress-photos/"
        )
        self.assertEqual(response.status_code, 404)
