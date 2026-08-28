"""Inventory app URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.inventory.views import (
    EquipmentViewSet,
    InventoryItemViewSet,
    MaintenanceLogViewSet,
)

router = DefaultRouter()
router.register(r"equipment", EquipmentViewSet, basename="equipment")
router.register(r"inventory-items", InventoryItemViewSet, basename="inventory-item")
router.register(r"maintenance-logs", MaintenanceLogViewSet, basename="maintenance-log")

urlpatterns = [
    path("", include(router.urls)),
]
