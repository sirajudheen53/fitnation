"""Tests for the attendance app."""

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.attendance.models import AttendanceRecord, TrainerAttendance
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_user, issue_token


def _make_customer(tenant, email):
    """Create a raw customer user and its Customer profile."""
    user = User.objects.create_user(
        email=email,
        password="F1tNati0n!",
        first_name="Customer",
        last_name="User",
        role=User.Role.CUSTOMER,
        tenant=tenant,
    )
    return Customer.objects.create(
        tenant=tenant,
        user=user,
        name=email,
        email=email,
    )


def _make_trainer(tenant, email):
    """Create a trainer user and return its auto-created Trainer profile."""
    user = create_user(
        tenant=tenant,
        email=email,
        first_name="Trainer",
        last_name="User",
        role=User.Role.TRAINER,
    )
    return user.trainer_profile


class AttendanceModelTests(TestCase):
    """Unit tests for attendance models and tenant isolation."""

    def setUp(self) -> None:
        """Create two isolated tenants and shared fixtures."""
        self.tenant_a = provision_tenant(name="Gym A", contact_email="a@local.test")
        self.tenant_b = provision_tenant(name="Gym B", contact_email="b@local.test")
        self.customer_a = _make_customer(self.tenant_a, "cust-a@local.test")
        self.customer_b = _make_customer(self.tenant_b, "cust-b@local.test")

    def test_attendance_requires_tenant(self) -> None:
        """Saving an attendance record without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            AttendanceRecord.objects.create(
                customer=self.customer_a,
                check_in_time=timezone.now(),
            )

    def test_date_auto_set_from_check_in_time(self) -> None:
        """The date field defaults to the local date of check_in_time."""
        check_in = timezone.localtime()
        record = AttendanceRecord.objects.create(
            tenant=self.tenant_a,
            customer=self.customer_a,
            check_in_time=check_in,
        )
        self.assertEqual(record.date, check_in.date())

    def test_attendance_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's attendance records."""
        AttendanceRecord.objects.create(
            tenant=self.tenant_a,
            customer=self.customer_a,
            check_in_time=timezone.now(),
        )
        self.assertEqual(
            AttendanceRecord.objects.for_tenant(self.tenant_a).count(), 1
        )
        self.assertEqual(
            AttendanceRecord.objects.for_tenant(self.tenant_b).count(), 0
        )

    def test_trainer_attendance_date_auto_set(self) -> None:
        """Trainer attendance date defaults to check_in_time's local date."""
        trainer = _make_trainer(self.tenant_a, "trainer-a@local.test")
        check_in = timezone.localtime()
        record = TrainerAttendance.objects.create(
            tenant=self.tenant_a,
            trainer=trainer,
            check_in_time=check_in,
        )
        self.assertEqual(record.date, check_in.date())

    def test_trainer_attendance_requires_tenant(self) -> None:
        """Saving trainer attendance without a tenant raises ValueError."""
        trainer = _make_trainer(self.tenant_a, "trainer-orphan@local.test")
        with self.assertRaises(ValueError):
            TrainerAttendance.objects.create(
                trainer=trainer,
                check_in_time=timezone.now(),
            )


class AttendanceAPITests(APITestCase):
    """Integration tests for attendance endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, customer, branch, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_user(
            tenant=self.tenant,
            email="owner@local.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.customer = _make_customer(self.tenant, "cust@local.test")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _log(self, **overrides):
        """Create an attendance record via the API."""
        payload = {
            "customer": self.customer.id,
            "branch": self.branch.id,
            "check_in_time": "2026-08-23T08:00:00+05:30",
            "method": "qr",
        }
        payload.update(overrides)
        return self.client.post(
            "/api/v1/attendance/attendance/", payload, format="json"
        )

    def test_log_attendance(self) -> None:
        """Owners can log attendance for a customer."""
        response = self._log()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["customer"], self.customer.id)
        self.assertEqual(response.data["method"], "qr")

    def test_list_and_filter_attendance(self) -> None:
        """Attendance can be listed and filtered by customer and date."""
        self._log()
        response = self.client.get(
            f"/api/v1/attendance/attendance/?customer={self.customer.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        response = self.client.get(
            "/api/v1/attendance/attendance/?date=2026-08-23"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        response = self.client.get(
            "/api/v1/attendance/attendance/?date=2026-08-24"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_check_out(self) -> None:
        """Owners can add a check-out time via partial update."""
        response = self._log()
        record_id = response.data["id"]
        response = self.client.patch(
            f"/api/v1/attendance/attendance/{record_id}/",
            {"check_out_time": "2026-08-23T10:00:00+05:30"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["check_out_time"])

    def test_reports_daily(self) -> None:
        """The reports action aggregates daily attendance counts."""
        self._log()
        response = self.client.get(
            "/api/v1/attendance/attendance/reports/?period=daily"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["period"], "daily")
        total = sum(r["count"] for r in response.data["results"])
        self.assertEqual(total, 1)

    def test_tenant_isolation(self) -> None:
        """A user cannot see another tenant's attendance records."""
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="other@local.test"
        )
        other_branch = Branch.objects.create(
            tenant=other_tenant, name="Other Branch", address_line1="Other"
        )
        other_customer = _make_customer(other_tenant, "other@local.test")
        AttendanceRecord.objects.create(
            tenant=other_tenant,
            customer=other_customer,
            branch=other_branch,
            check_in_time=timezone.now(),
        )

        response = self.client.get("/api/v1/attendance/attendance/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)


class TrainerAttendanceAPITests(APITestCase):
    """Integration tests for trainer attendance endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, trainer, branch, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_user(
            tenant=self.tenant,
            email="owner@local.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )
        self.trainer = _make_trainer(self.tenant, "trainer@local.test")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_log_trainer_attendance(self) -> None:
        """Owners can log trainer attendance."""
        response = self.client.post(
            "/api/v1/attendance/trainer-attendance/",
            {
                "trainer": self.trainer.id,
                "branch": self.branch.id,
                "check_in_time": "2026-08-23T08:00:00+05:30",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["trainer"], self.trainer.id)

    def test_trainer_attendance_reports(self) -> None:
        """Trainer attendance reports aggregate by period."""
        self.client.post(
            "/api/v1/attendance/trainer-attendance/",
            {
                "trainer": self.trainer.id,
                "branch": self.branch.id,
                "check_in_time": "2026-08-23T08:00:00+05:30",
            },
            format="json",
        )
        response = self.client.get(
            "/api/v1/attendance/trainer-attendance/reports/?period=weekly"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["period"], "weekly")
        total = sum(r["count"] for r in response.data["results"])
        self.assertEqual(total, 1)
