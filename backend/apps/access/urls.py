"""Access app URL routing."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.access.views import (
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
    path("", include(router.urls)),
]
