"""Payment tracking models."""

from typing import ClassVar

from django.db import models
from django.utils import timezone

from apps.core.fields import EncryptedCharField
from apps.tenants.models import TenantModelMixin


class RazorpayConfig(TenantModelMixin):
    """Per-tenant Razorpay credentials and activation state."""

    api_key = EncryptedCharField(max_length=255, blank=True)
    api_secret = EncryptedCharField(max_length=255, blank=True)
    webhook_secret = EncryptedCharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """RazorpayConfig model metadata."""

        db_table = "razorpay_configs"

    def __str__(self) -> str:
        """Return a human-readable label."""
        return f"Razorpay config for {self.tenant.name} ({'active' if self.is_active else 'inactive'})"


class Payment(TenantModelMixin):
    """A payment recorded against a customer, optionally linked to a membership."""

    class PaymentMethod(models.TextChoices):
        """Supported payment methods."""

        CASH = "cash", "Cash"
        CARD = "card", "Card"
        ONLINE = "online", "Online"
        UPI = "upi", "UPI"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        """Lifecycle status of a payment."""

        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class Kind(models.TextChoices):
        """What the payment is for (msg 2438 admission fees)."""

        MEMBERSHIP = "membership", "Membership"
        ADMISSION = "admission", "Admission"

    customer = models.ForeignKey(
        "customers.Customer",
        # Issue #81: financial records survive a deleted customer — a hard
        # delete fails loudly instead of destroying payment history.
        on_delete=models.PROTECT,
        related_name="payments",
    )
    # kind=membership is the default so pre-existing rows are unaffected.
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.MEMBERSHIP,
    )
    membership = models.ForeignKey(
        "memberships.Membership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    transaction_id = models.CharField(max_length=100, blank=True)
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    # Issue #72: the latest Razorpay payment link created for this payment and
    # when its message was last successfully sent (resend-cooldown guard).
    razorpay_payment_link_id = models.CharField(max_length=100, blank=True)
    payment_link_sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Payment model metadata."""

        db_table = "payments"
        ordering: ClassVar[list] = ["-created_at"]
        indexes: ClassVar[list] = [
            models.Index(fields=["tenant", "customer"], name="idx_payment_tenant_customer"),
            models.Index(fields=["tenant", "status"], name="idx_payment_tenant_status"),
            models.Index(fields=["tenant", "razorpay_order_id"], name="idx_payment_order_id"),
            # Issue #82: the dashboard revenue series and revenue-summary
            # filter completed payments by paid_at; the pending queue orders
            # by created_at within a status.
            models.Index(fields=["tenant", "status", "paid_at"], name="idx_pay_tenant_status_paid"),
            models.Index(fields=["tenant", "status", "created_at"], name="idx_pay_tenant_status_created"),
        ]

    def __str__(self) -> str:
        """Return payment label."""
        return f"Payment {self.id} — {self.customer} ({self.amount})"


class Invoice(TenantModelMixin):
    """An invoice generated from a payment."""

    customer = models.ForeignKey(
        "customers.Customer",
        # Issue #81: invoices are financial records — PROTECT, never cascade.
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Invoice model metadata."""

        db_table = "invoices"
        ordering: ClassVar[list] = ["-generated_at"]

    def __str__(self) -> str:
        """Return invoice label."""
        return f"Invoice {self.invoice_number} — {self.customer}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the invoice, auto-generating the invoice number if absent."""
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)

    def _generate_invoice_number(self) -> str:
        """Generate a unique invoice number like ``INV-YYYYMMDD-<seq>``.

        The sequence is derived from the count of invoices generated on the same
        day, so numbers are unique per day and globally unique via the unique
        constraint on ``invoice_number``.

        Returns:
            A string invoice number.
        """
        today = timezone.localdate()
        prefix = f"INV-{today:%Y%m%d}"
        count = Invoice.objects.filter(
            invoice_number__startswith=prefix,
        ).count()
        return f"{prefix}-{count + 1:04d}"


class PaymentRefund(TenantModelMixin):
    """A refund issued against a payment via Razorpay."""

    class Status(models.TextChoices):
        """Lifecycle status of a refund."""

        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="refunds",
    )
    refund_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reason = models.CharField(max_length=200, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """PaymentRefund model metadata."""

        db_table = "payment_refunds"
        ordering: ClassVar[list] = ["-created_at"]
        indexes: ClassVar[list] = [
            models.Index(fields=["tenant", "payment"], name="idx_refund_tenant_payment"),
        ]

    def __str__(self) -> str:
        """Return a human-readable refund label."""
        return f"Refund {self.refund_id or self.id} — {self.amount}"
