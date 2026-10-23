"""Notification serializers."""

from typing import ClassVar

from rest_framework import serializers

from apps.notifications.models import DeviceToken, NotificationLog


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
            "channel",
            "provider",
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


class DeviceTokenSerializer(serializers.ModelSerializer):
    """Validate an FCM device-token registration (FBOS-011 §7.4)."""

    class Meta:
        """Serializer metadata."""

        model = DeviceToken
        fields: ClassVar[list[str]] = [
            "id",
            "token",
            "device_id",
            "platform",
            "device_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
        # Registration is an upsert keyed on the token string (FBOS-011 §7.4):
        # the view's ``update_or_create`` owns uniqueness, so DRF's auto
        # ``UniqueValidator`` must not pre-empt it with a 400 on re-register
        # (QA-DEF-001 — the mobile app re-registers on every app start).
        extra_kwargs: ClassVar[dict] = {"token": {"validators": []}}

    def validate_platform(self, value: str) -> str:
        """Default a blank platform to android (the v1 customer app)."""
        return value or DeviceToken.Platform.ANDROID
