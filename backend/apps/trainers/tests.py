"""Tests for the trainers app (FBOS-007)."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.tenants.services import provision_tenant
from apps.trainers.models import TrainerAssignment, TrainerPerformance
from apps.users.models import TrainerSchedule, User
from apps.users.services import (
    create_owner_user,
    create_user,
    issue_token,
)
from apps.users.trainer_services import create_trainer


def _make_trainer(tenant, email="trainer@local.test"):
    """Create a trainer (user + profile) within a tenant."""
    return create_trainer(
        tenant=tenant,
        email=email,
        first_name="Alex",
        last_name="Trainer",
        specialization="Strength",
        max_clients=10,
    )


def _make_customer(tenant, email="customer@local.test"):
    """Create a customer within a tenant (profile auto-created by create_user)."""
    user = create_user(
        tenant=tenant,
        email=email,
        first_name="Casey",
        last_name="Customer",
        role=User.Role.CUSTOMER,
    )
    return user.customer_profile


class TrainerModelTests(TestCase):
    """Unit tests for trainer models and tenant isolation."""

    def setUp(self) -> None:
        """Create two isolated tenants and shared fixtures."""
        self.tenant_a = provision_tenant(name="Gym A", contact_email="a@local.test")
        self.tenant_b = provision_tenant(name="Gym B", contact_email="b@local.test")
        self.trainer_a = _make_trainer(self.tenant_a, "a@trainer.test")
        self.trainer_b = _make_trainer(self.tenant_b, "b@trainer.test")
        self.customer_a = _make_customer(self.tenant_a, "a@customer.test")
        self.customer_b = _make_customer(self.tenant_b, "b@customer.test")

    def test_assignment_requires_tenant(self) -> None:
        """Saving an assignment without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            TrainerAssignment.objects.create(
                trainer=self.trainer_a,
                customer=self.customer_a,
            )

    def test_assignment_unique_within_tenant(self) -> None:
        """A tenant cannot have duplicate (trainer, customer) assignments."""
        TrainerAssignment.objects.create(
            tenant=self.tenant_a,
            trainer=self.trainer_a,
            customer=self.customer_a,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrainerAssignment.objects.create(
                tenant=self.tenant_a,
                trainer=self.trainer_a,
                customer=self.customer_a,
            )
        # Same pair is fine in another tenant.
        TrainerAssignment.objects.create(
            tenant=self.tenant_b,
            trainer=self.trainer_b,
            customer=self.customer_b,
        )

    def test_assignment_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's assignments."""
        TrainerAssignment.objects.create(
            tenant=self.tenant_a,
            trainer=self.trainer_a,
            customer=self.customer_a,
        )
        TrainerAssignment.objects.create(
            tenant=self.tenant_b,
            trainer=self.trainer_b,
            customer=self.customer_b,
        )
        self.assertEqual(TrainerAssignment.objects.for_tenant(self.tenant_a).count(), 1)
        self.assertEqual(TrainerAssignment.objects.for_tenant(self.tenant_b).count(), 1)

    def test_performance_unique_within_tenant(self) -> None:
        """A tenant cannot have duplicate (trainer, month) performance records."""
        month = "2026-01-01"
        TrainerPerformance.objects.create(
            tenant=self.tenant_a,
            trainer=self.trainer_a,
            month=month,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrainerPerformance.objects.create(
                tenant=self.tenant_a,
                trainer=self.trainer_a,
                month=month,
            )
        # Same trainer+month is fine in another tenant.
        TrainerPerformance.objects.create(
            tenant=self.tenant_b,
            trainer=self.trainer_b,
            month=month,
        )

    def test_performance_requires_tenant(self) -> None:
        """Saving a performance record without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            TrainerPerformance.objects.create(
                trainer=self.trainer_a,
                month="2026-01-01",
            )

    def test_performance_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's performance records."""
        TrainerPerformance.objects.create(
            tenant=self.tenant_a,
            trainer=self.trainer_a,
            month="2026-01-01",
            revenue=Decimal("1000.00"),
        )
        TrainerPerformance.objects.create(
            tenant=self.tenant_b,
            trainer=self.trainer_b,
            month="2026-01-01",
            revenue=Decimal("5000.00"),
        )
        self.assertEqual(TrainerPerformance.objects.for_tenant(self.tenant_a).count(), 1)
        self.assertEqual(TrainerPerformance.objects.for_tenant(self.tenant_b).count(), 1)


class TrainerScheduleModelTests(TestCase):
    """Tests for the existing users.TrainerSchedule model used via the trainers app."""

    def setUp(self) -> None:
        """Create a tenant and trainer."""
        self.tenant = provision_tenant(name="Gym A", contact_email="a@local.test")
        self.trainer = _make_trainer(self.tenant)

    def test_schedule_requires_tenant(self) -> None:
        """Saving a schedule without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            TrainerSchedule.objects.create(
                trainer=self.trainer,
                day_of_week="monday",
                start_time="09:00",
                end_time="10:00",
            )

    def test_schedule_day_unique_per_trainer(self) -> None:
        """A trainer can only have one schedule per day."""
        TrainerSchedule.objects.create(
            tenant=self.tenant,
            trainer=self.trainer,
            day_of_week="monday",
            start_time="09:00",
            end_time="10:00",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrainerSchedule.objects.create(
                tenant=self.tenant,
                trainer=self.trainer,
                day_of_week="monday",
                start_time="11:00",
                end_time="12:00",
            )


class TrainerAPITests(APITestCase):
    """Integration tests for trainer endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_list_trainers(self) -> None:
        """Owners can list trainers in their tenant."""
        _make_trainer(self.tenant, "a@trainer.test")
        response = self.client.get("/api/v1/trainers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_trainers_tenant_scoped(self) -> None:
        """Trainer list is filtered to the authenticated tenant."""
        _make_trainer(self.tenant, "mine@trainer.test")
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        _make_trainer(other_tenant, "other@trainer.test")

        response = self.client.get("/api/v1/trainers/")
        self.assertEqual(response.status_code, 200)
        emails = {t["email"] for t in response.data}
        self.assertIn("mine@trainer.test", emails)
        self.assertNotIn("other@trainer.test", emails)

    def test_retrieve_trainer(self) -> None:
        """Owners can retrieve a trainer's detail."""
        trainer = _make_trainer(self.tenant, email="detail@trainer.test")
        response = self.client.get(f"/api/v1/trainers/{trainer.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "detail@trainer.test")

    def test_cross_tenant_trainer_access_blocked(self) -> None:
        """Owners cannot access trainers belonging to another tenant."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        trainer = _make_trainer(other_tenant, "other@trainer.test")
        response = self.client.get(f"/api/v1/trainers/{trainer.id}/")
        self.assertEqual(response.status_code, 404)

    def test_trainer_performance_metrics(self) -> None:
        """The performance action returns aggregated metrics for a trainer."""
        trainer = _make_trainer(self.tenant, email="perf@trainer.test")
        TrainerPerformance.objects.create(
            tenant=self.tenant,
            trainer=trainer,
            month="2026-01-01",
            revenue=Decimal("1000.00"),
            customer_count=5,
            sessions_completed=20,
            rating_avg=Decimal("4.50"),
        )
        TrainerPerformance.objects.create(
            tenant=self.tenant,
            trainer=trainer,
            month="2026-02-01",
            revenue=Decimal("2000.00"),
            customer_count=8,
            sessions_completed=30,
            rating_avg=Decimal("4.80"),
        )
        response = self.client.get(f"/api/v1/trainers/{trainer.id}/performance/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_revenue"], Decimal(3000))
        self.assertEqual(response.data["total_sessions_completed"], 50)
        self.assertEqual(len(response.data["monthly_records"]), 2)

    def test_assignment_create_and_unassign(self) -> None:
        """Owners can create, list, and unassign an assignment."""
        trainer = _make_trainer(self.tenant, email="assign@trainer.test")
        customer = _make_customer(self.tenant, "assign@customer.test")
        branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main",
            address_line1="MG Road",
        )

        create_resp = self.client.post(
            "/api/v1/trainer-assignments/",
            {"trainer": trainer.id, "customer": customer.id, "branch": branch.id},
        )
        self.assertEqual(create_resp.status_code, 201)
        assignment_id = create_resp.data["id"]

        list_resp = self.client.get("/api/v1/trainer-assignments/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.data), 1)

        unassign_resp = self.client.post(f"/api/v1/trainer-assignments/{assignment_id}/unassign/")
        self.assertEqual(unassign_resp.status_code, 200)
        self.assertFalse(unassign_resp.data["is_active"])
        self.assertIsNotNone(unassign_resp.data["unassigned_at"])

    def test_assignment_tenant_isolation_api(self) -> None:
        """Assignments are scoped to the authenticated tenant."""
        trainer = _make_trainer(self.tenant, email="a@trainer.test")
        customer = _make_customer(self.tenant, "a@customer.test")
        TrainerAssignment.objects.create(tenant=self.tenant, trainer=trainer, customer=customer)
        other_tenant = provision_tenant(name="Other", contact_email="other@local.test")
        other_trainer = _make_trainer(other_tenant, "b@trainer.test")
        other_customer = _make_customer(other_tenant, "b@customer.test")
        TrainerAssignment.objects.create(tenant=other_tenant, trainer=other_trainer, customer=other_customer)

        response = self.client.get("/api/v1/trainer-assignments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["trainer_email"], "a@trainer.test")

    def test_trainer_schedule_endpoint(self) -> None:
        """Owners can create a schedule for a trainer."""
        trainer = _make_trainer(self.tenant, email="sched@trainer.test")
        response = self.client.post(
            "/api/v1/trainer-schedules/",
            {
                "trainer": trainer.id,
                "day_of_week": "monday",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["day_of_week"], "monday")

    def test_manager_cannot_edit_trainers(self) -> None:
        """Managers lack the trainers.edit_trainer permission (edit denied)."""
        manager = create_user(
            tenant=self.tenant,
            email="manager@local.test",
            first_name="Manager",
            last_name="One",
            role=User.Role.MANAGER,
        )
        token = issue_token(manager, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        trainer = _make_trainer(self.tenant, email="mgmt@trainer.test")
        customer = _make_customer(self.tenant, "mgmt@customer.test")

        response = self.client.post(
            "/api/v1/trainer-assignments/",
            {"trainer": trainer.id, "customer": customer.id},
        )
        self.assertEqual(response.status_code, 403)
