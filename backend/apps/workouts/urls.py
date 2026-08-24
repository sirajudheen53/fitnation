"""Workouts app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.workouts.views import (
    WorkoutAssignmentViewSet,
    WorkoutDayViewSet,
    WorkoutExerciseViewSet,
    WorkoutLogViewSet,
    WorkoutPlanViewSet,
)

router = DefaultRouter()
router.register(r"workout-plans", WorkoutPlanViewSet, basename="workout-plan")
router.register(r"workout-days", WorkoutDayViewSet, basename="workout-day")
router.register(r"workout-exercises", WorkoutExerciseViewSet, basename="workout-exercise")
router.register(r"workout-assignments", WorkoutAssignmentViewSet, basename="workout-assignment")
router.register(r"workout-logs", WorkoutLogViewSet, basename="workout-log")

urlpatterns = [
    path("", include(router.urls)),
]
