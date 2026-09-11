"""Access app serializers."""

from __future__ import annotations

from rest_framework import serializers

from apps.access.models import (
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
)


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
