"""Membership management serializers."""

from typing import ClassVar

from rest_framework import serializers

from apps.customers.serializers import DeletedCustomerFlagMixin
from apps.memberships.models import Coupon, Membership, MembershipPlan
from apps.memberships.services import assert_no_membership_overlap


class MembershipPlanSerializer(serializers.ModelSerializer):
    """Serialize membership plan details."""

    class Meta:
        """Serializer metadata."""

        model = MembershipPlan
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "plan_type",
            "price",
            "duration_days",
            "description",
            "is_active",
            "includes_app_access",
            "sessions_allowed",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "created_at", "updated_at"]


class MembershipSerializer(DeletedCustomerFlagMixin, serializers.ModelSerializer):
    """Serialize membership details."""

    customer_id = serializers.ReadOnlyField()
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    price = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata."""

        model = Membership
        fields: ClassVar[list[str]] = [
            "id",
            "customer",
            "customer_id",
            "customer_name",
            "customer_is_deleted",
            "plan",
            "plan_name",
            "price",
            "start_date",
            "end_date",
            "status",
            "auto_renew",
            "created_at",
            "updated_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["id", "status", "created_at", "updated_at"]

    def get_price(self, obj: Membership) -> float:
        """Return the plan price as a float (0 when no plan is attached)."""
        if obj.plan and obj.plan.price is not None:
            return float(obj.plan.price)
        return 0.0

    def validate(self, data: dict) -> dict:
        """Ensure end_date is after start_date and no ACTIVE period overlaps (#104)."""
        start_date = data.get("start_date") or getattr(self.instance, "start_date", None)
        end_date = data.get("end_date") or getattr(self.instance, "end_date", None)
        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError(
                {"end_date": "end_date must be after start_date."},
            )
        customer = data.get("customer") or getattr(self.instance, "customer", None)
        if customer is not None and start_date and end_date:
            # A cancelled row stays cancelled regardless of dates
            # (``compute_status``), so moving its period can never produce a
            # second ACTIVE membership — nothing to guard.
            cancelled = self.instance is not None and self.instance.status == Membership.Status.CANCELLED
            if not cancelled:
                assert_no_membership_overlap(
                    tenant=customer.tenant,
                    customer=customer,
                    start_date=start_date,
                    end_date=end_date,
                    exclude_pk=self.instance.pk if self.instance is not None else None,
                )
        return data


class AppInviteSerializer(serializers.Serializer):
    """Validate an app-invite send/resend request (FBOS-011 §5.1b)."""

    customer_id = serializers.IntegerField()
    resend = serializers.BooleanField(required=False, default=False)


class CouponSerializer(serializers.ModelSerializer):
    """Serialize coupon details."""

    class Meta:
        """Serializer metadata."""

        model = Coupon
        fields: ClassVar[list[str]] = [
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
        read_only_fields: ClassVar[list[str]] = ["id", "used_count", "created_at", "updated_at"]
