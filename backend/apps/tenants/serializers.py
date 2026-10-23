"""Tenant serializers."""

from typing import Any, ClassVar

from rest_framework import serializers

from apps.tenants.features import MODULE_FEATURES
from apps.tenants.models import Tenant, TenantSettings


class TenantSettingsSerializer(serializers.ModelSerializer):
    """Serialize tenant settings."""

    class Meta:
        """Serializer metadata."""

        model = TenantSettings
        fields: ClassVar[list[str]] = [
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
    """Body of ``POST /tenants/whatsapp/test/`` (settings-page test send).

    ``provider`` picks which WhatsApp BSP to test — ``wati`` (default, the
    original contract) or ``gupshup`` (issue #66 / frontend ticket #67). The
    test never falls back to the other provider: it reports the chosen one's
    own outcome.
    """

    phone = serializers.CharField(max_length=20)
    provider = serializers.ChoiceField(
        choices=["wati", "gupshup"],
        default="wati",
        required=False,
        help_text="Which WhatsApp provider to test (wati | gupshup).",
    )


class ModuleFeatureMetaSerializer(serializers.Serializer):
    """One entry of the module-toggle catalog (``GET /tenants/features/``)."""

    key = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True, help_text="Settings-page display name.")
    description = serializers.CharField(read_only=True)
    default = serializers.BooleanField(
        read_only=True,
        help_text="Value seeded for new tenants; re-enabling resets to this.",
    )


class TenantFeatureSettingsSerializer(serializers.Serializer):
    """Shape of ``GET /tenants/features/`` (issue #46 gym-level settings).

    - ``flags``: resolved ``{key: enabled}`` for every registered module —
      what the ERP/mobile read to hide a module's surface.
    - ``catalog``: toggle metadata for the settings UI (labels, defaults).
    """

    flags = serializers.DictField(
        child=serializers.BooleanField(),
        read_only=True,
        help_text="Resolved module flags: missing stored key = registry default.",
    )
    catalog = ModuleFeatureMetaSerializer(many=True, read_only=True)


def tenant_feature_settings_payload(tenant: Tenant) -> dict[str, Any]:
    """Build the ``TenantFeatureSettingsSerializer`` payload for a tenant."""
    from apps.tenants.features import get_feature_flags

    return {
        "flags": get_feature_flags(tenant),
        "catalog": [
            {
                "key": feature.key,
                "label": feature.label,
                "description": feature.description,
                "default": feature.default,
            }
            for feature in MODULE_FEATURES
        ],
    }


class TenantFeatureUpdateSerializer(serializers.Serializer):
    """Body of ``PATCH /tenants/features/``: partial module-flag merge.

    ``flags`` keys must all be registered module features (anything else is a
    400 so a typo can never become a dead toggle); values must be real JSON
    booleans. The merge preserves non-module keys already on the tenant
    (``app_access`` etc.).
    """

    flags = serializers.DictField(
        child=serializers.BooleanField(),
        help_text="Partial ``{key: bool}`` map of module toggles to merge.",
    )

    def validate_flags(self, value: dict[str, bool]) -> dict[str, bool]:
        """Reject non-boolean input values and unregistered feature keys.

        DRF's ``BooleanField`` coerces ``"no"``/``"0"``/``1`` silently; the API
        requires real JSON booleans, so the raw payload is type-checked too.
        """
        raw = (self.initial_data or {}).get("flags") or {}
        for key, raw_value in raw.items():
            if not isinstance(raw_value, bool):
                raise serializers.ValidationError({key: "Must be true or false."})
        unknown = [key for key in value if key not in {feature.key for feature in MODULE_FEATURES}]
        if unknown:
            raise serializers.ValidationError(
                {key: "Unknown module feature (typos are never stored)." for key in unknown},
            )
        return value


class TenantSerializer(serializers.ModelSerializer):
    """Serialize tenant details, including the WhatsApp (WATI/Gupshup) config."""

    config = TenantSettingsSerializer(read_only=True)
    wati_api_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Write-only. Stored encrypted; a PATCH without it keeps the stored key.",
    )
    wati_api_key_configured = serializers.SerializerMethodField()
    gupshup_api_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Write-only. Stored encrypted; a PATCH without it keeps the stored key.",
    )
    gupshup_api_key_configured = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata."""

        model = Tenant
        fields: ClassVar[list[str]] = [
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
            # Gupshup (issue #66): same exposure pattern as WATI.
            "is_gupshup_enabled",
            "gupshup_source",
            "gupshup_app_name",
            "gupshup_api_key",
            "gupshup_api_key_configured",
            "created_at",
            "updated_at",
        ]

    def get_wati_api_key_configured(self, obj: Tenant) -> bool:
        """Whether the tenant has a WATI API key configured (never the value)."""
        return bool(obj.wati_api_key)

    def get_gupshup_api_key_configured(self, obj: Tenant) -> bool:
        """Whether the tenant has a Gupshup API key configured (never the value)."""
        return bool(obj.gupshup_api_key)

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
        gupshup_key = validated_data.pop("gupshup_api_key", None)
        if gupshup_key:
            instance.gupshup_api_key = gupshup_key
        return super().update(instance, validated_data)
