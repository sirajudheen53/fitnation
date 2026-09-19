"""Access control domain models — biometric device registry and membership."""

from __future__ import annotations


from django.core.validators import MinLengthValidator
from django.db import models

from apps.tenants.models import TenantModelMixin


class Vendor(models.TextChoices):
    """Supported biometric device vendors."""

    HIKVISION = "hikvision", "Hikvision"
    ZKTECO = "zkteco", "ZKTeco"
    ESSL = "essl", "eSSL"
    MATRIX = "matrix", "Matrix"
    SUPREMA = "suprema", "Suprema"
    ANVIZ = "anviz", "Anviz"
    DAHUA = "dahua", "Dahua"
    REALTIME = "realtime", "Realtime"
    MANTRA = "mantra", "Mantra"
    TIMEWATCH = "timewatch", "TimeWatch"
    GENERIC = "generic", "Generic HTTP/MQTT"


class ConnectionType(models.TextChoices):
    """How the device communicates with our backend."""

    WEBHOOK = "webhook", "Webhook Push (device calls us)"
    AGENT = "agent", "Agent Pull (our agent polls device)"
    CLOUD_API = "cloud_api", "Cloud Sync (vendor cloud API)"


class CredentialType(models.TextChoices):
    """Biometric credential type."""

    FINGERPRINT = "fingerprint", "Fingerprint"
    FACE = "face", "Face Recognition"
    CARD = "card", "RFID Card"
    PIN = "pin", "PIN Code"
    QR = "qr", "QR Code"


class BiometricDevice(TenantModelMixin):
    """A registered biometric access device at a gym branch door."""

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="biometric_devices",
    )
    vendor = models.CharField(max_length=32, choices=Vendor.choices)
    model = models.CharField(max_length=128)
    serial_number = models.CharField(
        max_length=64,
        validators=[MinLengthValidator(3)],
        help_text="Device serial / MAC / IMEI",
    )
    name = models.CharField(
        max_length=128,
        help_text="Human-readable name, e.g. 'Main Entrance'",
    )
    connection_type = models.CharField(
        max_length=16,
        choices=ConnectionType.choices,
    )
    api_endpoint = models.URLField(
        blank=True,
        help_text="Device webhook or cloud API URL",
    )
    api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Device API key / secret (encrypted at rest)",
    )
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        unique_together = [("branch", "serial_number")]
        ordering = ["branch__name", "name"]

    def __str__(self) -> str:
        """Return human-readable device name."""
        return f"{self.name} ({self.vendor} — {self.serial_number})"


class BiometricCredential(TenantModelMixin):
    """A customer's biometric credential mapped to a specific device."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="biometric_credentials",
    )
    device = models.ForeignKey(
        BiometricDevice,
        on_delete=models.CASCADE,
        related_name="credentials",
    )
    credential_type = models.CharField(
        max_length=16,
        choices=CredentialType.choices,
    )
    device_user_id = models.CharField(
        max_length=64,
        help_text="User ID assigned on the device (e.g. device index number)",
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        unique_together = [("device", "device_user_id")]
        ordering = ["device__name", "device_user_id"]

    def __str__(self) -> str:
        """Return human-readable credential identifier."""
        return f"{self.customer} on {self.device} ({self.device_user_id})"


class AccessOverride(TenantModelMixin):
    """Gym-owner override for a customer's access at a specific device."""

    REASON_GRACE = "grace_period"
    REASON_VIP = "vip"
    REASON_PAYMENT_ISSUE = "payment_issue"
    REASON_VIOLATION = "violation"
    REASON_STAFF = "staff"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="access_overrides",
    )
    device = models.ForeignKey(
        BiometricDevice,
        on_delete=models.CASCADE,
        related_name="overrides",
    )
    allow_access = models.BooleanField(
        help_text="True = grant access, False = deny access",
    )
    reason = models.CharField(max_length=32)
    reason_notes = models.TextField(blank=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Auto-revert after this time; null = permanent",
    )
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="access_overrides_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return human-readable override identifier."""
        return f"{self.customer} {'grant' if self.allow_access else 'deny'} on {self.device}"


class AccessLog(TenantModelMixin):
    """An entry/exit event recorded from a biometric device."""

    DEVICE_EVENT_TYPES = [
        ("entry", "Entry"),
        ("exit", "Exit"),
        ("denied", "Access Denied"),
        ("error", "Device Error"),
    ]

    device = models.ForeignKey(
        BiometricDevice,
        on_delete=models.CASCADE,
        related_name="access_logs",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="access_logs",
    )
    device_user_id = models.CharField(max_length=64)
    credential_type = models.CharField(
        max_length=16,
        choices=CredentialType.choices,
    )
    event_type = models.CharField(max_length=16, choices=DEVICE_EVENT_TYPES)
    event_timestamp = models.DateTimeField()
    raw_payload = models.JSONField(
        default=dict,
        help_text="Raw device payload for debugging",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        ordering = ["-event_timestamp"]

    def __str__(self) -> str:
        """Return human-readable log identifier."""
        return f"{self.customer} {self.event_type} at {self.event_timestamp}"


class DeviceCommandQueue(TenantModelMixin):
    """A queued outbound command for an ADMS device.

    ADMS devices poll our endpoint; commands are held here until the
    device's next poll delivers them (``executed_at`` is stamped on
    delivery).
    """

    device = models.ForeignKey(
        BiometricDevice,
        on_delete=models.CASCADE,
        related_name="pending_commands",
    )
    command = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Model metadata."""

        ordering = ["created_at"]

    def __str__(self) -> str:
        """Return a human-readable command label."""
        status = "executed" if self.executed_at else "pending"
        return f"{self.device.name}: {self.command} ({status})"


class AccessDecisionLog(TenantModelMixin):
    """A logged access-control decision from the rule engine (issue #19).

    Every evaluation of ``decide_and_log`` persists one row so gyms can
    audit why a member was granted or denied entry.
    """

    SOURCES = [
        ("override", "Owner Override"),
        ("plan_active", "Active Plan"),
        ("plan_expired", "Plan Expired"),
        ("no_membership", "No Membership"),
    ]

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="access_decisions",
    )
    device = models.ForeignKey(
        BiometricDevice,
        on_delete=models.CASCADE,
        related_name="decision_logs",
    )
    allowed = models.BooleanField(help_text="True = entry granted, False = denied.")
    source = models.CharField(max_length=32, choices=SOURCES)
    reason = models.CharField(max_length=255, blank=True)
    override = models.ForeignKey(
        AccessOverride,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decision_logs",
        help_text="Set when the decision came from an owner override.",
    )
    checked_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Model metadata."""

        ordering = ["-checked_at"]

    def __str__(self) -> str:
        """Return a human-readable decision label."""
        verdict = "ALLOW" if self.allowed else "DENY"
        return f"{verdict} {self.customer} at {self.device} ({self.source})"
