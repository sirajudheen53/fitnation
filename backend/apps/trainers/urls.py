"""Trainers app URL configuration (FBOS-007)."""

from rest_framework.routers import DefaultRouter

from apps.trainers.views import (
    TrainerAssignmentViewSet,
    TrainerPerformanceViewSet,
    TrainerScheduleViewSet,
    TrainerViewSet,
)

router = DefaultRouter()
router.register(r"trainers", TrainerViewSet, basename="trainer")
router.register(r"trainer-assignments", TrainerAssignmentViewSet, basename="trainer-assignment")
router.register(r"trainer-performance", TrainerPerformanceViewSet, basename="trainer-performance")
router.register(r"trainer-schedules", TrainerScheduleViewSet, basename="trainer-schedule")

urlpatterns = router.urls
