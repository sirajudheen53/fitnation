"""Admin ops serializers."""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.tenants.models import Tenant
from apps.vendors.models import SubscriptionPlan


class TenantAdminSerializer(serializers.ModelSerializer):
    """Platform-admin view of a tenant with computed counts."""

    member_count = serializers.IntegerField(read_only=True)
    branch_count = serializers.IntegerField(read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Tenant
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "subscription_plan",
            "status",
            "contact_email",
            "contact_phone",
            "member_count",
            "branch_count",
            "created_at",
        ]
        read_only_fields = fields


class AdminOnboardGymSerializer(serializers.Serializer):
    """Payload for POST /api/v1/admin/tenants/onboard/ (issue #40)."""

    gym_name = serializers.CharField(max_length=200)
    contact_name = serializers.CharField(max_length=200)
    owner_email = serializers.EmailField()
    owner_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    branch_name = serializers.CharField(max_length=200)
    branch_type = serializers.ChoiceField(choices=["main", "sub"], default="main")
    plan_code = serializers.ChoiceField(choices=SubscriptionPlan.PlanCode.choices)


class TenantAdminUpdateSerializer(serializers.ModelSerializer):
    """Payload for PUT/PATCH /api/v1/admin/tenants/{id}/ (gym edit + suspension).

    All fields optional on PATCH; PUT requires ``name`` and ``contact_email``.
    ``status`` stays limited to active/suspended — archiving a gym happens
    only via DELETE (soft delete). ``contact_email`` is validated against
    the model's unique constraint (the current tenant is excluded) and
    normalized to lowercase, matching onboarding.
    """

    class Meta:
        """Serializer metadata."""

        model = Tenant
        fields: ClassVar[list[str]] = [
            "name",
            "contact_email",
            "contact_phone",
            "subscription_plan",
            "status",
        ]
        extra_kwargs: ClassVar[dict] = {
            "subscription_plan": {"choices": SubscriptionPlan.PlanCode.choices},
            "status": {"choices": ["active", "suspended"]},
        }

    def validate_contact_email(self, value: str) -> str:
        """Normalize the contact email to lowercase (onboarding invariant)."""
        return value.strip().lower()


class SubscriptionPlanAdminSerializer(serializers.ModelSerializer):
    """Platform-admin CRUD serializer for subscription plans (issue #44)."""

    class Meta:
        """Serializer metadata."""

        model = SubscriptionPlan
        fields: ClassVar[list[str]] = [
            "id",
            "code",
            "name",
            "price_monthly",
            "price_yearly",
            "max_branches",
            "max_customers",
            "max_trainers",
            "features",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
