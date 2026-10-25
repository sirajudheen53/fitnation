"""Tests for the payments app."""

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.notifications.models import NotificationLog
from apps.notifications.services.router import WhatsAppAttempt
from apps.payments import razorpay_service
from apps.payments.models import Invoice, Payment, PaymentRefund, RazorpayConfig
from apps.payments.services import send_payment_link
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


class PaymentModelTests(TestCase):
    """Unit tests for the Payment model."""

    def setUp(self) -> None:
        """Create a tenant, user, and customer for model tests."""
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
        )

    def test_payment_requires_tenant(self) -> None:
        """Saving a payment without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            Payment.objects.create(
                customer=self.customer,
                amount="1500.00",
                payment_method=Payment.PaymentMethod.CASH,
            )

    def test_payment_default_status_pending(self) -> None:
        """A new payment defaults to pending status."""
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
        )
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_payment_kind_defaults_to_membership(self) -> None:
        """A payment without an explicit kind defaults to membership."""
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
        )
        self.assertEqual(payment.kind, Payment.Kind.MEMBERSHIP)

    def test_payment_tenant_isolation(self) -> None:
        """Payments are scoped to their tenant."""
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(
            Payment.objects.for_tenant(self.tenant).first().id,
            payment.id,
        )
        self.assertEqual(Payment.objects.for_tenant(other_tenant).count(), 0)


class InvoiceModelTests(TestCase):
    """Unit tests for the Invoice model."""

    def setUp(self) -> None:
        """Create a tenant, user, customer, and payment for model tests."""
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
        )
        self.payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
        )

    def test_invoice_number_auto_generated(self) -> None:
        """An invoice number is auto-generated on save."""
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            payment=self.payment,
            subtotal="1500.00",
            tax="0.00",
            total="1500.00",
        )
        self.assertTrue(invoice.invoice_number.startswith("INV-"))
        self.assertEqual(len(invoice.invoice_number.split("-")), 3)

    def test_invoice_number_unique(self) -> None:
        """Invoice numbers are globally unique."""
        Invoice.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            payment=self.payment,
            invoice_number="INV-20260101-0001",
            subtotal="1500.00",
            tax="0.00",
            total="1500.00",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Invoice.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                payment=self.payment,
                invoice_number="INV-20260101-0001",
                subtotal="1500.00",
                tax="0.00",
                total="1500.00",
            )

    def test_invoice_tenant_isolation(self) -> None:
        """Invoices are scoped to their tenant."""
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            payment=self.payment,
            subtotal="1500.00",
            tax="0.00",
            total="1500.00",
        )
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(
            Invoice.objects.for_tenant(self.tenant).first().id,
            invoice.id,
        )
        self.assertEqual(Invoice.objects.for_tenant(other_tenant).count(), 0)


class PaymentAPITests(APITestCase):
    """Integration tests for payment endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, plan, customer, membership, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly",
            price="1500.00",
            duration_days=30,
        )
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
        )
        self.membership = Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
        )

    def test_record_payment(self) -> None:
        """Owners can record a payment."""
        response = self.client.post(
            "/api/v1/payments/",
            {
                "customer_id": self.customer.id,
                "membership_id": self.membership.id,
                "amount": "1500.00",
                "method": "cash",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "completed")
        self.assertIsNotNone(response.data["payment_date"])
        self.assertEqual(response.data["customer_name"], "API Customer")

    def test_record_pending_payment_has_no_paid_at(self) -> None:
        """A pending payment has no paid_at timestamp."""
        response = self.client.post(
            "/api/v1/payments/",
            {
                "customer_id": self.customer.id,
                "amount": "1500.00",
                "method": "cash",
                "status": "pending",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        # pending payments carry no paid_at; payment_date falls back to created_at
        self.assertIsNotNone(response.data["payment_date"])
        self.assertNotIn("paid_at", response.data)

    def test_list_payments(self) -> None:
        """Owners can list payments."""
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
        )
        response = self.client.get("/api/v1/payments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_payment_list_contract_shape(self) -> None:
        """List rows match the frontend Payment contract (FBOS-005)."""
        response = self.client.post(
            "/api/v1/payments/",
            {
                "customer_id": self.customer.id,
                "amount": "1500.00",
                "method": "bank_transfer",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        list_response = self.client.get("/api/v1/payments/")
        self.assertEqual(list_response.status_code, 200)
        row = list_response.data["results"][0]
        for key in (
            "id",
            "customer_id",
            "customer_name",
            "membership_id",
            "invoice_id",
            "amount",
            "method",
            "status",
            "payment_date",
            "notes",
            "created_at",
            "updated_at",
        ):
            self.assertIn(key, row)
        self.assertEqual(row["customer_id"], self.customer.id)
        self.assertEqual(row["customer_name"], "API Customer")
        self.assertEqual(row["method"], "bank_transfer")
        self.assertIsNotNone(row["payment_date"])  # created_at fallback for rows without paid_at
        self.assertIn("invoice_id", row)

    def test_filter_payments_by_status(self) -> None:
        """Payments can be filtered by status."""
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
        )
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="500.00",
            payment_method=Payment.PaymentMethod.UPI,
            status=Payment.Status.PENDING,
        )
        response = self.client.get("/api/v1/payments/?status=completed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], "completed")

    def test_filter_payments_by_customer(self) -> None:
        """Payments can be filtered by customer."""
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
        )
        response = self.client.get(f"/api/v1/payments/?customer={self.customer.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_payments_by_date_range(self) -> None:
        """Payments can be filtered by paid_at date range."""
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
            paid_at=timezone.now(),
        )
        start = quote((timezone.now() - timedelta(days=1)).isoformat())
        end = quote((timezone.now() + timedelta(days=1)).isoformat())
        response = self.client.get(f"/api/v1/payments/?paid_at__gte={start}&paid_at__lte={end}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_payments_by_kind(self) -> None:
        """Payments can be filtered by kind (?kind=admission)."""
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
        )
        Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="500.00",
            payment_method=Payment.PaymentMethod.UPI,
            status=Payment.Status.COMPLETED,
            kind=Payment.Kind.ADMISSION,
        )
        response = self.client.get("/api/v1/payments/?kind=admission")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["kind"], "admission")

    def test_record_payment_defaults_to_membership_kind(self) -> None:
        """Omitting kind records a membership payment (existing clients unaffected)."""
        response = self.client.post(
            "/api/v1/payments/",
            {
                "customer_id": self.customer.id,
                "amount": "1500.00",
                "method": "cash",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["kind"], "membership")

    def test_record_admission_payment(self) -> None:
        """kind=admission records an admission fee with no membership link."""
        response = self.client.post(
            "/api/v1/payments/",
            {
                "customer_id": self.customer.id,
                "amount": "500.00",
                "method": "upi",
                "status": "completed",
                "kind": "admission",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["kind"], "admission")
        self.assertIsNone(response.data["membership_id"])
        self.assertIsNotNone(response.data["payment_date"])  # paid now → paid_at set

    def test_generate_invoice(self) -> None:
        """The generate action creates an invoice from a payment."""
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
        )
        response = self.client.post(
            "/api/v1/invoices/generate/",
            {"payment": payment.id, "tax_rate": 18},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(float(response.data["subtotal"]), 1500.00)
        self.assertEqual(float(response.data["tax"]), 270.00)
        self.assertEqual(float(response.data["total"]), 1770.00)
        self.assertTrue(response.data["invoice_number"].startswith("INV-"))

    def test_generate_invoice_with_fixed_tax(self) -> None:
        """The generate action accepts a fixed tax amount."""
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
        )
        response = self.client.post(
            "/api/v1/invoices/generate/",
            {"payment": payment.id, "tax": 100},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(float(response.data["tax"]), 100.00)
        self.assertEqual(float(response.data["total"]), 1600.00)

    def test_list_invoices(self) -> None:
        """Owners can list invoices."""
        Invoice.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            subtotal="1500.00",
            tax="0.00",
            total="1500.00",
        )
        response = self.client.get("/api/v1/invoices/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_payment_tenant_isolation(self) -> None:
        """A payment from another tenant is not accessible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        create_owner_user(
            tenant=other_tenant,
            email="other-owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        other_user = User.objects.create_user(
            email="other-cust@local.test",
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
            email="other-cust@local.test",
        )
        other_payment = Payment.objects.create(
            tenant=other_tenant,
            customer=other_customer,
            amount="1000.00",
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
        )
        response = self.client.get(f"/api/v1/payments/{other_payment.id}/")
        self.assertEqual(response.status_code, 404)


class RazorpayConfigModelTests(TestCase):
    """Unit tests for the RazorpayConfig model."""

    def setUp(self) -> None:
        """Create a tenant and an inactive Razorpay config."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.config = RazorpayConfig.objects.create(
            tenant=self.tenant,
            api_key="rzp_test_key",
            api_secret="rzp_test_secret",
            webhook_secret="whsec_test",
            is_active=True,
        )

    def test_requires_tenant(self) -> None:
        """Saving a config without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            RazorpayConfig.objects.create(api_key="x", api_secret="y")

    def test_secrets_encrypted_at_rest(self) -> None:
        """API secrets are not stored as plaintext."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT api_key FROM razorpay_configs WHERE id = %s", [self.config.id])
            row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], "rzp_test_key")
        self.assertTrue(str(row[0]).startswith("gAAAA"))

    def test_decrypts_on_read(self) -> None:
        """The API key decrypts to its plaintext value."""
        fresh = RazorpayConfig.objects.get(id=self.config.id)
        self.assertEqual(fresh.api_key, "rzp_test_key")
        self.assertEqual(fresh.api_secret, "rzp_test_secret")
        self.assertEqual(fresh.webhook_secret, "whsec_test")

    def test_tenant_isolation(self) -> None:
        """Configs are scoped to their tenant."""
        other = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(RazorpayConfig.objects.for_tenant(other).count(), 0)
        self.assertEqual(RazorpayConfig.objects.for_tenant(self.tenant).first().id, self.config.id)


