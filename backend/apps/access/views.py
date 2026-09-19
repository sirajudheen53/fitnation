"""Access control API views — biometric devices, credentials, overrides, logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.access.adapters import AdapterError, get_adapter
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
    BiometricCredentialEnrollResultSerializer,
    BiometricCredentialEnrollSerializer,
    BiometricCredentialSerializer,
    BiometricDeviceSerializer,
    DeviceConnectionTestResultSerializer,
    DeviceEventsFetchResultSerializer,
    DeviceSyncResultSerializer,
)
from apps.access.services import (
    decide_and_log,
    enroll_credential,
    fetch_device_events,
    ingest_event,
    sync_device,
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

    ACTION_PERMISSIONS = {
        "test_connection": "customers.edit_customer",
        "sync": "customers.edit_customer",
        "enroll": "customers.edit_customer",
        # fetch-events is read-oriented: viewers may pull events too.
        "fetch_events": ("customers.edit_customer", "customers.view_customer"),
    }

    def get_permissions(self) -> list:
        """Apply action-specific permission strings before checks run.

        RolePermission reads ``required_permission`` while evaluating
        permissions (before the handler), so per-action overrides must
        happen here rather than inside the action methods.
        """
        required = self.ACTION_PERMISSIONS.get(self.action)
        if required is not None:
            self.required_permission = required
        return super().get_permissions()

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request: Request, pk: int | None = None) -> Response:  # noqa: ARG002
        """Run the vendor adapter connection test against this device."""
        device = self.get_object()
        try:
            result = get_adapter(device).test_connection(device)
        except AdapterError as exc:
            result = {"online": False, "detail": str(exc)}
        if result.get("online"):
            # Adapter already stamped last_seen_at; a successful round-trip
            # also refreshes last_sync_at per the issue #22 contract.
            device.last_sync_at = timezone.now()
            device.save(update_fields=["last_seen_at", "last_sync_at", "updated_at"])
        return Response(
            DeviceConnectionTestResultSerializer(result).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request: Request, pk: int | None = None) -> Response:
        """Force an allow-list sync for this device now."""
        device = self.get_object()
        result = sync_device(device)
        return Response(DeviceSyncResultSerializer(result).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="enroll")
    def enroll(self, request: Request) -> Response:
        """Enroll a credential on a device and immediately sync that device."""
        serializer = BiometricCredentialEnrollSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        device = serializer.validated_data["device"]
        credential = enroll_credential(
            tenant=request.tenant,
            device=device,
            customer=serializer.validated_data["customer"],
            credential_type=serializer.validated_data["credential_type"],
            device_user_id=serializer.validated_data["device_user_id"],
        )
        sync_result = sync_device(device)
        return Response(
            BiometricCredentialEnrollResultSerializer(
                {"credential": credential, "sync": sync_result}
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="fetch-events")
    def fetch_events(self, request: Request, pk: int | None = None) -> Response:
        """Pull access events from this device and record them as logs.

        Optional query param: ``since`` (ISO-8601 timestamp).
        """
        device = self.get_object()
        since = None
        since_param = request.query_params.get("since")
        if since_param:
            try:
                since = datetime.fromisoformat(since_param.replace("Z", "+00:00"))
            except ValueError:
                return Response(
                    {"detail": "since must be an ISO-8601 timestamp."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        result = fetch_device_events(device=device, since=since)
        return Response(
            DeviceEventsFetchResultSerializer(result).data,
            status=status.HTTP_200_OK,
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


class AccessCheckView(APIView):
    """GET /api/v1/access/check/ — rule-engine evaluation with audit log.

    Query params: ``customer_id`` and ``device_id`` (both required).
    Every call persists an :class:`~apps.access.models.AccessDecisionLog`
    row so gyms can audit why a member was granted or denied entry (#19).
    """

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request: Request) -> Response:
        """Evaluate and log the access decision for a customer + device."""
        customer_id = request.query_params.get("customer_id")
        device_id = request.query_params.get("device_id")
        if not customer_id or not device_id:
            return Response(
                {"detail": "customer_id and device_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer = Customer.objects.filter(pk=customer_id, tenant=request.tenant).first()
        device = BiometricDevice.objects.filter(pk=device_id, tenant=request.tenant).first()
        if customer is None or device is None:
            return Response(
                {"detail": "Customer or device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        result = decide_and_log(customer=customer, device=device)
        return Response(result, status=status.HTTP_200_OK)


class AccessEventIngestView(APIView):
    """POST /api/v1/access/events/ — device event ingestion (issue #21).

    Accepts events pushed by device bridges/adapters, resolves the
    customer from the device's credential map, records the access log
    (idempotent), and auto-creates an attendance check-in on entry.
    """

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request: Request) -> Response:
        """Ingest one access event."""
        device_id = request.data.get("device_id")
        device_user_id = request.data.get("device_user_id")
        event_type = request.data.get("event_type")
        raw_ts = request.data.get("event_timestamp")
        if not device_id or not device_user_id or not event_type or not raw_ts:
            return Response(
                {"detail": "device_id, device_user_id, event_type, event_timestamp are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        device = BiometricDevice.objects.filter(pk=device_id, tenant=request.tenant).first()
        if device is None:
            return Response(
                {"detail": "Device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        ts = parse_datetime(str(raw_ts)) if isinstance(raw_ts, str) else raw_ts
        if ts is None:
            return Response(
                {"detail": "event_timestamp must be an ISO-8601 datetime."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if timezone.is_naive(ts):
            ts = timezone.make_aware(ts)
        try:
            result = ingest_event(
                device=device,
                device_user_id=str(device_user_id),
                event_type=event_type,
                event_timestamp=ts,
                credential_type=request.data.get("credential_type", "fingerprint"),
                raw_payload=request.data.get("raw_payload"),
            )
        except AdapterError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "duplicate": result["duplicate"],
                "customer_id": result["log"].customer_id,
                "event_type": result["log"].event_type,
                "attendance_created": result["attendance_created"],
            },
            status=status.HTTP_200_OK if result["duplicate"] else status.HTTP_201_CREATED,
        )
