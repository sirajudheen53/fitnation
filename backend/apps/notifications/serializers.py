"""Notification serializers."""

from typing import ClassVar

from rest_framework import serializers

from apps.notifications.models import NotificationLog


class NotificationLogSerializer(serializers.ModelSerializer):
    """Serialize a notification log entry."""

    customer_name = serializers.CharField(source="customer.name", read_only=True, default="")

    class Meta:
        """Serializer metadata."""

        model = NotificationLog
        fields: ClassVar[list] = [
            "id",
            "customer",
            "customer_name",
            "notification_type",
            "status",
            "content",
            "wati_message_id",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list] = ["id", "created_at", "updated_at"]


class TestNotificationSerializer(serializers.Serializer):
    """Validate a test-notification request."""

    to = serializers.CharField()
    message = serializers.CharField(required=False, allow_blank=True, default="")
    notification_type = serializers.ChoiceField(
        choices=NotificationLog.NotificationType.choices,
        required=False,
        default=NotificationLog.NotificationType.CHECK_IN,
    )


class WatiSettingsSerializer(serializers.Serializer):
    """Validate Wati settings updates (masked read, write for api_key)."""

    wati_api_key = serializers.CharField(required=False, write_only=True)
    wati_endpoint = serializers.URLField(required=False)
    is_wati_enabled = serializers.BooleanField(required=False)
