"""Tests for the payments app."""

from datetime import timedelta
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.payments.models import Invoice, Payment
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
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="other@local.test"
        )
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
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="other@local.test"
        )
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
        response = self.client.get(
            f"/api/v1/payments/?paid_at__gte={start}&paid_at__lte={end}"
        )
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
