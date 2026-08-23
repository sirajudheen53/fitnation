"""Attendance app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.attendance.views import (
    AttendanceRecordViewSet,
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
    path("", include(router.urls)),
]
