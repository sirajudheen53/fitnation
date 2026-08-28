"""Analytics API viewsets (FBOS-030).

Each viewset provides read-only ``list`` (GET) endpoints that serve pre-computed
aggregates stored in the analytics models. All querysets are tenant-scoped via the
``for_tenant`` manager and paginated through DRF's default pagination.
"""

from typing import ClassVar

from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.analytics.models import (
    AttendanceHeatmap,
    MembershipFunnel,
    RevenueReport,
    TopCustomer,
)
from apps.analytics.serializers import (
    AttendanceHeatmapSerializer,
    MembershipFunnelSerializer,
    RevenueReportSerializer,
    TopCustomerSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class AnalyticsBaseViewSet(ReadOnlyModelViewSet):
    """Shared auth/permission configuration for analytics endpoints."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [
        IsAuthenticated,
        IsTenantMember,
        RolePermission,
    ]
    required_permission = "reports.view_report"


class RevenueReportViewSet(AnalyticsBaseViewSet):
    """Read-only revenue report endpoint (``/revenue/``)."""

    serializer_class = RevenueReportSerializer

    def get_queryset(self):
        """Return revenue reports scoped to the request tenant."""
        return RevenueReport.objects.for_tenant(self.request.tenant)


class AttendanceHeatmapViewSet(AnalyticsBaseViewSet):
    """Read-only attendance heatmap endpoint (``/attendance/heatmap/``)."""

    serializer_class = AttendanceHeatmapSerializer

    def get_queryset(self):
        """Return attendance heatmap rows scoped to the request tenant."""
        return AttendanceHeatmap.objects.for_tenant(self.request.tenant)


class MembershipFunnelViewSet(AnalyticsBaseViewSet):
    """Read-only membership funnel endpoint (``/memberships/funnel/``)."""

    serializer_class = MembershipFunnelSerializer

    def get_queryset(self):
        """Return membership funnel rows scoped to the request tenant."""
        return MembershipFunnel.objects.for_tenant(self.request.tenant)


class TopCustomersViewSet(AnalyticsBaseViewSet):
    """Read-only top customers endpoint (``/top-customers/``)."""

    serializer_class = TopCustomerSerializer

    def get_queryset(self):
        """Return top customers scoped to the request tenant."""
        return TopCustomer.objects.for_tenant(self.request.tenant)
