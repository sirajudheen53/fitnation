"""Tenant serializers."""

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


class TenantSerializer(serializers.ModelSerializer):
    """Serialize tenant details."""

    config = TenantSettingsSerializer(read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Tenant
        fields = [
            "id",
            "uuid",
            "name",
            "legal_name",
            "subscription_plan",
            "status",
            "contact_email",
            "contact_phone",
            "timezone",
            "settings",
            "config",
            "created_at",
            "updated_at",
        ]