class PaymentLinkButtonSuffixTests(TestCase):
    """The CTA URL-button variable extraction for the Gupshup payment send
    (issue #85): strip the fixed Razorpay short_url prefix, never garble."""

    def test_short_url_suffix_after_fixed_prefix(self) -> None:
        """``https://rzp.io/i/<token>`` → ``<token>`` (the button URL variable)."""
        self.assertEqual(razorpay_service.payment_link_button_suffix("https://rzp.io/i/nxrHnLJ"), "nxrHnLJ")
        self.assertEqual(
            razorpay_service.payment_link_button_suffix("https://rzp.io/i/PlNKsh0RtQKxWn"),
            "PlNKsh0RtQKxWn",
        )

    def test_non_matching_link_passes_through_with_a_warning(self) -> None:
        """A link off the fixed prefix passes whole (loudly warned) — the
        template prefix needs re-checking, the audit copy still has the URL."""
        with self.assertLogs("apps.payments.razorpay_service", level="WARNING"):
            self.assertEqual(
                razorpay_service.payment_link_button_suffix("https://rzp.io/l/oddLink"),
                "https://rzp.io/l/oddLink",
            )

    def test_prefix_match_survives_url_casing_drift(self) -> None:
        """Scheme/host casing drift must not turn a good link into garbage."""
        self.assertEqual(razorpay_service.payment_link_button_suffix("HTTPS://RZP.IO/i/Token9x"), "Token9x")


