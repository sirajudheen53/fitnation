"""Tests for the attendance app."""

import datetime as dt

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.attendance.models import AttendanceRecord, TrainerAttendance
from apps.attendance.selectors import attendance_stats
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
        self.assertEqual(AttendanceRecord.objects.for_tenant(self.tenant_a).count(), 1)
        self.assertEqual(AttendanceRecord.objects.for_tenant(self.tenant_b).count(), 0)

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
        return self.client.post("/api/v1/attendance/attendance/", payload, format="json")

    def test_log_attendance(self) -> None:
        """Owners can log attendance for a customer."""
        response = self._log()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["customer"], self.customer.id)
        self.assertEqual(response.data["method"], "qr")

    def test_list_and_filter_attendance(self) -> None:
        """Attendance can be listed and filtered by customer and date."""
        self._log()
        response = self.client.get(f"/api/v1/attendance/attendance/?customer={self.customer.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        response = self.client.get("/api/v1/attendance/attendance/?date=2026-08-23")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        response = self.client.get("/api/v1/attendance/attendance/?date=2026-08-24")
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
        response = self.client.get("/api/v1/attendance/attendance/reports/?period=daily")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["period"], "daily")
        total = sum(r["count"] for r in response.data["results"])
        self.assertEqual(total, 1)

    def test_tenant_isolation(self) -> None:
        """A user cannot see another tenant's attendance records."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_branch = Branch.objects.create(tenant=other_tenant, name="Other Branch", address_line1="Other")
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
        response = self.client.get("/api/v1/attendance/trainer-attendance/reports/?period=weekly")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["period"], "weekly")
        total = sum(r["count"] for r in response.data["results"])
        self.assertEqual(total, 1)


class CheckInViewTests(APITestCase):
    """Integration tests for POST /api/v1/attendance/check-in/."""

    def setUp(self) -> None:
        """Create tenant, owner, customer, trainer, branch, and auth token."""
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
        self.trainer = _make_trainer(self.tenant, "trainer@local.test")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_customer_check_in_returns_frontend_shape(self) -> None:
        """Check-in creates a record in the person_* shape the UI renders."""
        res = self.client.post(
            "/api/v1/attendance/check-in/",
            {
                "person_id": self.customer.id,
                "person_type": "customer",
                "branch_id": self.branch.id,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["person_type"], "customer")
        self.assertEqual(res.data["person_name"], "cust@local.test")
        self.assertEqual(res.data["status"], "present")
        self.assertIn("check_in_time", res.data)

    def test_trainer_check_in(self) -> None:
        """Trainer check-in creates a trainer attendance record."""
        res = self.client.post(
            "/api/v1/attendance/check-in/",
            {"person_id": self.trainer.id, "person_type": "trainer"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["person_type"], "trainer")

    def test_staff_check_in(self) -> None:
        """Staff check-in creates a staff attendance record."""
        staff_user = create_user(
            tenant=self.tenant,
            email="manager@local.test",
            first_name="Manny",
            last_name="Ger",
            role=User.Role.MANAGER,
        )
        res = self.client.post(
            "/api/v1/attendance/check-in/",
            {"person_id": staff_user.id, "person_type": "staff"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["person_type"], "staff")
        self.assertEqual(res.data["person_name"], "Manny Ger")

    def test_staff_check_in_rejects_customer(self) -> None:
        """A customer id with person_type 'staff' is rejected."""
        res = self.client.post(
            "/api/v1/attendance/check-in/",
            {"person_id": self.customer.user_id, "person_type": "staff"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_submitted_status_stored(self) -> None:
        """A submitted status ('late') is stored on the record."""
        res = self.client.post(
            "/api/v1/attendance/check-in/",
            {
                "person_id": self.customer.id,
                "person_type": "customer",
                "status": "late",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "late")

    def test_unknown_customer_rejected(self) -> None:
        """Check-in for a non-existent customer is rejected."""
        res = self.client.post(
            "/api/v1/attendance/check-in/",
            {"person_id": 99999, "person_type": "customer"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_duplicate_check_in_rejected(self) -> None:
        """A second open check-in for the same day is rejected."""
        payload = {"person_id": self.customer.id, "person_type": "customer"}
        self.client.post("/api/v1/attendance/check-in/", payload, format="json")
        res = self.client.post("/api/v1/attendance/check-in/", payload, format="json")
        self.assertEqual(res.status_code, 400)


class CheckOutTests(APITestCase):
    """Integration tests for the check-out action."""

    def setUp(self) -> None:
        """Create tenant, owner, customer, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_user(
            tenant=self.tenant,
            email="owner@local.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        self.token = issue_token(self.owner, self.tenant)
        self.customer = _make_customer(self.tenant, "cust@local.test")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _check_in(self):
        """Check the customer in and return the response."""
        return self.client.post(
            "/api/v1/attendance/check-in/",
            {"person_id": self.customer.id, "person_type": "customer"},
            format="json",
        )

    def test_check_out_stamps_time(self) -> None:
        """Check-out stamps check_out_time and returns status 'left'."""
        check_in = self._check_in()
        record_id = check_in.data["id"]
        res = self.client.post(
            f"/api/v1/attendance/attendance/{record_id}/check-out/",
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "left")
        self.assertIsNotNone(res.data["check_out_time"])

    def test_double_check_out_rejected(self) -> None:
        """A second check-out on the same record is rejected."""
        check_in = self._check_in()
        record_id = check_in.data["id"]
        self.client.post(
            f"/api/v1/attendance/attendance/{record_id}/check-out/",
            format="json",
        )
        res = self.client.post(
            f"/api/v1/attendance/attendance/{record_id}/check-out/",
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class AttendanceStatsViewTests(APITestCase):
    """Integration tests for GET /api/v1/attendance/stats/."""

    def setUp(self) -> None:
        """Create tenant, owner, customer, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_user(
            tenant=self.tenant,
            email="owner@local.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        self.token = issue_token(self.owner, self.tenant)
        self.customer = _make_customer(self.tenant, "cust@local.test")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_stats_shape(self) -> None:
        """Stats return the stats + weekly summary the frontend renders."""
        self.client.post(
            "/api/v1/attendance/check-in/",
            {"person_id": self.customer.id, "person_type": "customer"},
            format="json",
        )
        res = self.client.get("/api/v1/attendance/stats/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("stats", res.data)
        self.assertIn("summary", res.data)
        self.assertGreaterEqual(res.data["stats"]["today_count"], 1)
        self.assertEqual(len(res.data["summary"]["labels"]), 7)
        self.assertEqual(len(res.data["summary"]["check_ins"]), 7)


class TrainerCheckOutTests(APITestCase):
    """Integration tests for the trainer check-out action."""

    def setUp(self) -> None:
        """Create tenant, owner, trainer, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_user(
            tenant=self.tenant,
            email="owner@local.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        self.token = issue_token(self.owner, self.tenant)
        self.trainer = _make_trainer(self.tenant, "trainer@local.test")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _log_trainer(self):
        """Log a trainer attendance record via the API."""
        return self.client.post(
            "/api/v1/attendance/trainer-attendance/",
            {"trainer": self.trainer.id, "check_in_time": timezone.now().isoformat()},
            format="json",
        )

    def test_trainer_check_out(self) -> None:
        """Trainer check-out stamps check_out_time and sets status 'left'."""
        res = self._log_trainer()
        self.assertEqual(res.status_code, 201)
        record_id = res.data["id"]
        res = self.client.post(
            f"/api/v1/attendance/trainer-attendance/{record_id}/check-out/",
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "left")
        self.assertIsNotNone(res.data["check_out_time"])

    def test_double_trainer_check_out_rejected(self) -> None:
        """A second trainer check-out is rejected."""
        res = self._log_trainer()
        record_id = res.data["id"]
        self.client.post(
            f"/api/v1/attendance/trainer-attendance/{record_id}/check-out/",
            format="json",
        )
        res = self.client.post(
            f"/api/v1/attendance/trainer-attendance/{record_id}/check-out/",
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class StaffAttendanceTests(APITestCase):
    """Integration tests for staff attendance endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, staff user, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_user(
            tenant=self.tenant,
            email="owner@local.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        self.token = issue_token(self.owner, self.tenant)
        self.staff_user = create_user(
            tenant=self.tenant,
            email="manager@local.test",
            first_name="Manny",
            last_name="Ger",
            role=User.Role.MANAGER,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _check_in_staff(self):
        """Check the staff user in via the check-in endpoint."""
        return self.client.post(
            "/api/v1/attendance/check-in/",
            {"person_id": self.staff_user.id, "person_type": "staff"},
            format="json",
        )

    def test_staff_attendance_list(self) -> None:
        """The staff attendance list endpoint returns tenant records."""
        self._check_in_staff()
        res = self.client.get("/api/v1/attendance/staff-attendance/")
        self.assertEqual(res.status_code, 200)

    def test_staff_check_out(self) -> None:
        """Staff check-out stamps check_out_time and sets status 'left'."""
        check_in = self._check_in_staff()
        record_id = check_in.data["id"]
        res = self.client.post(
            f"/api/v1/attendance/staff-attendance/{record_id}/check-out/",
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "left")
        self.assertIsNotNone(res.data["check_out_time"])

    def test_double_staff_check_out_rejected(self) -> None:
        """A second staff check-out is rejected."""
        check_in = self._check_in_staff()
        record_id = check_in.data["id"]
        self.client.post(
            f"/api/v1/attendance/staff-attendance/{record_id}/check-out/",
            format="json",
        )
        res = self.client.post(
            f"/api/v1/attendance/staff-attendance/{record_id}/check-out/",
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class AttendanceStatsAggregationTests(TestCase):
    """Issue #82: the stats selector aggregates in SQL over all person types.

    Pins the metrics that used to be computed by hydrating a week of rows:
    today count, peak hour (today only), weekly distribution, weekly total,
    and the most frequent check-out hour — across customers, trainers and
    staff, with the 7-day window edges.
    """

    def setUp(self) -> None:
        """Create a tenant with one member of each person type."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.customer = _make_customer(self.tenant, "cust@local.test")
        self.trainer = _make_trainer(self.tenant, "trainer@local.test")
        self.staff = create_user(
            tenant=self.tenant,
            email="staff@local.test",
            first_name="Staff",
            last_name="User",
            role=User.Role.MANAGER,
        )

    def _customer_check_in(self, days_ago: int, hour: int, **extra):
        """Create a customer check-in N days ago at a given local hour."""
        moment = timezone.make_aware(
            dt.datetime.combine(
                timezone.localdate() - dt.timedelta(days=days_ago),
                dt.time(hour, 0),
            )
        )
        return AttendanceRecord.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            check_in_time=moment,
            check_out_time=extra.pop("check_out_time", moment + dt.timedelta(hours=1)),
            date=moment.date(),
            **extra,
        )

    def test_stats_across_person_types_and_window_edges(self) -> None:
        """Counts merge all three tables; the 7-day window cuts at 6 days ago."""
        # Today: two customer check-ins at 7:00 and one at 18:00.
        self._customer_check_in(0, 7)
        self._customer_check_in(0, 7)
        self._customer_check_in(0, 18)
        # Trainer + staff today at 7:00 — same hour as the customers.
        trainer_in = timezone.make_aware(dt.datetime.combine(timezone.localdate(), dt.time(7, 0)))
        TrainerAttendance.objects.create(
            tenant=self.tenant,
            trainer=self.trainer,
            check_in_time=trainer_in,
            check_out_time=trainer_in + dt.timedelta(hours=1),
            date=trainer_in.date(),
        )
        from apps.attendance.models import StaffAttendance

        StaffAttendance.objects.create(
            tenant=self.tenant,
            user=self.staff,
            check_in_time=trainer_in,
            check_out_time=trainer_in + dt.timedelta(hours=1),
            date=trainer_in.date(),
        )
        # Window edges: 6 days ago counts, 7 days ago does not.
        self._customer_check_in(6, 9)
        self._customer_check_in(7, 9)

        stats = attendance_stats(self.tenant)

        # 3 customers + 1 trainer + 1 staff today = 5.
        self.assertEqual(stats["stats"]["today_count"], 5)
        # 7:00 has 4 check-ins (2 customers + trainer + staff) vs 18:00's 1.
        self.assertEqual(stats["stats"]["peak_hour"], "07:00")
        self.assertEqual(stats["stats"]["peak_hour_count"], 4)
        # Weekly: today's 5 + 6-days-ago 1 = 6 (7-days-ago excluded).
        self.assertEqual(stats["stats"]["weekly_check_ins"], 6)
        self.assertEqual(stats["stats"]["avg_daily_check_ins"], round(6 / 7, 1))
        self.assertEqual(stats["summary"]["check_ins"][-1], 5)  # today's bucket
        self.assertEqual(stats["summary"]["check_ins"][0], 1)  # 6 days ago
        self.assertNotIn(7, stats["summary"]["check_ins"])  # 7 days ago cut
        # Dropouts: every check-out lands one hour after its check-in, so
        # 8:00 holds today's four 7:00 check-outs (customers + trainer +
        # staff); the 6-days-ago 9:00 check-out at 10:00 and 19:00 trail.
        self.assertEqual(stats["stats"]["most_frequent_dropout_hour"], "08:00")

    def test_empty_tenant_zeroes(self) -> None:
        """A tenant with no attendance gets well-formed zeros."""
        stats = attendance_stats(self.tenant)
        self.assertEqual(stats["stats"]["today_count"], 0)
        self.assertIsNone(stats["stats"]["peak_hour"])
        self.assertEqual(stats["stats"]["peak_hour_count"], 0)
        self.assertEqual(stats["stats"]["weekly_check_ins"], 0)
        self.assertIsNone(stats["stats"]["most_frequent_dropout_hour"])
        self.assertEqual(stats["summary"]["check_ins"], [0] * 7)

    def test_tenant_isolation(self) -> None:
        """Another tenant's check-ins never leak into the stats."""
        other = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_customer = _make_customer(other, "other@local.test")
        moment = timezone.now()
        AttendanceRecord.objects.create(
            tenant=other,
            customer=other_customer,
            check_in_time=moment,
            date=moment.date(),
        )
        stats = attendance_stats(self.tenant)
        self.assertEqual(stats["stats"]["today_count"], 0)
        self.assertEqual(stats["stats"]["weekly_check_ins"], 0)
