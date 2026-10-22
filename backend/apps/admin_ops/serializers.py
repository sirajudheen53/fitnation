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


# ─── Platform stats (issue #47) ─────────────────────────────────────────────
# GET /api/v1/admin/stats/ — superuser only. Every field is read-only; the
# nested field docs below ARE the API contract for the frontend cards/charts.


class MonthCountPointSerializer(serializers.Serializer):
    """One ``{month, count}`` point of a per-month growth series."""

    month = serializers.CharField(help_text="Calendar month as ``YYYY-MM``.")
    count = serializers.IntegerField(help_text="Created-in-that-month rows.")


class MonthRevenuePointSerializer(serializers.Serializer):
    """One ``{month, total}`` point of the collected-revenue series."""

    month = serializers.CharField(help_text="Calendar month as ``YYYY-MM``.")
    total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Completed-payment amount collected that month, zero-filled.",
    )


class GymStatsSerializer(serializers.Serializer):
    """Gym (tenant) totals and lifecycle split."""

    total = serializers.IntegerField(help_text="All tenants regardless of status.")
    active = serializers.IntegerField()
    trial = serializers.IntegerField()
    suspended = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    archived = serializers.IntegerField()
    new_this_month = serializers.IntegerField(help_text="Tenants created this calendar month (local tz).")
    by_month = MonthCountPointSerializer(many=True, help_text="New gyms per month (zero-filled).")


class MemberStatsSerializer(serializers.Serializer):
    """Gym member (Customer) totals across the platform."""

    total = serializers.IntegerField(help_text="All customer records across gyms.")
    new_this_month = serializers.IntegerField()
    by_month = MonthCountPointSerializer(many=True, help_text="New members per month (zero-filled).")


class UserStatsSerializer(serializers.Serializer):
    """All platform users, split by cohort."""

    total = serializers.IntegerField()
    staff = serializers.IntegerField(help_text="gym_owner + manager + trainer + dietitian.")
    customers = serializers.IntegerField(help_text="role='customer' users (member app logins).")
    platform_admins = serializers.IntegerField()
    new_this_month = serializers.IntegerField()


class MembershipStatsSerializer(serializers.Serializer):
    """Membership lifecycle summary (stored status, synced with end_date on save)."""

    total = serializers.IntegerField()
    active = serializers.IntegerField()
    expired = serializers.IntegerField()
    cancelled = serializers.IntegerField()


class DeviceStatsSerializer(serializers.Serializer):
    """Biometric access devices registered across gyms."""

    total = serializers.IntegerField()
    active = serializers.IntegerField(help_text="Devices with is_active=True.")


class RevenueStatsSerializer(serializers.Serializer):
    """Payment/revenue summary (the ``payments`` app is always present)."""

    data_available = serializers.BooleanField(
        help_text="False until any Payment row exists — frontend shows a 'no payment data' state.",
    )
    total_collected = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Sum of COMPLETED payments platform-wide.",
    )
    collected_this_month = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Sum of COMPLETED payments with paid_at in the current month.",
    )
    pending_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Sum of PENDING payments.",
    )
    failed_count = serializers.IntegerField(help_text="Count of FAILED payments.")
    by_month = MonthRevenuePointSerializer(many=True, help_text="Collected per month (zero-filled).")


class PlatformStatsSerializer(serializers.Serializer):
    """Full payload of ``GET /api/v1/admin/stats/`` (issue #47).

    Single composite document for the admin dashboard cards + charts:
    ``{gyms, members, users, memberships, devices, revenue, growth,
    window_months}`` where ``growth`` aliases ``gyms.by_month`` /
    ``members.by_month`` for the chart component. All series cover the same
    ``window_months`` (6) and are zero-filled and oldest-first.
    """

    gyms = GymStatsSerializer()
    members = MemberStatsSerializer()
    users = UserStatsSerializer()
    memberships = MembershipStatsSerializer()
    devices = DeviceStatsSerializer()
    revenue = RevenueStatsSerializer()
    growth = serializers.DictField(
        child=MonthCountPointSerializer(many=True),
        help_text="``new_gyms_by_month`` / ``new_members_by_month`` chart series.",
    )
    window_months = serializers.IntegerField(help_text="Length of every per-month series.")