class RazorpayServiceTests(TestCase):
    """Unit tests for the Razorpay service layer."""

    def setUp(self) -> None:
        """Create tenant, active config, customer, and a payment."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.config = RazorpayConfig.objects.create(
            tenant=self.tenant,
            api_key="rzp_test_key",
            api_secret="rzp_test_secret",
            webhook_secret="whsec_test",
            is_active=True,
        )
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
        )
        self.payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            razorpay_order_id="order_test123",
            razorpay_payment_id="pay_test456",
            status=Payment.Status.COMPLETED,
        )

    def test_create_order_calls_sdk(self) -> None:
        """create_order posts an amount (in paise) to the SDK and returns the id."""
        mock_client = mock.Mock()
        mock_client.order.create.return_value = {
            "id": "order_new123",
            "amount": 150000,
            "currency": "INR",
        }
        order = razorpay_service.create_order(self.tenant, Decimal("1500.00"), receipt="p1", client=mock_client)
        self.assertEqual(order["id"], "order_new123")
        mock_client.order.create.assert_called_once()
        data = mock_client.order.create.call_args[1]["data"]
        self.assertEqual(data["amount"], 150000)
        self.assertEqual(data["currency"], "INR")

    def test_create_order_inactive_raises(self) -> None:
        """create_order raises when the tenant has no active config."""
        self.config.is_active = False
        self.config.save()
        with self.assertRaises(razorpay_service.RazorpayError):
            razorpay_service.create_order(self.tenant, Decimal("100.00"))

    def test_create_order_sdk_error_raises(self) -> None:
        """SDK errors are normalized to RazorpayError."""
        mock_client = mock.Mock()
        mock_client.order.create.side_effect = Exception("boom")
        with self.assertRaises(razorpay_service.RazorpayError):
            razorpay_service.create_order(self.tenant, Decimal("100.00"), client=mock_client)

    def test_verify_signature_valid(self) -> None:
        """A correct signature verifies True."""
        order_id = "order_test123"
        payment_id = "pay_test456"
        message = f"{order_id}|{payment_id}".encode()
        signature = hmac.new(b"whsec_test", message, hashlib.sha256).hexdigest()
        self.assertTrue(razorpay_service.verify_signature(order_id, payment_id, signature, self.tenant))

    def test_verify_signature_invalid(self) -> None:
        """An incorrect signature verifies False."""
        self.assertFalse(razorpay_service.verify_signature("order_test123", "pay_test456", "deadbeef", self.tenant))

    def test_refund_payment_success(self) -> None:
        """A successful refund marks the refund processed and payment refunded."""
        mock_client = mock.Mock()
        mock_client.payment.refund.return_value = {"id": "refund_abc123"}
        refund = razorpay_service.refund_payment(self.payment, reason="cancelled", client=mock_client)
        self.assertEqual(refund.status, PaymentRefund.Status.PROCESSED)
        self.assertEqual(refund.refund_id, "refund_abc123")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.REFUNDED)

    def test_refund_payment_no_payment_id_raises(self) -> None:
        """A payment without a Razorpay payment id cannot be refunded."""
        self.payment.razorpay_payment_id = ""
        self.payment.save()
        with self.assertRaises(razorpay_service.RazorpayError):
            razorpay_service.refund_payment(self.payment)

    def test_refund_payment_failure_marks_failed(self) -> None:
        """A failed refund is logged and the error is raised."""
        mock_client = mock.Mock()
        mock_client.payment.refund.side_effect = Exception("insufficient balance")
        with self.assertRaises(razorpay_service.RazorpayError):
            razorpay_service.refund_payment(self.payment, client=mock_client)
        refund = PaymentRefund.objects.get(payment=self.payment)
        self.assertEqual(refund.status, PaymentRefund.Status.FAILED)
        self.assertIn("insufficient balance", refund.error_message)


class RazorpayWebhookTests(TestCase):
    """Tests for the Razorpay webhook receiver."""

    def setUp(self) -> None:
        """Create tenant, config, customer, and a pending order payment."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.config = RazorpayConfig.objects.create(
            tenant=self.tenant,
            api_key="rzp_test_key",
            api_secret="rzp_test_secret",
            webhook_secret="whsec_test",
            is_active=True,
        )
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
        )
        self.payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            razorpay_order_id="order_webhook1",
            status=Payment.Status.PENDING,
        )

    def _sign(self, payload: bytes) -> str:
        return hmac.new(b"whsec_test", payload, hashlib.sha256).hexdigest()

    def _post(self, event: str, entity: dict, refund: dict | None = None) -> None:
        payload_obj = {"payment": {"entity": entity}}
        if refund:
            payload_obj["refund"] = {"entity": refund}
        data = {"event": event, "payload": payload_obj}
        body = json.dumps(data).encode()
        return self.client.post(
            "/api/v1/payments/razorpay/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_RAZORPAY_TENANT=str(self.tenant.id),
            HTTP_X_RAZORPAY_SIGNATURE=self._sign(body),
        )

    def test_payment_captured_updates_status_and_generates_invoice(self) -> None:
        """A captured payment is marked paid and an invoice is generated."""
        response = self._post(
            "payment.captured",
            {"order_id": "order_webhook1", "id": "pay_webhook1"},
        )
        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.COMPLETED)
        self.assertEqual(self.payment.razorpay_payment_id, "pay_webhook1")
        self.assertTrue(Invoice.objects.filter(payment=self.payment).exists())

    def test_payment_failed_marks_failed(self) -> None:
        """A failed payment is marked failed with a reason."""
        response = self._post(
            "payment.failed",
            {
                "order_id": "order_webhook1",
                "id": "pay_webhook1",
                "error_description": "Payment declined",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.assertIn("Payment declined", self.payment.notes)

    def test_invalid_signature_rejected(self) -> None:
        """A bad signature returns 400 and does not change state."""
        body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {}}}}).encode()
        response = self.client.post(
            "/api/v1/payments/razorpay/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_RAZORPAY_TENANT=str(self.tenant.id),
            HTTP_X_RAZORPAY_SIGNATURE="bad-signature",
        )
        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)

    def test_unknown_tenant_returns_404(self) -> None:
        """A webhook without a resolvable tenant returns 404."""
        body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
        response = self.client.post(
            "/api/v1/payments/razorpay/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_RAZORPAY_TENANT="999999",
            HTTP_X_RAZORPAY_SIGNATURE="sig",
        )
        self.assertEqual(response.status_code, 404)

    def test_refund_processed_updates_refund_and_payment(self) -> None:
        """A processed refund marks the refund and payment as refunded."""
        refund = PaymentRefund.objects.create(
            tenant=self.tenant,
            payment=self.payment,
            amount="1500.00",
            status=PaymentRefund.Status.PENDING,
            refund_id="refund_webhook1",
        )
        response = self._post("refund.processed", {}, refund={"id": "refund_webhook1"})
        self.assertEqual(response.status_code, 200)
        refund.refresh_from_db()
        self.assertEqual(refund.status, PaymentRefund.Status.PROCESSED)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.REFUNDED)


