from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.analytics.views import (
    AttendanceHeatmapViewSet,
    MembershipFunnelViewSet,
    RevenueReportViewSet,
    TopCustomersViewSet,
)

router = DefaultRouter()
router.register(r"revenue", RevenueReportViewSet, basename="analytics-revenue")
router.register(r"attendance/heatmap", AttendanceHeatmapViewSet, basename="analytics-heatmap")
router.register(r"memberships/funnel", MembershipFunnelViewSet, basename="analytics-funnel")
router.register(r"top-customers", TopCustomersViewSet, basename="analytics-topcustomers")

urlpatterns = [
    path("", include(router.urls)),
]
