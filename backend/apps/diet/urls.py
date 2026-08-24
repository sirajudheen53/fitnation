"""Diet app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.diet.views import (
    DietAssignmentViewSet,
    DietDayViewSet,
    DietMealViewSet,
    DietPlanViewSet,
    FoodItemViewSet,
)

router = DefaultRouter()
router.register(r"food-items", FoodItemViewSet, basename="food-item")
router.register(r"diet-plans", DietPlanViewSet, basename="diet-plan")
router.register(r"diet-days", DietDayViewSet, basename="diet-day")
router.register(r"diet-meals", DietMealViewSet, basename="diet-meal")
router.register(r"diet-assignments", DietAssignmentViewSet, basename="diet-assignment")

urlpatterns = [
    path("", include(router.urls)),
]