class RazorpayAPITests(APITestCase):
    """Integration tests for Razorpay API endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, config, customer, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.config = RazorpayConfig.objects.create(
            tenant=self.tenant,
            api_key="rzp_test_key",
            api_secret="rzp_test_secret",
            webhook_secret="whsec_test",
            is_active=True,
        )
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
        )

    def test_create_order_endpoint(self) -> None:
        """POST create-order creates a payment and Razorpay order."""
        with mock.patch(
            "apps.payments.razorpay_service.create_order",
            return_value={"id": "order_api1", "amount": 150000, "currency": "INR"},
        ):
            response = self.client.post(
                "/api/v1/payments/razorpay/create-order/",
                {"customer": self.customer.id, "amount": "1500.00"},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["razorpay_order_id"], "order_api1")
        payment = Payment.objects.get(tenant=self.tenant, customer=self.customer)
        self.assertEqual(payment.razorpay_order_id, "order_api1")
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_create_order_config_error(self) -> None:
        """A config error returns 400 and marks the payment failed."""
        self.config.is_active = False
        self.config.save()
        response = self.client.post(
            "/api/v1/payments/razorpay/create-order/",
            {"customer": self.customer.id, "amount": "1500.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        payment = Payment.objects.get(tenant=self.tenant, customer=self.customer)
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_verify_endpoint_success(self) -> None:
        """POST verify validates the signature and marks the payment paid."""
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            razorpay_order_id="order_verify1",
            status=Payment.Status.PENDING,
        )
        message = b"order_verify1|pay_verify1"
        signature = hmac.new(b"whsec_test", message, hashlib.sha256).hexdigest()
        response = self.client.post(
            "/api/v1/payments/razorpay/verify/",
            {
                "razorpay_order_id": "order_verify1",
                "razorpay_payment_id": "pay_verify1",
                "razorpay_signature": signature,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.COMPLETED)
        self.assertTrue(Invoice.objects.filter(payment=payment).exists())

    def test_verify_endpoint_invalid_signature(self) -> None:
        """An invalid signature marks the payment failed and returns 400."""
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            razorpay_order_id="order_verify2",
            status=Payment.Status.PENDING,
        )
        response = self.client.post(
            "/api/v1/payments/razorpay/verify/",
            {
                "razorpay_order_id": "order_verify2",
                "razorpay_payment_id": "pay_verify2",
                "razorpay_signature": "tampered",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_config_get(self) -> None:
        """GET config returns public key and active flag."""
        response = self.client.get("/api/v1/payments/razorpay/config/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_active"])
        self.assertEqual(response.data["api_key"], "rzp_test_key")

    def test_config_patch(self) -> None:
        """PATCH config updates the config."""
        response = self.client.patch(
            "/api/v1/payments/razorpay/config/",
            {"api_key": "rzp_new_key", "is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.api_key, "rzp_new_key")

    def test_refund_endpoint(self) -> None:
        """POST refunds initiates a refund for a Razorpay payment."""
        payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            razorpay_order_id="order_refund1",
            razorpay_payment_id="pay_refund1",
            status=Payment.Status.COMPLETED,
        )
        with mock.patch("apps.payments.razorpay_service.refund_payment") as m:
            m.return_value = PaymentRefund.objects.create(
                tenant=self.tenant,
                payment=payment,
                amount="1500.00",
                status=PaymentRefund.Status.PROCESSED,
                refund_id="refund_api1",
            )
            response = self.client.post(
                "/api/v1/refunds/",
                {"payment": payment.id, "reason": "cancelled"},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["refund_id"], "refund_api1")

    def test_razorpay_tenant_isolation(self) -> None:
        """Another tenant's payment cannot be accessed via refunds."""
        other = provision_tenant(name="Other Gym", contact_email="other@local.test")
        create_owner_user(
            tenant=other,
            email="other-owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        other_user = User.objects.create_user(
            email="other-cust@local.test",
            password="F1tNati0n!",
            first_name="Other",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=other,
        )
        other_customer = Customer.objects.create(
            tenant=other,
            user=other_user,
            name="Other Customer",
            email="other-cust@local.test",
        )
        other_payment = Payment.objects.create(
            tenant=other,
            customer=other_customer,
            amount="1000.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            status=Payment.Status.COMPLETED,
        )
        response = self.client.post(
            "/api/v1/refunds/",
            {"payment": other_payment.id},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class RevenueSummaryAPITests(APITestCase):
    """Revenue summary splits membership and admission revenue (msg 2438)."""

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
            email="rev-cust@local.test",
            password="F1tNati0n!",
            first_name="Rev",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Rev Customer",
            email="rev-cust@local.test",
        )

    def _paid(self, amount: str, kind: str, paid_at, status: str = Payment.Status.COMPLETED) -> Payment:
        """Create a payment in the fixture tenant."""
        return Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount=amount,
            payment_method=Payment.PaymentMethod.CASH,
            status=status,
            kind=kind,
            paid_at=paid_at,
        )

    def test_membership_and_admission_reported_separately(self) -> None:
        """Membership metrics exclude admission fees; admission has its own split."""
        now = timezone.now()
        long_ago = now - timedelta(days=40)  # outside the today/week/month windows
        self._paid("1500.00", Payment.Kind.MEMBERSHIP, now)  # membership, all windows
        self._paid("250.00", Payment.Kind.MEMBERSHIP, long_ago)  # membership, no window
        self._paid("500.00", Payment.Kind.ADMISSION, now)  # admission, all windows
        self._paid("900.00", Payment.Kind.ADMISSION, long_ago)  # admission, no window
        self._paid("700.00", Payment.Kind.ADMISSION, None, status=Payment.Status.PENDING)  # excluded

        response = self.client.get("/api/v1/payments/revenue-summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["today"], 1500.0)  # admission fee did not pollute
        self.assertEqual(response.data["this_week"], 1500.0)
        self.assertEqual(response.data["this_month"], 1500.0)
        self.assertEqual(
            response.data["admission"],
            {"today": 500.0, "this_week": 500.0, "this_month": 500.0},
        )

    def test_empty_tenant_zero_filled(self) -> None:
        """A tenant with no payments gets zeroed membership and admission splits."""
        response = self.client.get("/api/v1/payments/revenue-summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["today"], 0.0)
        self.assertEqual(response.data["this_week"], 0.0)
        self.assertEqual(response.data["this_month"], 0.0)
        self.assertEqual(
            response.data["admission"],
            {"today": 0.0, "this_week": 0.0, "this_month": 0.0},
        )


class PaymentLinkServiceTests(TestCase):
    """Unit tests for Razorpay payment-link creation (issue #72, mocked SDK)."""

    def setUp(self) -> None:
        """Create tenant, active config, customer, and a pending payment."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.config = RazorpayConfig.objects.create(
            tenant=self.tenant,
            api_key="rzp_test_key",
            api_secret="rzp_test_secret",
            webhook_secret="whsec_test",
            is_active=True,
        )
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
            phone="+919876543210",
        )
        self.payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            status=Payment.Status.PENDING,
        )

    def test_create_payment_link_calls_sdk(self) -> None:
        """create_payment_link posts a paise amount with reference_id and customer."""
        mock_client = mock.Mock()
        mock_client.payment_link.create.return_value = {
            "id": "plink_api1",
            "short_url": "https://rzp.io/i/plink_api1",
        }
        link = razorpay_service.create_payment_link(self.tenant, self.payment, client=mock_client)
        self.assertEqual(link["id"], "plink_api1")
        mock_client.payment_link.create.assert_called_once()
        data = mock_client.payment_link.create.call_args[1]["data"]
        self.assertEqual(data["amount"], 150000)
        self.assertEqual(data["currency"], "INR")
        self.assertEqual(data["reference_id"], str(self.payment.id))
        self.assertEqual(data["customer"]["name"], "Cust Customer")
        self.assertEqual(data["customer"]["contact"], "919876543210")
        self.assertEqual(data["customer"]["email"], "cust@local.test")
        self.assertEqual(data["notes"]["payment_id"], str(self.payment.id))

    def test_create_payment_link_skips_synthetic_email(self) -> None:
        """Phone-keyed OTP mailboxes are never attached to the link customer."""
        self.customer.email = "9876543210.x@fitnation.local"
        self.customer.save()
        mock_client = mock.Mock()
        mock_client.payment_link.create.return_value = {"id": "plink_api2"}
        razorpay_service.create_payment_link(self.tenant, self.payment, client=mock_client)
        data = mock_client.payment_link.create.call_args[1]["data"]
        self.assertNotIn("email", data["customer"])
        self.assertIn("contact", data["customer"])

    def test_create_payment_link_inactive_raises(self) -> None:
        """create_payment_link raises when the tenant has no active config."""
        self.config.is_active = False
        self.config.save()
        with self.assertRaises(razorpay_service.RazorpayError):
            razorpay_service.create_payment_link(self.tenant, self.payment)

    def test_create_payment_link_sdk_error_raises(self) -> None:
        """SDK errors are normalized to RazorpayError."""
        mock_client = mock.Mock()
        mock_client.payment_link.create.side_effect = Exception("boom")
        with self.assertRaises(razorpay_service.RazorpayError):
            razorpay_service.create_payment_link(self.tenant, self.payment, client=mock_client)


class SendPaymentLinkServiceTests(TestCase):
    """Tests for the payment-link send orchestration (channels, cooldown, audit)."""

    def setUp(self) -> None:
        """Create tenant with Gupshup, Razorpay config, customer, pending payment."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.tenant.is_gupshup_enabled = True
        self.tenant.gupshup_api_key = "gups_key"
        self.tenant.gupshup_source = "919999000000"
        self.tenant.gupshup_app_name = "hash-fit"
        self.tenant.save()
        RazorpayConfig.objects.create(
            tenant=self.tenant,
            api_key="rzp_test_key",
            api_secret="rzp_test_secret",
            webhook_secret="whsec_test",
            is_active=True,
        )
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
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
            phone="+919876543210",
        )
        self.payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            status=Payment.Status.PENDING,
        )

    def test_sent_over_gupshup_with_audited_template_send(self) -> None:
        """A configured Gupshup tenant delivers the template and audits it."""
        with (
            mock.patch(
                "apps.payments.razorpay_service.create_payment_link",
                return_value={"id": "plink_s1", "short_url": "https://rzp.io/i/s1"},
            ),
            mock.patch(
                "apps.payments.services.send_whatsapp_template",
                return_value=WhatsAppAttempt(provider="gupshup", sent=True, attempted=True),
            ) as send_template,
        ):
            result = send_payment_link(self.tenant, self.payment, actor=self.owner)
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.channel, "whatsapp")
        self.assertEqual(result.provider, "gupshup")
        self.assertEqual(result.payment_link_url, "https://rzp.io/i/s1")

        # Template args: approved slug, normalized msisdn, positional params.
        # Per #85 the two BSP shapes differ: WATI's params carry the whole
        # link; Gupshup's carry the 3 body variables + the short_url suffix
        # for the "Pay Now" CTA URL button pinned to https://rzp.io/i/{{1}}.
        args = send_template.call_args
        self.assertEqual(args[0][1], "fitnation_payment_link")
        self.assertEqual(args[0][2], "919876543210")
        self.assertEqual(args[0][3], ["Cust Customer", "1500.00", "Iron Peak", "https://rzp.io/i/s1"])
        self.assertEqual(args[1]["gupshup_params"], ["Cust Customer", "1500.00", "Iron Peak", "s1"])

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.razorpay_payment_link_id, "plink_s1")
        self.assertIsNotNone(self.payment.payment_link_sent_at)

        log = NotificationLog.objects.get(notification_type=NotificationLog.NotificationType.PAYMENT_LINK)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "whatsapp")
        self.assertEqual(log.provider, "gupshup")
        self.assertEqual(log.actor, self.owner)
        self.assertIn("Cust Customer", log.content)
        self.assertIn("https://rzp.io/i/s1", log.content)

    def test_resend_within_cooldown_is_blocked(self) -> None:
        """A second send inside the cooldown returns already_sent, no new calls."""
        with (
            mock.patch(
                "apps.payments.razorpay_service.create_payment_link",
                return_value={"id": "plink_s2", "short_url": "https://rzp.io/i/s2"},
            ) as create_link,
            mock.patch(
                "apps.payments.services.send_whatsapp_template",
                return_value=WhatsAppAttempt(provider="gupshup", sent=True, attempted=True),
            ) as send_template,
        ):
            first = send_payment_link(self.tenant, self.payment)
            self.assertEqual(first.status, "sent")
            second = send_payment_link(self.tenant, self.payment)
        self.assertEqual(second.status, "already_sent")
        self.assertIsNotNone(second.resend_allowed_after)
        create_link.assert_called_once()
        send_template.assert_called_once()
        self.assertEqual(
            NotificationLog.objects.filter(
                notification_type=NotificationLog.NotificationType.PAYMENT_LINK,
                status=NotificationLog.Status.SENT,
            ).count(),
            1,
        )

    def test_cooldown_disabled_allows_immediate_resend(self) -> None:
        """PAYMENT_LINK_RESEND_COOLDOWN_MINUTES=0 removes the guard entirely."""
        with (
            mock.patch(
                "apps.payments.razorpay_service.create_payment_link",
                return_value={"id": "plink_s3", "short_url": "https://rzp.io/i/s3"},
            ),
            mock.patch(
                "apps.payments.services.send_whatsapp_template",
                return_value=WhatsAppAttempt(provider="gupshup", sent=True, attempted=True),
            ),
            override_settings(PAYMENT_LINK_RESEND_COOLDOWN_MINUTES=0),
        ):
            first = send_payment_link(self.tenant, self.payment)
            second = send_payment_link(self.tenant, self.payment)
        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "sent")

    def test_only_pending_payments_receive_links(self) -> None:
        """A completed payment short-circuits before any call or audit row."""
        self.payment.status = Payment.Status.COMPLETED
        self.payment.save()
        with mock.patch("apps.payments.razorpay_service.create_payment_link") as create_link:
            result = send_payment_link(self.tenant, self.payment)
        self.assertEqual(result.status, "not_pending")
        create_link.assert_not_called()
        self.assertFalse(
            NotificationLog.objects.filter(notification_type=NotificationLog.NotificationType.PAYMENT_LINK).exists()
        )

    def test_email_only_customer_gets_the_link_by_email(self) -> None:
        """No phone but a real mailbox → the email leg carries the link."""
        self.customer.phone = ""
        self.customer.save()
        with (
            mock.patch(
                "apps.payments.razorpay_service.create_payment_link",
                return_value={"id": "plink_s4", "short_url": "https://rzp.io/i/s4"},
            ),
            override_settings(SENDGRID_API_KEY="sg_test"),
        ):
            result = send_payment_link(self.tenant, self.payment)
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.channel, "email")
        self.assertEqual(result.provider, "sendgrid")
        log = NotificationLog.objects.get(notification_type=NotificationLog.NotificationType.PAYMENT_LINK)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "email")
        self.payment.refresh_from_db()
        self.assertIsNotNone(self.payment.payment_link_sent_at)

    def test_no_channels_configured_fails_with_audit(self) -> None:
        """No WhatsApp, SMS, or emailable address → failed, link kept for manual share."""
        self.customer.email = "9876543210.x@fitnation.local"
        self.customer.save()
        self.tenant.is_gupshup_enabled = False
        self.tenant.save()
        with mock.patch(
            "apps.payments.razorpay_service.create_payment_link",
            return_value={"id": "plink_s5", "short_url": "https://rzp.io/i/s5"},
        ):
            result = send_payment_link(self.tenant, self.payment)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.payment_link_url, "https://rzp.io/i/s5")
        log = NotificationLog.objects.get(notification_type=NotificationLog.NotificationType.PAYMENT_LINK)
        self.assertEqual(log.status, NotificationLog.Status.FAILED)

    def test_link_creation_failure_is_audited(self) -> None:
        """Razorpay errors surface as failed with the error on the audit row."""
        with mock.patch(
            "apps.payments.razorpay_service.create_payment_link",
            side_effect=razorpay_service.RazorpayError("Razorpay is not enabled for this tenant"),
        ):
            result = send_payment_link(self.tenant, self.payment)
        self.assertEqual(result.status, "failed")
        self.assertIn("not enabled", result.reason)
        log = NotificationLog.objects.get(notification_type=NotificationLog.NotificationType.PAYMENT_LINK)
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn("not enabled", log.error_message)


