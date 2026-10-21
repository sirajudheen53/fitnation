"""Tenant API views."""

from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.tenants.selectors import tenant_get_by_id
from apps.tenants.serializers import TenantSerializer, WhatsappTestSendSerializer
from apps.tenants.services import send_whatsapp_test, whatsapp_status_counts
from apps.users.authentication import TenantTokenAuthentication


class TenantDetailView(APIView):
    """Retrieve current tenant details / update its WhatsApp config (owner/admin)."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "tenants.view_tenant"
    # Only gym owners / platform admins may change tenant settings; every other
    # role lacks "tenants.change_tenant" in RolePermission's matrix → 403.
    method_permissions = {"PATCH": "tenants.change_tenant"}

    def get(self, request: Any) -> Response:
        """Return the tenant associated with the current request.

        Args:
            request: The incoming DRF request.

        Returns:
            Serialized tenant payload.
        """
        tenant = tenant_get_by_id(request.tenant.id)
        serializer = TenantSerializer(tenant)
        return Response(serializer.data)

    def patch(self, request: Any) -> Response:
        """Save the tenant's WhatsApp configuration.

        The ``wati_api_key`` is write-only: omitted or blank keeps the stored
        secret, while a non-blank value replaces it (encrypted at rest).

        Args:
            request: The incoming DRF request.

        Returns:
            The refreshed tenant payload (same shape as ``GET``).
        """
        tenant = tenant_get_by_id(request.tenant.id)
        serializer = TenantSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TenantSerializer(tenant_get_by_id(tenant.id)).data)


class WhatsappTestSendView(APIView):
    """Send a settings-page test message through the tenant's WATI config.

    Always resolves to a non-500 outcome for the UI: not-enabled / not-
    configured / provider errors come back as 200 with the logged status and
    a human-readable detail (the attempt is recorded in ``NotificationLog``).
    """

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    # Owner/platform-admin only (same gate as config changes).
    required_permission = "tenants.change_tenant"

    def post(self, request: Any) -> Response:
        """Handle ``{phone}`` and dispatch the welcome-template test message.

        Args:
            request: The incoming DRF request.

        Returns:
            ``{status, detail}`` matching the frontend's ``WhatsappTestResult``.
        """
        body = WhatsappTestSendSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        log = send_whatsapp_test(
            request.tenant,
            body.validated_data["phone"],
            actor=request.user,
        )
        return Response({"status": log.status, "detail": log.error_message})


class WhatsappStatusView(APIView):
    """Today's WhatsApp usage counters for the settings page (FBOS-011 §6)."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "tenants.view_tenant"

    def get(self, request: Any) -> Response:
        """Return ``{otp_sent_today, invites_sent_today, daily_cap}``.

        Args:
            request: The incoming DRF request.

        Returns:
            Counters matching the frontend's ``WhatsappStatus`` interface.
        """
        return Response(whatsapp_status_counts(request.tenant))
