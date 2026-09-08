"""Dashboard response serializers (FBOS-008).

These serializers shape the aggregation dictionaries returned by
``apps.dashboard.services`` into the contract defined by the frontend
(``frontend/src/types/dashboard.ts``).
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
    mrr = serializers.CharField()
    revenue_summary = RevenueSummarySerializer()
    today_attendance = serializers.IntegerField(default=0)
    trainer_count = serializers.IntegerField(default=0)
    pending_payments = serializers.IntegerField(default=0)


class RevenuePointSerializer(serializers.Serializer):
    """A single revenue bucket in a time-series."""

    label = serializers.CharField()
    amount = serializers.FloatField(default=0.0)


class RevenueSerializer(serializers.Serializer):
    """Revenue breakdown response — one series per period."""

    daily = RevenuePointSerializer(many=True)
    weekly = RevenuePointSerializer(many=True)
    monthly = RevenuePointSerializer(many=True)


class AttendancePointSerializer(serializers.Serializer):
    """An attendance chart point — ``hour`` carries the x-axis label."""

    hour = serializers.CharField()
    check_ins = serializers.IntegerField(default=0)


class AttendanceSerializer(serializers.Serializer):
    """Attendance analytics response."""

    peak_hours = AttendancePointSerializer(many=True)
    weekly_trend = AttendancePointSerializer(many=True)


class MembershipBreakdownSerializer(serializers.Serializer):
    """Membership status breakdown."""

    active = serializers.IntegerField(default=0)
    expired = serializers.IntegerField(default=0)
    cancelled = serializers.IntegerField(default=0)


class PlanDistributionSerializer(serializers.Serializer):
    """A per-plan membership distribution bucket."""

    plan = serializers.CharField()
    count = serializers.IntegerField(default=0)


class MembershipStatsSerializer(serializers.Serializer):
    """Membership stats response."""

    breakdown = MembershipBreakdownSerializer()
    plan_distribution = PlanDistributionSerializer(many=True)


class PendingPaymentSerializer(serializers.Serializer):
    """A single pending payment row for the dashboard."""

    id = serializers.IntegerField()
    customer_name = serializers.CharField()
    amount = serializers.FloatField(default=0.0)
    due_date = serializers.CharField(allow_null=True, default=None)