class SendPaymentLinkAPITests(APITestCase):
    """Integration tests for POST /payments/{id}/send-link/ (issue #72)."""

    def setUp(self) -> None:
        """Create tenant, owner, config, customer, and a pending payment."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.tenant.is_gupshup_enabled = True
        self.tenant.gupshup_api_key = "gups_key"
        self.tenant.gupshup_source = "919999000000"
        self.tenant.gupshup_app_name = "hash-fit"
        self.tenant.save()
        RazorpayConfig.objects.create(
            tenant=self.tenant,
            api_key="rzp_test_key",
            api_secret="rzp_test_secret",
            webhook_secret="whsec_test",
            is_active=True,
        )
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
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
            email="9876543210.x@fitnation.local",
            phone="+919876543210",
        )
        self.payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            status=Payment.Status.PENDING,
        )

    def _send(self, payment: Payment) -> object:
        return self.client.post(f"/api/v1/payments/{payment.id}/send-link/", format="json")

    def test_send_link_endpoint_success_and_audit(self) -> None:
        """Owners send a link; the outcome, audit row, and payment are returned."""
        with (
            mock.patch(
                "apps.payments.razorpay_service.create_payment_link",
                return_value={"id": "plink_e1", "short_url": "https://rzp.io/i/e1"},
            ),
            mock.patch(
                "apps.payments.services.send_whatsapp_template",
                return_value=WhatsAppAttempt(provider="gupshup", sent=True, attempted=True),
            ),
        ):
            response = self._send(self.payment)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "sent")
        self.assertEqual(response.data["channel"], "whatsapp")
        self.assertEqual(response.data["provider"], "gupshup")
        self.assertEqual(response.data["payment_link_url"], "https://rzp.io/i/e1")
        self.assertIsNotNone(response.data["payment"])
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.razorpay_payment_link_id, "plink_e1")
        log = NotificationLog.objects.get(notification_type=NotificationLog.NotificationType.PAYMENT_LINK)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.actor, self.owner)

    def test_send_link_resend_cooldown(self) -> None:
        """A resend inside the cooldown reports already_sent with the retry time."""
        with (
            mock.patch(
                "apps.payments.razorpay_service.create_payment_link",
                return_value={"id": "plink_e2", "short_url": "https://rzp.io/i/e2"},
            ),
            mock.patch(
                "apps.payments.services.send_whatsapp_template",
                return_value=WhatsAppAttempt(provider="gupshup", sent=True, attempted=True),
            ),
        ):
            self._send(self.payment)
            response = self._send(self.payment)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "already_sent")
        self.assertIsNotNone(response.data["resend_allowed_after"])

    def test_send_link_rejects_non_pending_payment(self) -> None:
        """Only pending payments can receive a link."""
        self.payment.status = Payment.Status.COMPLETED
        self.payment.save()
        response = self._send(self.payment)
        self.assertEqual(response.status_code, 400)

    def test_send_link_failure_returns_400_with_detail(self) -> None:
        """All legs failing (no channel config) surfaces as a 400 with detail."""
        self.tenant.is_gupshup_enabled = False
        self.tenant.save()
        with mock.patch(
            "apps.payments.razorpay_service.create_payment_link",
            return_value={"id": "plink_e3", "short_url": "https://rzp.io/i/e3"},
        ):
            response = self._send(self.payment)
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_send_link_tenant_isolation(self) -> None:
        """A foreign tenant's 404s on send-link keep queues isolated."""
        other_tenant = provision_tenant(name="Pulse Gym", contact_email="pulse@local.test")
        other_user = User.objects.create_user(
            email="pulse@local.test",
            password="F1tNati0n!",
            first_name="Pulse",
            last_name="Owner",
            role=User.Role.GYM_OWNER,
            tenant=other_tenant,
        )
        other_token = issue_token(other_user, other_tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
        response = self._send(self.payment)
        self.assertEqual(response.status_code, 404)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.razorpay_payment_link_id, "")


