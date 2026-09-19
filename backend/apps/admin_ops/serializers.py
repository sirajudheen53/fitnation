"""Admin ops serializers."""

from __future__ import annotations

from rest_framework import serializers

from apps.tenants.models import Tenant


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
