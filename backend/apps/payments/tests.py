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
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.payments import razorpay_service
from apps.payments.models import Invoice, Payment, PaymentRefund, RazorpayConfig
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
                "customer": self.customer.id,
                "membership": self.membership.id,
                "amount": "1500.00",
                "payment_method": "cash",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "completed")
        self.assertIsNotNone(response.data["paid_at"])

    def test_record_pending_payment_has_no_paid_at(self) -> None:
        """A pending payment has no paid_at timestamp."""
        response = self.client.post(
            "/api/v1/payments/",
            {
                "customer": self.customer.id,
                "amount": "1500.00",
                "payment_method": "cash",
                "status": "pending",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["paid_at"])

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