class PaymentLinkWebhookTests(TestCase):
    """Tests for the ``payment_link.paid`` webhook (issue #72)."""

    def setUp(self) -> None:
        """Create tenant, config, customer, and a pending link payment."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.config = RazorpayConfig.objects.create(
            tenant=self.tenant,
            api_key="rzp_test_key",
            api_secret="rzp_test_secret",
            webhook_secret="whsec_test",
            is_active=True,
        )
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
        )
        self.payment = Payment.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            amount="1500.00",
            payment_method=Payment.PaymentMethod.ONLINE,
            status=Payment.Status.PENDING,
            razorpay_payment_link_id="plink_wh1",
        )

    def _sign(self, payload: bytes) -> str:
        return hmac.new(b"whsec_test", payload, hashlib.sha256).hexdigest()

    def _post(self, plink_entity: dict, payment_entity: dict | None = None, with_header: bool = True) -> None:
        payload_obj = {"payment_link": {"entity": plink_entity}}
        if payment_entity is not None:
            payload_obj["payment"] = {"entity": payment_entity}
        data = {"event": "payment_link.paid", "payload": payload_obj}
        body = json.dumps(data).encode()
        headers = {"HTTP_X_RAZORPAY_SIGNATURE": self._sign(body)}
        if with_header:
            headers["HTTP_X_RAZORPAY_TENANT"] = str(self.tenant.id)
        return self.client.post(
            "/api/v1/payments/razorpay/webhook/",
            data=body,
            content_type="application/json",
            **headers,
        )

    def test_payment_link_paid_marks_payment_completed(self) -> None:
        """A paid link marks the referenced payment completed and invoices it."""
        response = self._post(
            {"id": "plink_wh1", "reference_id": str(self.payment.id)},
            {"id": "pay_wh1"},
        )
        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.COMPLETED)
        self.assertEqual(self.payment.razorpay_payment_id, "pay_wh1")
        self.assertEqual(self.payment.transaction_id, "pay_wh1")
        self.assertIsNotNone(self.payment.paid_at)
        self.assertTrue(Invoice.objects.filter(payment=self.payment).exists())
        # The proven payment_received template fires alongside (issue #72).
        self.assertTrue(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.PAYMENT_RECEIVED,
                customer=self.customer,
            ).exists(),
        )

    def test_payment_link_paid_is_idempotent(self) -> None:
        """A duplicated webhook transitions once — one transition, invoice, message."""
        first = self._post({"id": "plink_wh1", "reference_id": str(self.payment.id)}, {"id": "pay_wh1"})
        second = self._post({"id": "plink_wh1", "reference_id": str(self.payment.id)}, {"id": "pay_wh1"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.COMPLETED)
        self.assertEqual(self.payment.razorpay_payment_id, "pay_wh1")
        self.assertEqual(Invoice.objects.filter(payment=self.payment).count(), 1)
        self.assertEqual(
            NotificationLog.objects.filter(
                tenant=self.tenant,
                notification_type=NotificationLog.NotificationType.PAYMENT_RECEIVED,
            ).count(),
            1,
        )

    def test_payment_link_paid_resolves_by_link_id_without_reference(self) -> None:
        """No reference_id → the stored razorpay_payment_link_id resolves the payment."""
        response = self._post({"id": "plink_wh1"}, {"id": "pay_wh2"})
        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.COMPLETED)
        self.assertEqual(self.payment.razorpay_payment_id, "pay_wh2")

    def test_payment_link_paid_resolves_tenant_without_header(self) -> None:
        """Without the tenant header, the stored link id resolves tenant + payment."""
        other_tenant = provision_tenant(name="Pulse Gym", contact_email="pulse@local.test")
        RazorpayConfig.objects.create(
            tenant=other_tenant,
            api_key="rzp_other",
            api_secret="rzp_other_secret",
            webhook_secret="whsec_other",
            is_active=True,
        )
        response = self._post(
            {"id": "plink_wh1", "reference_id": str(self.payment.id)},
            {"id": "pay_wh3"},
            with_header=False,
        )
        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.COMPLETED)

    def test_unknown_payment_link_tenant_is_404(self) -> None:
        """A link nobody stores cannot resolve a tenant — 404 so Razorpay retries."""
        response = self._post({"id": "plink_unknown", "reference_id": ""}, {"id": "pay_x"}, with_header=False)
        self.assertEqual(response.status_code, 404)

    def test_tampered_link_webhook_rejected(self) -> None:
        """A bad signature on a payment_link event is rejected with 400."""
        body = json.dumps(
            {"event": "payment_link.paid", "payload": {"payment_link": {"entity": {"id": "plink_wh1"}}}}
        ).encode()
        response = self.client.post(
            "/api/v1/payments/razorpay/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_RAZORPAY_TENANT=str(self.tenant.id),
            HTTP_X_RAZORPAY_SIGNATURE="deadbeef",
        )
        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)
