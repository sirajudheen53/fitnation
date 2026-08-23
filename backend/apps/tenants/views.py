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
    """Retrieve current tenant details."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "tenants.view_tenant"

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
