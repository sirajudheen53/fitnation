"""Tests for the notifications app."""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.attendance.models import AttendanceRecord
from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.notifications.models import NotificationLog
from apps.notifications.services.wati_service import (
    MESSAGE_TEMPLATES,
    build_message,
    send_notification,
)
from apps.payments.models import Payment
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token
from apps.workouts.models import WorkoutAssignment, WorkoutPlan

User = get_user_model()


class NotificationLogModelTests(TestCase):
    """Unit tests for the NotificationLog model."""

    def setUp(self) -> None:
        """Create a tenant, user, and customer."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.user = User.objects.create_user(
            email="cust@local.test",
            password="F1tNati0n!",
            first_name="Cust",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Cust Customer",
            email="cust@local.test",
            phone="+919000000000",
        )

    def test_requires_tenant(self) -> None:
        """Saving a log without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            NotificationLog.objects.create(notification_type=NotificationLog.NotificationType.CHECK_IN)

    def test_default_status_pending(self) -> None:
        """A new log defaults to pending status."""
        log = NotificationLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type=NotificationLog.NotificationType.CHECK_IN,
        )
        self.assertEqual(log.status, NotificationLog.Status.PENDING)

    def test_tenant_isolation(self) -> None:
        """Logs are scoped to their tenant."""
        log = NotificationLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type=NotificationLog.NotificationType.CHECK_IN,
        )
        other = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(NotificationLog.objects.for_tenant(self.tenant).first().id, log.id)
        self.assertEqual(NotificationLog.objects.for_tenant(other).count(), 0)


