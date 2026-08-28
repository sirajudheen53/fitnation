"""Dashboard response serializers (FBOS-008).

These serializers are intentionally lightweight — they shape the aggregation
dictionaries returned by ``apps.dashboard.services`` into validated, documented
DRF responses.
"""

from __future__ import annotations

from rest_framework import serializers


class RevenueSummarySerializer(serializers.Serializer):
    """Total and this-month revenue for the overview payload."""

    total = serializers.FloatField(default=0.0)
    this_month = serializers.FloatField(default=0.0)


class OverviewSerializer(serializers.Serializer):
    """Top-level dashboard overview response."""

    total_members = serializers.IntegerField(default=0)
    active_memberships = serializers.IntegerField(default=0)
    revenue_summary = RevenueSummarySerializer()
    today_attendance = serializers.IntegerField(default=0)
    trainer_count = serializers.IntegerField(default=0)
    pending_payments = serializers.IntegerField(default=0)


class RevenuePointSerializer(serializers.Serializer):
    """A single revenue bucket in the time-series."""

    period = serializers.CharField()
    amount = serializers.FloatField(default=0.0)


class RevenueSerializer(serializers.Serializer):
    """Revenue breakdown response."""

    period = serializers.ChoiceField(
        choices=["daily", "weekly", "monthly"],
        default="monthly",
    )
    results = RevenuePointSerializer(many=True)


class PeakHourSerializer(serializers.Serializer):
    """A peak attendance hour bucket."""

    hour = serializers.IntegerField()
    count = serializers.IntegerField(default=0)


class WeeklyCountSerializer(serializers.Serializer):
    """Weekly check-in count bucket."""

    week = serializers.CharField()
    count = serializers.IntegerField(default=0)


class AttendanceSerializer(serializers.Serializer):
    """Attendance analytics response."""

    peak_hours = PeakHourSerializer(many=True)
    weekly_counts = WeeklyCountSerializer(many=True)


class MembershipStatusSerializer(serializers.Serializer):
    """Membership status counts."""

    active = serializers.IntegerField(default=0)
    expired = serializers.IntegerField(default=0)
    cancelled = serializers.IntegerField(default=0)


class PlanDistributionSerializer(serializers.Serializer):
    """A per-plan membership distribution bucket."""

    plan = serializers.CharField()
    plan_type = serializers.CharField()
    count = serializers.IntegerField(default=0)


class MembershipStatsSerializer(serializers.Serializer):
    """Membership stats response."""

    status_counts = MembershipStatusSerializer()
    plan_distribution = PlanDistributionSerializer(many=True)


class TrainerPerformanceSerializer(serializers.Serializer):
    """A single trainer performance row."""

    trainer_id = serializers.IntegerField()
    name = serializers.CharField()
    revenue = serializers.FloatField(default=0.0)
    rating_avg = serializers.FloatField(allow_null=True, default=None)
    client_count = serializers.IntegerField(default=0)
    sessions_completed = serializers.IntegerField(default=0)


class TrainerPerformanceResponseSerializer(serializers.Serializer):
    """Top trainers response."""

    results = TrainerPerformanceSerializer(many=True)
    total = serializers.IntegerField(default=0)


class PendingPaymentSerializer(serializers.Serializer):
    """A single pending payment row for the dashboard."""

    id = serializers.IntegerField()
    customer_name = serializers.CharField()
    amount = serializers.FloatField(default=0.0)
    due_date = serializers.CharField(allow_null=True, default=None)
