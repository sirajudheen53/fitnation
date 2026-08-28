"""Analytics serializers (FBOS-030)."""

from rest_framework import serializers

from apps.analytics.models import (
    AttendanceHeatmap,
    MembershipFunnel,
    RevenueReport,
    TopCustomer,
)


class RevenueReportSerializer(serializers.ModelSerializer):
    """Serialize a revenue report row."""

    class Meta:
        """Serializer metadata."""

        model = RevenueReport
        fields = ["period", "amount"]


class AttendanceHeatmapSerializer(serializers.ModelSerializer):
    """Serialize an attendance heatmap row."""

    class Meta:
        """Serializer metadata."""

        model = AttendanceHeatmap
        fields = ["date", "count"]


class MembershipFunnelSerializer(serializers.ModelSerializer):
    """Serialize a membership funnel row."""

    class Meta:
        """Serializer metadata."""

        model = MembershipFunnel
        fields = ["stage", "count"]


class TopCustomerSerializer(serializers.ModelSerializer):
    """Serialize a top customer row."""

    class Meta:
        """Serializer metadata."""

        model = TopCustomer
        fields = ["customer_id", "total_spent"]