class WatiServiceTests(TestCase):
    """Unit tests for the Wati service."""

    def setUp(self) -> None:
        """Create a tenant, user, and customer."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "wati_secret_key"
        self.tenant.wati_endpoint = "https://api.wati.io/api/v1/sendSessionMessage"
        self.tenant.save()
        self.user = User.objects.create_user(
            email="cust@local.test",
            password="F1tNati0n!",
            first_name="Cust",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Cust Customer",
            email="cust@local.test",
            phone="+919000000000",
        )

    def test_disabled_tenant_logs_skipped(self) -> None:
        """When Wati is disabled, notifications are logged as skipped."""
        self.tenant.is_wati_enabled = False
        self.tenant.save()
        log = send_notification(self.tenant, self.customer, NotificationLog.NotificationType.CHECK_IN, {})
        self.assertEqual(log.status, NotificationLog.Status.SKIPPED)
        self.assertIn("not enabled", log.error_message)

    def test_missing_api_key_logs_failed(self) -> None:
        """A missing API key is logged as failed without calling the API."""
        self.tenant.wati_api_key = ""
        self.tenant.save()
        with mock.patch("apps.notifications.services.wati_service.requests.post") as m:
            log = send_notification(
                self.tenant,
                self.customer,
                NotificationLog.NotificationType.CHECK_IN,
                {},
            )
        m.assert_not_called()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)

    def test_successful_send_logs_sent(self) -> None:
        """A successful POST logs the notification as sent with a message id."""
        fake_response = mock.Mock()
        fake_response.json.return_value = {"messageId": "wati_msg_123"}
        fake_response.raise_for_status = mock.Mock()

        with mock.patch(
            "apps.notifications.services.wati_service.requests.post",
            return_value=fake_response,
        ) as m:
            log = send_notification(
                self.tenant,
                self.customer,
                NotificationLog.NotificationType.CHECK_IN,
                {"customer_name": "Cust Customer"},
            )

        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.wati_message_id, "wati_msg_123")
        m.assert_called_once()
        call_kwargs = m.call_args[1]
        self.assertEqual(call_kwargs["headers"]["Authorization"], "wati_secret_key")
        self.assertEqual(call_kwargs["json"]["to"], "+919000000000")

    def test_send_failure_logs_failed(self) -> None:
        """A failed request logs the notification as failed with the error."""
        fake_response = mock.Mock()
        fake_response.raise_for_status.side_effect = Exception("HTTP 500")

        with mock.patch(
            "apps.notifications.services.wati_service.requests.post",
            return_value=fake_response,
        ):
            log = send_notification(
                self.tenant,
                self.customer,
                NotificationLog.NotificationType.CHECK_IN,
                {},
            )
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn("HTTP 500", log.error_message)

    def test_build_message_renders_context(self) -> None:
        """Message templates render with context values."""
        msg = build_message(
            "check_in",
            {"customer_name": "Ravi", "gym_name": "Iron Peak"},
        )
        self.assertIn("Ravi", msg)
        self.assertIn("Iron Peak", msg)

    def test_build_message_missing_key_returns_template(self) -> None:
        """Missing context keys do not raise."""
        msg = build_message("check_in", {})
        self.assertEqual(msg, MESSAGE_TEMPLATES["check_in"])

    def test_payment_received_template_has_amount(self) -> None:
        """The payment template includes the amount."""
        msg = build_message(
            "payment_received",
            {"customer_name": "Ravi", "amount": "1500", "gym_name": "Iron Peak"},
        )
        self.assertIn("1500", msg)


class NotificationSignalTests(TestCase):
    """Tests for signal receivers that trigger notifications."""

    def setUp(self) -> None:
        """Create tenant, user, customer, plan, and branch."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "wati_secret_key"
        self.tenant.save()
        self.user = User.objects.create_user(
            email="cust@local.test",
            password="F1tNati0n!",
            first_name="Cust",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Cust Customer",
            email="cust@local.test",
            phone="+919000000000",
        )
        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly",
            price="1500.00",
            duration_days=30,
        )

    def test_attendance_created_triggers_check_in(self) -> None:
        """Creating an attendance record sends a check-in notification."""
        with mock.patch("apps.notifications.services.wati_service.requests.post") as m:
            m.return_value.json.return_value = {"messageId": "m1"}
            AttendanceRecord.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                check_in_time=timezone.now(),
            )
        self.assertTrue(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.CHECK_IN,
            ).exists()
        )

    def test_membership_near_expiry_triggers_reminder(self) -> None:
        """A membership within 7 days of expiry triggers a reminder."""
        with mock.patch("apps.notifications.services.wati_service.requests.post") as m:
            m.return_value.json.return_value = {"messageId": "m2"}
            Membership.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                plan=self.plan,
                start_date=timezone.localdate(),
                end_date=timezone.localdate() + timedelta(days=5),
            )
        self.assertTrue(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.MEMBERSHIP_EXPIRY,
            ).exists()
        )

    def test_membership_far_from_expiry_no_reminder(self) -> None:
        """A membership more than 7 days from expiry does not remind."""
        with mock.patch("apps.notifications.services.wati_service.requests.post") as m:
            m.return_value.json.return_value = {"messageId": "m3"}
            Membership.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                plan=self.plan,
                start_date=timezone.localdate(),
                end_date=timezone.localdate() + timedelta(days=30),
            )
        self.assertFalse(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.MEMBERSHIP_EXPIRY,
            ).exists()
        )

    def test_workout_assignment_triggers_notification(self) -> None:
        """Creating a workout assignment sends a notification."""
        plan = WorkoutPlan.objects.create(tenant=self.tenant, name="Fat Burn", goal="weight_loss")
        with mock.patch("apps.notifications.services.wati_service.requests.post") as m:
            m.return_value.json.return_value = {"messageId": "m4"}
            WorkoutAssignment.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                workout_plan=plan,
            )
        self.assertTrue(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.WORKOUT_ASSIGNED,
            ).exists()
        )

    def test_payment_paid_triggers_receipt(self) -> None:
        """A completed payment sends a payment-received notification."""
        with mock.patch("apps.notifications.services.wati_service.requests.post") as m:
            m.return_value.json.return_value = {"messageId": "m5"}
            Payment.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                amount="1500.00",
                payment_method=Payment.PaymentMethod.ONLINE,
                status=Payment.Status.COMPLETED,
            )
        self.assertTrue(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.PAYMENT_RECEIVED,
            ).exists()
        )

    def test_pending_payment_no_notification(self) -> None:
        """A pending payment does not send a receipt notification."""
        with mock.patch("apps.notifications.services.wati_service.requests.post") as m:
            m.return_value.json.return_value = {"messageId": "m6"}
            Payment.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                amount="1500.00",
                payment_method=Payment.PaymentMethod.ONLINE,
                status=Payment.Status.PENDING,
            )
        self.assertFalse(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.PAYMENT_RECEIVED,
            ).exists()
        )

    def test_signal_errors_are_swallowed(self) -> None:
        """A signal that raises does not break the triggering workflow."""
        with mock.patch(
            "apps.notifications.services.wati_service.requests.post",
            side_effect=Exception("network down"),
        ):
            AttendanceRecord.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                check_in_time=timezone.now(),
            )
        self.assertTrue(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.CHECK_IN,
                status=NotificationLog.Status.FAILED,
            ).exists()
        )


