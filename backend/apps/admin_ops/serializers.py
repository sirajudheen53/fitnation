"""Admin ops serializers."""

from __future__ import annotations

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
        fields = [
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
    owner_phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    branch_name = serializers.CharField(max_length=200)
    branch_type = serializers.ChoiceField(choices=["main", "sub"], default="main")
    plan_code = serializers.ChoiceField(choices=SubscriptionPlan.PlanCode.choices)
