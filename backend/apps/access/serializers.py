"""Access app serializers."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from rest_framework import serializers

from apps.access.models import (
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
    CredentialType,
    PunchLogRaw,
)
from apps.access.services import parse_attlog_punch
from apps.customers.models import Customer


class BiometricDeviceSerializer(serializers.ModelSerializer):
    """Serializer for biometric device registry."""

    class Meta:
        """Serializer metadata."""

        model = BiometricDevice
        fields: ClassVar[list[str]] = [
            "id",
            "branch",
            "vendor",
            "model",
            "serial_number",
            "name",
            "connection_type",
            "api_endpoint",
            "is_active",
            "last_sync_at",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at", "last_sync_at", "last_seen_at"]


class BiometricCredentialEnrollSerializer(serializers.Serializer):
    """Input serializer for enrolling a credential and syncing its device.

    ``device_user_id`` is optional: when omitted, the customer's canonical
    tenant-wide id is allocated/reused server-side (phase 2) and returned
    so the front desk can type it on the device.
    """

    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    device = serializers.PrimaryKeyRelatedField(queryset=BiometricDevice.objects.all())
    credential_type = serializers.ChoiceField(choices=CredentialType.choices)
    device_user_id = serializers.CharField(max_length=64, required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        """Keep enrollment inside the request tenant."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise serializers.ValidationError("Tenant context is required.")
        for key in ("customer", "device"):
            if attrs[key].tenant_id != tenant.id:
                raise serializers.ValidationError(f"{key.capitalize()} must belong to the current tenant.")
        return attrs


class DeviceConnectionTestResultSerializer(serializers.Serializer):
    """Output serializer for the device test-connection action."""

    online = serializers.BooleanField()
    detail = serializers.CharField()


class DeviceSyncResultSerializer(serializers.Serializer):
    """Output serializer for the device sync action."""

    synced = serializers.BooleanField()
    pushed = serializers.IntegerField(required=False)
    detail = serializers.CharField()


class DeviceEventsFetchResultSerializer(serializers.Serializer):
    """Output serializer for the device fetch-events action."""

    fetched = serializers.BooleanField()
    recorded = serializers.IntegerField()
    detail = serializers.CharField()


class DevicePullHistoryResultSerializer(serializers.Serializer):
    """Output serializer for the device pull-history action."""

    queued = serializers.BooleanField()
    mechanism = serializers.CharField()
    detail = serializers.CharField()
    device_id = serializers.IntegerField()
    last_seen_at = serializers.DateTimeField(allow_null=True)


class PunchLogRawSerializer(serializers.Serializer):
    """Raw punch row for the BioDebug viewer, with a cheap ATTLOG parse.

    ``pin``/``punch_at`` are best-effort parses of ATTLOG lines (device
    wall time, made aware); ``None`` for other tables and unparseable rows.
    """

    id = serializers.IntegerField(read_only=True)
    table_name = serializers.CharField(read_only=True)
    raw_line = serializers.CharField(read_only=True)
    received_at = serializers.DateTimeField(read_only=True)
    pin = serializers.SerializerMethodField()
    punch_at = serializers.SerializerMethodField()

    def get_pin(self, obj: PunchLogRaw) -> str | None:
        """Device user id from an ATTLOG line, else None."""
        if obj.table_name != "ATTLOG":
            return None
        return parse_attlog_punch(obj.raw_line)[0] or None

    def get_punch_at(self, obj: PunchLogRaw) -> datetime | None:
        """Aware punch timestamp from an ATTLOG line, else None."""
        if obj.table_name != "ATTLOG":
            return None
        return parse_attlog_punch(obj.raw_line)[1]


class BiometricCredentialSerializer(serializers.ModelSerializer):
    """Serializer for biometric credentials."""

    class Meta:
        """Serializer metadata."""

        model = BiometricCredential
        fields: ClassVar[list[str]] = [
            "id",
            "customer",
            "device",
            "credential_type",
            "device_user_id",
            "enrolled_at",
            "is_active",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "enrolled_at"]


class BiometricCredentialEnrollResultSerializer(serializers.Serializer):
    """Output serializer for the enroll action (credential + device sync)."""

    credential = BiometricCredentialSerializer()
    sync = DeviceSyncResultSerializer()


class AccessOverrideSerializer(serializers.ModelSerializer):
    """Serializer for access overrides."""

    class Meta:
        """Serializer metadata."""

        model = AccessOverride
        fields: ClassVar[list[str]] = [
            "id",
            "customer",
            "device",
            "allow_access",
            "reason",
            "reason_notes",
            "expires_at",
            "created_by",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_by"]


class AccessLogSerializer(serializers.ModelSerializer):
    """Serializer for access logs."""

    class Meta:
        """Serializer metadata."""

        model = AccessLog
        fields: ClassVar[list[str]] = [
            "id",
            "device",
            "customer",
            "device_user_id",
            "credential_type",
            "event_type",
            "event_timestamp",
            "raw_payload",
        ]
        read_only_fields: ClassVar[list[str]] = ["id"]
