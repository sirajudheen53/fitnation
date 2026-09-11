"""Access control API views — biometric devices, credentials, overrides, logs."""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.access.models import (
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
)
from apps.access.selectors import get_customer_access_state
from apps.access.serializers import (
    AccessLogSerializer,
    AccessOverrideSerializer,
    BiometricCredentialSerializer,
    BiometricDeviceSerializer,
)
from apps.customers.models import Customer
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class BiometricDeviceViewSet(ModelViewSet):
    """Tenant-scoped biometric device registry."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "access.view_device"
    serializer_class = BiometricDeviceSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "serial_number", "model"]
    ordering_fields = ["name", "created_at", "last_seen_at"]
    ordering = ["-created_at"]

    def get_queryset(self) -> Any:
        """Return devices scoped to the request tenant."""
        queryset = BiometricDevice.objects.for_tenant(self.request.tenant)
        branch = self.request.query_params.get("branch")
        if branch:
            queryset = queryset.filter(branch_id=branch)
        return queryset.select_related("branch")

    def create(self, request: Request) -> Response:
        """Register a new biometric device."""
        self.required_permission = "access.create_device"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = serializer.save(tenant=request.tenant)
        return Response(
            BiometricDeviceSerializer(device).data,
            status=status.HTTP_201_CREATED,
        )


class BiometricCredentialViewSet(ModelViewSet):
    """Tenant-scoped credential enrollment."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "access.view_credential"
    serializer_class = BiometricCredentialSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    ordering = ["-enrolled_at"]

    def get_queryset(self) -> Any:
        """Return credentials scoped to the request tenant."""
        queryset = BiometricCredential.objects.for_tenant(self.request.tenant)
        device = self.request.query_params.get("device")
        if device:
            queryset = queryset.filter(device_id=device)
        customer = self.request.query_params.get("customer")
        if customer:
            queryset = queryset.filter(customer_id=customer)
        return queryset.select_related("device", "customer")

    def create(self, request: Request) -> Response:
        """Enroll a credential on a device."""
        self.required_permission = "access.create_credential"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.save(tenant=request.tenant)
        return Response(
            BiometricCredentialSerializer(credential).data,
            status=status.HTTP_201_CREATED,
        )


class AccessOverrideViewSet(ModelViewSet):
    """Owner access override management."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "access.view_override"
    serializer_class = AccessOverrideSerializer
    filter_backends = [OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self) -> Any:
        """Return overrides scoped to the request tenant."""
        queryset = AccessOverride.objects.for_tenant(self.request.tenant)
        device = self.request.query_params.get("device")
        if device:
            queryset = queryset.filter(device_id=device)
        customer = self.request.query_params.get("customer")
        if customer:
            queryset = queryset.filter(customer_id=customer)
        return queryset.select_related("device", "customer", "created_by")

    def create(self, request: Request) -> Response:
        """Create an owner override."""
        self.required_permission = "access.create_override"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        override = serializer.save(
            tenant=request.tenant,
            created_by=request.user,
        )
        return Response(
            AccessOverrideSerializer(override).data,
            status=status.HTTP_201_CREATED,
        )


class AccessLogViewSet(ReadOnlyModelViewSet):
    """Read-only access event log viewer."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "access.view_log"
    serializer_class = AccessLogSerializer
    filter_backends = [OrderingFilter]
    ordering = ["-event_timestamp"]

    def get_queryset(self) -> Any:
        """Return logs scoped to the request tenant."""
        queryset = AccessLog.objects.for_tenant(self.request.tenant)
        device = self.request.query_params.get("device")
        if device:
            queryset = queryset.filter(device_id=device)
        customer = self.request.query_params.get("customer")
        if customer:
            queryset = queryset.filter(customer_id=customer)
        return queryset.select_related("device", "customer")

    @action(detail=False, methods=["get"], url_path="check")
    def check_access(self, request: Request) -> Response:
        """Evaluate whether a customer is allowed at a device right now.

        Query params: customer_id, device_id (both required).
        """
        customer_id = request.query_params.get("customer_id")
        device_id = request.query_params.get("device_id")
        if not customer_id or not device_id:
            return Response(
                {"detail": "customer_id and device_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer = __import__("apps.customers.models", fromlist=["Customer"]).objects.filter(
            pk=customer_id, tenant=request.tenant
        ).first()
        device = BiometricDevice.objects.filter(
            pk=device_id, tenant=request.tenant
        ).first()
        if not customer or not device:
            return Response(
                {"detail": "Customer or device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        result = get_customer_access_state(customer=customer, device=device)
        return Response(result, status=status.HTTP_200_OK)
