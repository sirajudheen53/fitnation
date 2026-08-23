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
            f"/api/v1/customers/customers/{customer.id}/health_profile/",
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
            f"/api/v1/customers/customers/{customer.id}/health_profile/",
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
            f"/api/v1/customers/customers/{customer.id}/fitness_goals/",
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
            f"/api/v1/customers/customers/{customer.id}/fitness_goals/",
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
