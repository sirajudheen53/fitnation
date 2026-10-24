"""Notification tracking models."""

from typing import ClassVar

from django.db import models

from apps.tenants.models import Tenant, TenantManager, TenantModelMixin


class NotificationLog(TenantModelMixin):
    """A single notification attempt sent via Wati (or skipped/logged)."""

    class NotificationType(models.TextChoices):
        LOW_STOCK = "low_stock", "Low Stock"
        """Supported notification types."""

        CHECK_IN = "check_in", "Check-in"
        MEMBERSHIP_EXPIRY = "membership_expiry", "Membership Expiry"
        WORKOUT_ASSIGNED = "workout_assigned", "Workout Assigned"
        PAYMENT_RECEIVED = "payment_received", "Payment Received"
        PAYMENT_LINK = "payment_link", "Payment Link"
        APP_INVITE = "app_invite", "App Invite"
        OTP = "otp", "OTP Delivery"
        WELCOME = "welcome", "Welcome"
        EMAIL_VERIFICATION = "email_verification", "Email Verification"

    class Status(models.TextChoices):
        """Lifecycle status of a notification attempt."""

        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        PENDING = "pending", "Pending"
        SKIPPED = "skipped", "Skipped"

    class Provider(models.TextChoices):
        """The transport that carried (or attempted) the send.

        ``channel`` stays semantic (whatsapp | sms | email); ``provider``
        names which WhatsApp BSP / SMS / email vendor actually handled it
        (issue #66) — with two WhatsApp BSPs available the log must show
        which one carried the message.
        """

        WATI = "wati", "WATI"
        GUPSHUP = "gupshup", "Gupshup"
        MSG91 = "msg91", "MSG91"
        SENDGRID = "sendgrid", "SendGrid"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notification_logs",
    )
    actor = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_logs",
        help_text="The staff user who triggered the send (audit trail, FBOS-011 §10.2).",
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
    channel = models.CharField(
        max_length=20,
        blank=True,
        help_text='Delivery channel used for the attempt, e.g. "whatsapp" or "sms".',
    )
    provider = models.CharField(
        max_length=20,
        blank=True,
        choices=Provider.choices,
        help_text="The transport that carried the attempt (channel stays semantic, issue #66).",
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


class DeviceToken(models.Model):
    """A registered FCM (push) device token for the customer mobile app.

    Separate domain from ``apps/access`` device models — those are gym door
    hardware; this is the member's phone (FBOS-011 §7.4). Tokens are upserted
    (idempotent per token: re-registering rotates the binding), and deleted
    on logout.
    """

    class Platform(models.TextChoices):
        """Device platforms we can push to."""

        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="device_tokens",
        db_index=True,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="device_tokens",
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="device_tokens",
    )
    token = models.CharField(max_length=255, unique=True, db_index=True)
    device_id = models.CharField(max_length=200, blank=True)
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.ANDROID)
    device_type = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        """Model metadata."""

        db_table = "notification_device_tokens"
        ordering: ClassVar[list] = ["-created_at"]
        indexes: ClassVar[list] = [
            models.Index(fields=["tenant", "customer"], name="idx_devtoken_tenant_customer"),
        ]

    def __str__(self) -> str:
        """Return a redacted label (never the full token)."""
        owner = self.customer or self.user
        return f"DeviceToken {self.token[:8]}… ({owner}, {self.platform})"
