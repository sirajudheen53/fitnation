"""Membership management serializers."""

from rest_framework import serializers

from apps.memberships.models import Coupon, Membership, MembershipPlan


class MembershipPlanSerializer(serializers.ModelSerializer):
    """Serialize membership plan details."""

    class Meta:
        """Serializer metadata."""

        model = MembershipPlan
        fields = [
            "id",
            "name",
            "plan_type",
            "price",
            "duration_days",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MembershipSerializer(serializers.ModelSerializer):
    """Serialize membership details."""

    class Meta:
        """Serializer metadata."""

        model = Membership
        fields = [
            "id",
            "customer",
            "plan",
            "start_date",
            "end_date",
            "status",
            "auto_renew",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate(self, data: dict) -> dict:
        """Ensure end_date is after start_date."""
        start_date = data.get("start_date") or getattr(self.instance, "start_date", None)
        end_date = data.get("end_date") or getattr(self.instance, "end_date", None)
        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError(
                {"end_date": "end_date must be after start_date."},
            )
        return data


class CouponSerializer(serializers.ModelSerializer):
    """Serialize coupon details."""

    class Meta:
        """Serializer metadata."""

        model = Coupon
        fields = [
            "id",
            "code",
            "discount_percent",
            "max_uses",
            "used_count",
            "valid_from",
            "valid_to",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "used_count", "created_at", "updated_at"]
