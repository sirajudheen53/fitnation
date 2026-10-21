"""Tenant serializers."""

from typing import Any

from rest_framework import serializers

from apps.tenants.models import Tenant, TenantSettings


class TenantSettingsSerializer(serializers.ModelSerializer):
    """Serialize tenant settings."""

    class Meta:
        """Serializer metadata."""

        model = TenantSettings
        fields = [
            "max_branches",
            "max_customers",
            "max_trainers",
            "logo_url",
            "primary_color",
            "enable_whatsapp",
            "enable_razorpay",
            "custom_domain",
        ]


class WhatsappTestSendSerializer(serializers.Serializer):
    """Body of ``POST /tenants/whatsapp/test/`` (settings-page test send)."""

    phone = serializers.CharField(max_length=20)


class TenantSerializer(serializers.ModelSerializer):
    """Serialize tenant details, including the WhatsApp (WATI) config."""

    config = TenantSettingsSerializer(read_only=True)
    wati_api_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Write-only. Stored encrypted; a PATCH without it keeps the stored key.",
    )
    wati_api_key_configured = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata."""

        model = Tenant
        fields = [
            "id",
            "uuid",
            "name",
            "gym_code",
            "legal_name",
            "subscription_plan",
            "status",
            "contact_email",
            "contact_phone",
            "timezone",
            "settings",
            "config",
            # WATI (FBOS-011 §6): only enable + endpoint are readable; the
            # secret is exposed as a boolean "configured" flag, never the value.
            "is_wati_enabled",
            "wati_endpoint",
            "wati_api_key",
            "wati_api_key_configured",
            "created_at",
            "updated_at",
        ]

    def get_wati_api_key_configured(self, obj: Tenant) -> bool:
        """Whether the tenant has a WATI API key configured (never the value)."""
        return bool(obj.wati_api_key)

    def update(self, instance: Tenant, validated_data: dict[str, Any]) -> Tenant:
        """Persist the tenant, treating an omitted/blank key as "keep existing".

        Args:
            instance: The tenant being updated.
            validated_data: Cleaned payload from the PATCH body.

        Returns:
            The updated tenant.
        """
        wati_key = validated_data.pop("wati_api_key", None)
        if wati_key:
            instance.wati_api_key = wati_key
        return super().update(instance, validated_data)
