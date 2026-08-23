"""Customers app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.customers.views import (
    BodyMeasurementViewSet,
    CustomerViewSet,
    FitnessGoalViewSet,
    HealthProfileViewSet,
)

router = DefaultRouter()
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"health-profiles", HealthProfileViewSet, basename="health-profile")
router.register(r"fitness-goals", FitnessGoalViewSet, basename="fitness-goal")
router.register(
    r"body-measurements",
    BodyMeasurementViewSet,
    basename="body-measurement",
)

urlpatterns = [
    path("", include(router.urls)),
]
