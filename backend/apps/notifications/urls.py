"""Notifications app URL configuration.

Mounted at ``api/v1/notifications/`` from the root URL config, so paths here are
relative to that prefix (e.g. ``logs/`` → ``api/v1/notifications/logs/``).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.notifications.views import (
    NotificationLogViewSet,
    NotificationSettingsView,
    NotificationTestView,
)

router = DefaultRouter()
router.register(r"logs", NotificationLogViewSet, basename="notification-log")

urlpatterns = [
    path("", include(router.urls)),
    path("settings/", NotificationSettingsView.as_view(), name="notification-settings"),
    path("test/", NotificationTestView.as_view(), name="notification-test"),
]
