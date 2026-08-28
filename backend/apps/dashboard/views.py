"""Dashboard API views (FBOS-008)."""

from __future__ import annotations

from typing import ClassVar

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard import services
from apps.dashboard.serializers import (
    AttendanceSerializer,
    MembershipStatsSerializer,
    OverviewSerializer,
    PendingPaymentSerializer,
    RevenueSerializer,
    TrainerPerformanceResponseSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class DashboardBaseView(APIView):
    """Shared auth/permission configuration for dashboard endpoints."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [
        IsAuthenticated,
        IsTenantMember,
        RolePermission,
    ]
    required_permission = "dashboard.view_dashboard"

    def get_tenant(self):
        """Return the tenant scoped from the request."""
        return getattr(self.request, "tenant", None)


class DashboardOverviewView(DashboardBaseView):
    """GET overview/ — top-level dashboard metrics for the tenant."""

    def get(self, request):
        """Return the serialized overview payload."""
        tenant = self.get_tenant()
        data = services.get_overview(tenant)
        return Response(OverviewSerializer(data).data)


class DashboardRevenueView(DashboardBaseView):
    """GET revenue/?period=daily|weekly|monthly — revenue time-series."""

    def get(self, request):
        """Return the revenue breakdown for the requested period."""
        tenant = self.get_tenant()
        period = request.query_params.get("period", "monthly")
        data = services.get_revenue_breakdown(tenant, period)
        return Response(RevenueSerializer(data).data)


class DashboardAttendanceView(DashboardBaseView):
    """GET attendance/ — peak hours and weekly attendance analytics."""

    def get(self, request):
        """Return attendance analytics for the tenant."""
        tenant = self.get_tenant()
        data = services.get_attendance_analytics(tenant)
        return Response(AttendanceSerializer(data).data)


class DashboardMembershipsView(DashboardBaseView):
    """GET memberships/ — membership status and plan distribution."""

    def get(self, request):
        """Return membership stats for the tenant."""
        tenant = self.get_tenant()
        data = services.get_membership_stats(tenant)
        return Response(MembershipStatsSerializer(data).data)


class DashboardTrainersView(DashboardBaseView):
    """GET trainers/ — top trainers ranked by revenue/rating/client count."""

    def get(self, request):
        """Return trainer performance for the tenant."""
        tenant = self.get_tenant()
        data = services.get_trainer_performance(tenant)
        return Response(TrainerPerformanceResponseSerializer(data).data)


class DashboardPendingPaymentsView(DashboardBaseView):
    """GET pending-payments/ — pending payments with customer and due date."""

    def get(self, request):
        """Return pending payments for the tenant."""
        tenant = self.get_tenant()
        data = services.get_pending_payments(tenant)
        return Response(PendingPaymentSerializer(data, many=True).data)
