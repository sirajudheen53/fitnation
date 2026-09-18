"""Access app serializers."""

from __future__ import annotations

from rest_framework import serializers

from apps.access.models import (
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
    CredentialType,
)
from apps.customers.models import Customer


class BiometricDeviceSerializer(serializers.ModelSerializer):
    """Serializer for biometric device registry."""

    class Meta:
        """Serializer metadata."""

        model = BiometricDevice
        fields = [
            "id", "branch", "vendor", "model", "serial_number", "name",
            "connection_type", "api_endpoint", "is_active",
            "last_sync_at", "last_seen_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "last_sync_at", "last_seen_at"]


class BiometricCredentialEnrollSerializer(serializers.Serializer):
    """Input serializer for enrolling a credential and syncing its device."""

    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    device = serializers.PrimaryKeyRelatedField(queryset=BiometricDevice.objects.all())
    credential_type = serializers.ChoiceField(choices=CredentialType.choices)
    device_user_id = serializers.CharField(max_length=64)

    def validate(self, attrs: dict) -> dict:
        """Keep enrollment inside the request tenant and per-device unique."""
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise serializers.ValidationError("Tenant context is required.")
        for key in ("customer", "device"):
            if attrs[key].tenant_id != tenant.id:
                raise serializers.ValidationError(
                    f"{key.capitalize()} must belong to the current tenant."
                )
        if BiometricCredential.objects.filter(
            device=attrs["device"], device_user_id=attrs["device_user_id"]
        ).exists():
            raise serializers.ValidationError(
                {"device_user_id": "Already enrolled on this device."}
            )
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


class BiometricCredentialSerializer(serializers.ModelSerializer):
    """Serializer for biometric credentials."""

    class Meta:
        """Serializer metadata."""

        model = BiometricCredential
        fields = [
            "id", "customer", "device", "credential_type",
            "device_user_id", "enrolled_at", "is_active",
        ]
        read_only_fields = ["id", "enrolled_at"]


class BiometricCredentialEnrollResultSerializer(serializers.Serializer):
    """Output serializer for the enroll action (credential + device sync)."""

    credential = BiometricCredentialSerializer()
    sync = DeviceSyncResultSerializer()


class AccessOverrideSerializer(serializers.ModelSerializer):
    """Serializer for access overrides."""

    class Meta:
        """Serializer metadata."""

        model = AccessOverride
        fields = [
            "id", "customer", "device", "allow_access", "reason",
            "reason_notes", "expires_at", "created_by",
        ]
        read_only_fields = ["id", "created_by"]


class AccessLogSerializer(serializers.ModelSerializer):
    """Serializer for access logs."""

    class Meta:
        """Serializer metadata."""

        model = AccessLog
        fields = [
            "id", "device", "customer", "device_user_id",
            "credential_type", "event_type", "event_timestamp", "raw_payload",
        ]
        read_only_fields = ["id"]
