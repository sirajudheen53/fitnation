"""Access app URL routing."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.access.views import (
    AccessCheckView,
    AccessEventIngestView,
    AccessLogViewSet,
    AccessOverrideViewSet,
    BiometricCredentialViewSet,
    BiometricDeviceViewSet,
)

router = DefaultRouter()
router.register("devices", BiometricDeviceViewSet, basename="access-devices")
router.register("credentials", BiometricCredentialViewSet, basename="access-credentials")
router.register("overrides", AccessOverrideViewSet, basename="access-overrides")
router.register("logs", AccessLogViewSet, basename="access-logs")

app_name = "access"

urlpatterns = [
    # Rule-engine check with decision audit log (issue #19).
    path("check/", AccessCheckView.as_view(), name="access-check"),
    # Device event ingestion with attendance auto-creation (issue #21).
    path("events/", AccessEventIngestView.as_view(), name="access-events"),
    path("", include(router.urls)),
]