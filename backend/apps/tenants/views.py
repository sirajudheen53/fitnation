"""Tenant API views."""

from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.tenants.selectors import tenant_get_by_id
from apps.tenants.serializers import TenantSerializer
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
