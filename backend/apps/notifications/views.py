"""Notification API views."""

from typing import Any, ClassVar

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.notifications.models import NotificationLog
from apps.notifications.serializers import (
    NotificationLogSerializer,
    TestNotificationSerializer,
    WatiSettingsSerializer,
)
from apps.notifications.services.wati_service import send_notification
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class NotificationLogViewSet(ReadOnlyModelViewSet):
    """List notification logs scoped to the tenant."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "reports.view_report"
    serializer_class = NotificationLogSerializer

    def get_queryset(self) -> NotificationLog:
        """Return logs scoped to the request tenant with optional filters."""
        queryset = NotificationLog.objects.for_tenant(self.request.tenant)
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        type_param = self.request.query_params.get("notification_type")
        if type_param:
            queryset = queryset.filter(notification_type=type_param)
        customer = self.request.query_params.get("customer")
        if customer:
            queryset = queryset.filter(customer_id=customer)
        return queryset


class NotificationSettingsView(APIView):
    """Read/update the tenant's Wati settings."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "reports.view_report"

    def get(self, request: Request) -> Response:
        """Return the current Wati configuration (masked api key)."""
        tenant = request.tenant
        return Response(
            {
                "is_wati_enabled": tenant.is_wati_enabled,
                "wati_endpoint": tenant.wati_endpoint,
                "wati_api_key_configured": bool(tenant.wati_api_key),
            }
        )

    def patch(self, request: Request) -> Response:
        """Update the tenant's Wati configuration (owner/admin only)."""
        self.required_permission = "reports.edit_report"
        serializer = WatiSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant = request.tenant
        if "wati_api_key" in data:
            tenant.wati_api_key = data["wati_api_key"]
        if "wati_endpoint" in data:
            tenant.wati_endpoint = data["wati_endpoint"]
        if "is_wati_enabled" in data:
            tenant.is_wati_enabled = data["is_wati_enabled"]
        tenant.save()

        return Response(
            {
                "is_wati_enabled": tenant.is_wati_enabled,
                "wati_endpoint": tenant.wati_endpoint,
                "wati_api_key_configured": bool(tenant.wati_api_key),
            }
        )


class NotificationTestView(APIView):
    """Send a test WhatsApp message to verify Wati connectivity."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "reports.view_report"

    def post(self, request: Request) -> Response:
        """Dispatch a test notification and report the outcome."""
        serializer = TestNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Simulate a lightweight customer so the log can capture a recipient.
        from apps.customers.models import Customer

        customer = Customer.objects.filter(tenant=request.tenant).first()
        context: dict[str, Any] = {
            "gym_name": request.tenant.name,
            "customer_name": data.get("to", customer.name if customer else "there"),
            "expiry_date": "",
            "plan_name": "Test Plan",
            "amount": "0",
        }

        log = send_notification(
            request.tenant,
            customer,
            data["notification_type"],
            context,
        )
        return Response(
            {
                "status": log.status,
                "wati_message_id": log.wati_message_id,
                "error_message": log.error_message,
                "content": log.content,
            },
            status=(
                status.HTTP_200_OK
                if log.status in (NotificationLog.Status.SENT, NotificationLog.Status.SKIPPED)
                else status.HTTP_400_BAD_REQUEST
            ),
        )
