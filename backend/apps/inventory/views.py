"""Equipment & inventory API views."""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.inventory.models import Equipment, InventoryItem, MaintenanceLog
from apps.inventory.serializers import (
    EquipmentSerializer,
    InventoryItemSerializer,
    MaintenanceLogSerializer,
)
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class EquipmentViewSet(ModelViewSet):
    """Tenant-scoped equipment CRUD viewset."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "inventory.view_equipment"
    serializer_class = EquipmentSerializer

    def get_queryset(self):
        """Return equipment scoped to the request tenant."""
        return Equipment.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new equipment record."""
        self.required_permission = "inventory.create_equipment"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        equipment = serializer.save(tenant=request.tenant)
        return Response(
            EquipmentSerializer(equipment).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args, **kwargs) -> Response:
        """Update an equipment record."""
        self.required_permission = "inventory.edit_equipment"
        return super().update(request, *args, **kwargs)

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        """Partially update an equipment record."""
        self.required_permission = "inventory.edit_equipment"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """Delete an equipment record."""
        self.required_permission = "inventory.delete_equipment"
        return super().destroy(request, *args, **kwargs)


class InventoryItemViewSet(ModelViewSet):
    """Tenant-scoped inventory item CRUD viewset."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "inventory.view_inventory"
    serializer_class = InventoryItemSerializer

    def get_queryset(self):
        """Return inventory items scoped to the request tenant."""
        return InventoryItem.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new inventory item."""
        self.required_permission = "inventory.create_inventory"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(tenant=request.tenant)
        return Response(
            InventoryItemSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args, **kwargs) -> Response:
        """Update an inventory item."""
        self.required_permission = "inventory.edit_inventory"
        return super().update(request, *args, **kwargs)

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        """Partially update an inventory item."""
        self.required_permission = "inventory.edit_inventory"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """Delete an inventory item."""
        self.required_permission = "inventory.delete_inventory"
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def low_stock(self, request: Request) -> Response:
        """Return inventory items below their low-stock threshold.

        Only items with ``track_inventory=True`` and
        ``stock_quantity <= low_stock_threshold`` are returned.
        """
        self.required_permission = "inventory.view_inventory"
        queryset = self.get_queryset().filter(track_inventory=True)
        low_stock_items = [
            item for item in queryset if item.is_low_stock
        ]
        page = self.paginate_queryset(low_stock_items)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(low_stock_items, many=True)
        return Response(serializer.data)


class MaintenanceLogViewSet(ModelViewSet):
    """Tenant-scoped maintenance log CRUD viewset."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "inventory.view_equipment"
    serializer_class = MaintenanceLogSerializer

    def get_queryset(self):
        """Return maintenance logs scoped to the request tenant."""
        return MaintenanceLog.objects.for_tenant(self.request.tenant)

    def create(self, request: Request) -> Response:
        """Create a new maintenance log."""
        self.required_permission = "inventory.create_equipment"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = serializer.save(tenant=request.tenant)
        return Response(
            MaintenanceLogSerializer(log).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request: Request, *args, **kwargs) -> Response:
        """Update a maintenance log."""
        self.required_permission = "inventory.edit_equipment"
        return super().update(request, *args, **kwargs)

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        """Partially update a maintenance log."""
        self.required_permission = "inventory.edit_equipment"
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """Delete a maintenance log."""
        self.required_permission = "inventory.delete_equipment"
        return super().destroy(request, *args, **kwargs)
