"""Payment tracking models."""

from typing import ClassVar

from django.db import models
from django.utils import timezone

from apps.tenants.models import TenantModelMixin


class Payment(TenantModelMixin):
    """A payment recorded against a customer, optionally linked to a membership."""

    class PaymentMethod(models.TextChoices):
        """Supported payment methods."""

        CASH = "cash", "Cash"
        CARD = "card", "Card"
        ONLINE = "online", "Online"
        UPI = "upi", "UPI"

    class Status(models.TextChoices):
        """Lifecycle status of a payment."""

        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="payments",
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
        ]

    def __str__(self) -> str:
        """Return payment label."""
        return f"Payment {self.id} — {self.customer} ({self.amount})"


class Invoice(TenantModelMixin):
    """An invoice generated from a payment."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
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
