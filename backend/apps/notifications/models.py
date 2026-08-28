"""Notification tracking models."""

from typing import ClassVar

from django.db import models

from apps.tenants.models import TenantModelMixin


class NotificationLog(TenantModelMixin):
    """A single notification attempt sent via Wati (or skipped/logged)."""

    class NotificationType(models.TextChoices):
        LOW_STOCK = "low_stock", "Low Stock"
        """Supported notification types."""

        CHECK_IN = "check_in", "Check-in"
        MEMBERSHIP_EXPIRY = "membership_expiry", "Membership Expiry"
        WORKOUT_ASSIGNED = "workout_assigned", "Workout Assigned"
        PAYMENT_RECEIVED = "payment_received", "Payment Received"

    class Status(models.TextChoices):
        """Lifecycle status of a notification attempt."""

        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        PENDING = "pending", "Pending"
        SKIPPED = "skipped", "Skipped"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notification_logs",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    content = models.TextField(blank=True)
    wati_message_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """NotificationLog model metadata."""

        db_table = "notification_logs"
        ordering: ClassVar[list] = ["-created_at"]
        indexes: ClassVar[list] = [
            models.Index(
                fields=["tenant", "notification_type"],
                name="idx_notif_type",
            ),
            models.Index(fields=["tenant", "status"], name="idx_notif_status"),
        ]

    def __str__(self) -> str:
        """Return a human-readable notification label."""
        return f"{self.notification_type} → {self.customer} ({self.status})"
