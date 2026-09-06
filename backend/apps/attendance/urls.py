"""Attendance app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.attendance.views import (
    AttendanceRecordViewSet,
    AttendanceStatsView,
    CheckInView,
    TrainerAttendanceViewSet,
)

router = DefaultRouter()
router.register(r"attendance", AttendanceRecordViewSet, basename="attendance")
router.register(
    r"trainer-attendance",
    TrainerAttendanceViewSet,
    basename="trainer-attendance",
)

urlpatterns = [
    path("check-in/", CheckInView.as_view(), name="attendance-check-in"),
    path("stats/", AttendanceStatsView.as_view(), name="attendance-stats"),
    path("", include(router.urls)),
]
