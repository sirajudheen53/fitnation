"""AI Nutrition app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.ai_nutrition.views import (
    AIMealPlanViewSet,
    MacroLogViewSet,
    ShoppingListViewSet,
)

router = DefaultRouter()
router.register(r"nutrition/meal-plan", AIMealPlanViewSet, basename="ai-meal-plan")
router.register(r"nutrition/shopping-list", ShoppingListViewSet, basename="ai-shopping-list")
router.register(r"nutrition/track", MacroLogViewSet, basename="ai-macro-log")

urlpatterns = [
    path("ai/", include(router.urls)),
]
