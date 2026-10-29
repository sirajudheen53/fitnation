"""Query-count guards for the web ERP's hot list endpoints (issue #82).

Each test seeds a page's worth of rows (plus extra), hits the list endpoint
as the owner, and asserts the captured SQL stays at a small constant — the
serializers traverse customer/plan/branch/equipment relations, and a missing
``select_related``/``prefetch_related`` resurfaces as O(rows) queries that
these bounds catch. Payload correctness is owned by the per-app suites.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.attendance.models import AttendanceRecord, StaffAttendance, TrainerAttendance
from apps.customers.models import Customer
from apps.inventory.models import Equipment, InventoryItem, MaintenanceLog
from apps.memberships.models import Membership, MembershipPlan
from apps.notifications.models import NotificationLog
from apps.payments.models import Invoice, Payment
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_user, issue_token

#: Rows seeded per relation — a page is 20, so an N+1 regression shows up
#: as ≥ 21 queries where the budgets below allow single digits.
ROW_COUNT = 25


class ListQueryCountGuardTests(APITestCase):
    """One query-count assertion per fixed list endpoint."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Seed one tenant: owner, customers, plans, payments, attendance…"""
        cls.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        cls.owner = create_user(
            tenant=cls.tenant,
            email="owner@local.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        cls.token = issue_token(cls.owner, cls.tenant)
        cls.trainer_user = create_user(
            tenant=cls.tenant,
            email="trainer@local.test",
            first_name="Trainer",
            last_name="User",
            role=User.Role.TRAINER,
        )
        cls.staff = create_user(
            tenant=cls.tenant,
            email="staff@local.test",
            first_name="Staff",
            last_name="User",
            role=User.Role.MANAGER,
        )

        cls.plan = MembershipPlan.objects.create(tenant=cls.tenant, name="Monthly", price="1500.00", duration_days=30)
        today = timezone.localdate()
        now = timezone.now()
        cls.customers = [
            Customer.objects.create(tenant=cls.tenant, name=f"Member {i}", email=f"member{i}@local.test")
            for i in range(ROW_COUNT)
        ]
        for i, customer in enumerate(cls.customers):
            membership = Membership.objects.create(
                tenant=cls.tenant,
                customer=customer,
                plan=cls.plan,
                start_date=today - timedelta(days=60),
                end_date=today + timedelta(days=30),
            )
            payment = Payment.objects.create(
                tenant=cls.tenant,
                customer=customer,
                membership=membership,
                amount="1500.00",
                payment_method=Payment.PaymentMethod.UPI,
                status=Payment.Status.COMPLETED,
                paid_at=now - timedelta(days=i),
            )
            Invoice.objects.create(
                tenant=cls.tenant,
                customer=customer,
                payment=payment,
                subtotal="1500.00",
                total="1500.00",
            )
            NotificationLog.objects.create(
                tenant=cls.tenant,
                customer=customer,
                notification_type=NotificationLog.NotificationType.WELCOME,
                status=NotificationLog.Status.SENT,
                channel="whatsapp",
            )
            check_in = now - timedelta(days=i % 7, hours=i)
            AttendanceRecord.objects.create(
                tenant=cls.tenant,
                customer=customer,
                check_in_time=check_in,
                date=timezone.localdate(check_in),
            )
        trainer_check_in = now - timedelta(hours=1)
        cls.trainer_attendance = TrainerAttendance.objects.create(
            tenant=cls.tenant,
            trainer=cls.trainer_user.trainer_profile,
            check_in_time=trainer_check_in,
            date=timezone.localdate(trainer_check_in),
        )
        StaffAttendance.objects.create(
            tenant=cls.tenant,
            user=cls.staff,
            check_in_time=trainer_check_in,
            date=timezone.localdate(trainer_check_in),
        )
        equipment = Equipment.objects.create(tenant=cls.tenant, name="Treadmill")
        InventoryItem.objects.create(tenant=cls.tenant, equipment=equipment, stock_quantity=4)
        MaintenanceLog.objects.create(tenant=cls.tenant, equipment=equipment)

    def _list_query_count(self, url: str) -> int:
        """GET a list endpoint as the owner and return the SQL query count."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(ctx.captured_queries)

    def test_payments_list_query_budget(self) -> None:
        """/payments/ serializes customer, plan and invoices in constant queries."""
        count = self._list_query_count("/api/v1/payments/")
        # Budget: auth + count + page + invoice prefetch. An N+1 regression
        # (customer/plan/invoice per row) lands at ~40-80 queries.
        self.assertLessEqual(count, 8, f"payments list issued {count} queries")

    def test_invoices_list_query_budget(self) -> None:
        """/invoices/ joins its customer (#82)."""
        count = self._list_query_count("/api/v1/invoices/")
        self.assertLessEqual(count, 8, f"invoices list issued {count} queries")

    def test_memberships_list_query_budget(self) -> None:
        """/memberships/ joins customer+plan (#82)."""
        count = self._list_query_count("/api/v1/memberships/memberships/")
        self.assertLessEqual(count, 8, f"memberships list issued {count} queries")

    def test_attendance_list_query_budget(self) -> None:
        """/attendance/ joins customer+branch (#82)."""
        count = self._list_query_count("/api/v1/attendance/attendance/")
        self.assertLessEqual(count, 8, f"attendance list issued {count} queries")

    def test_trainer_attendance_list_query_budget(self) -> None:
        """/attendance/trainer-attendance/ joins trainer user+branch (#82)."""
        count = self._list_query_count("/api/v1/attendance/trainer-attendance/")
        self.assertLessEqual(count, 8, f"trainer-attendance list issued {count} queries")

    def test_staff_attendance_list_query_budget(self) -> None:
        """/attendance/staff-attendance/ joins user+branch (#82)."""
        count = self._list_query_count("/api/v1/attendance/staff-attendance/")
        self.assertLessEqual(count, 8, f"staff-attendance list issued {count} queries")

    def test_notification_logs_list_query_budget(self) -> None:
        """/notifications/logs/ joins its customer (#82)."""
        count = self._list_query_count("/api/v1/notifications/logs/")
        self.assertLessEqual(count, 8, f"notification logs list issued {count} queries")

    def test_inventory_item_list_query_budget(self) -> None:
        """/inventory/inventory-items/ joins its equipment (#82)."""
        count = self._list_query_count("/api/v1/inventory/inventory-items/")
        self.assertLessEqual(count, 8, f"inventory items list issued {count} queries")

    def test_maintenance_log_list_query_budget(self) -> None:
        """/inventory/maintenance-logs/ joins its equipment (#82)."""
        count = self._list_query_count("/api/v1/inventory/maintenance-logs/")
        self.assertLessEqual(count, 8, f"maintenance logs list issued {count} queries")

    def test_payments_page_payload_is_unchanged(self) -> None:
        """The joins don't alter the payment row contract (spot check)."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/v1/payments/")
        self.assertEqual(response.status_code, 200)
        row = response.data["results"][0]
        self.assertEqual(row["customer_name"], f"Member {ROW_COUNT - 1}")
        self.assertEqual(row["plan_name"], "Monthly")
        self.assertEqual(row["amount"], "1500.00")
        self.assertIsNotNone(row["invoice_id"])
        self.assertFalse(row["customer_is_deleted"])