class NotificationAPITests(APITestCase):
    """Integration tests for notification endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, customer, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.user = User.objects.create_user(
            email="api-cust@local.test",
            password="F1tNati0n!",
            first_name="API",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="API Customer",
            email="api-cust@local.test",
            phone="+919111111111",
        )

    def test_list_logs(self) -> None:
        """Owners can list notification logs."""
        NotificationLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type=NotificationLog.NotificationType.CHECK_IN,
            status=NotificationLog.Status.SENT,
            content="Hi API Customer",
        )
        response = self.client.get("/api/v1/notifications/logs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["notification_type"], "check_in")

    def test_filter_logs_by_status(self) -> None:
        """Logs can be filtered by status."""
        NotificationLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type=NotificationLog.NotificationType.CHECK_IN,
            status=NotificationLog.Status.SENT,
        )
        NotificationLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type=NotificationLog.NotificationType.CHECK_IN,
            status=NotificationLog.Status.FAILED,
        )
        response = self.client.get("/api/v1/notifications/logs/?status=failed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], "failed")

    def test_get_settings(self) -> None:
        """GET settings returns the Wati config (masked key)."""
        response = self.client.get("/api/v1/notifications/settings/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_wati_enabled", response.data)
        self.assertIn("wati_api_key_configured", response.data)
        self.assertNotIn("wati_api_key", response.data)

    def test_patch_settings(self) -> None:
        """PATCH settings updates the tenant Wati config."""
        response = self.client.patch(
            "/api/v1/notifications/settings/",
            {
                "wati_api_key": "new_wati_key",
                "wati_endpoint": "https://api.wati.io/api/v1/sendSessionMessage",
                "is_wati_enabled": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.is_wati_enabled)
        self.assertEqual(self.tenant.wati_api_key, "new_wati_key")
        self.assertTrue(response.data["wati_api_key_configured"])

    def test_test_notification(self) -> None:
        """POST test sends a test message and reports the outcome."""
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "wati_secret_key"
        self.tenant.save()
        with mock.patch("apps.notifications.services.wati_service.requests.post") as m:
            m.return_value.json.return_value = {"messageId": "test_msg"}
            m.return_value.raise_for_status = mock.Mock()
            response = self.client.post(
                "/api/v1/notifications/test/",
                {"to": "+919111111111", "message": "Hello from FitNation"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "sent")

    def test_test_notification_disabled(self) -> None:
        """POST test with Wati disabled returns skipped status."""
        response = self.client.post(
            "/api/v1/notifications/test/",
            {"to": "+919111111111"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "skipped")

    def test_log_tenant_isolation(self) -> None:
        """Another tenant's logs are not accessible."""
        other = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_log = NotificationLog.objects.create(
            tenant=other,
            notification_type=NotificationLog.NotificationType.CHECK_IN,
        )
        response = self.client.get(f"/api/v1/notifications/logs/{other_log.id}/")
        self.assertEqual(response.status_code, 404)


class TenantWatiFieldTests(TestCase):
    """Tests for the Wati fields on the Tenant model."""

    def test_wati_api_key_encrypted_at_rest(self) -> None:
        """The Wati API key is encrypted at rest."""
        from django.db import connection

        tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        tenant.wati_api_key = "super_secret_key"
        tenant.save()

        with connection.cursor() as cursor:
            cursor.execute("SELECT wati_api_key FROM tenants WHERE id = %s", [tenant.id])
            row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], "super_secret_key")
        self.assertTrue(str(row[0]).startswith("gAAAA"))

        tenant.refresh_from_db()
        self.assertEqual(tenant.wati_api_key, "super_secret_key")
