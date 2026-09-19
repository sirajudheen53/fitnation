"""Platform admin API views — cross-tenant, superuser only."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.admin_ops.selectors import list_tenants
from apps.admin_ops.serializers import TenantAdminSerializer
from apps.permissions.permissions import IsPlatformAdmin
from apps.users.authentication import TenantTokenAuthentication


class AdminTenantViewSet(ReadOnlyModelViewSet):
    """All tenants on the platform (issue #39).

    Superuser-only: no tenant scoping — the operator sees every gym.
    """

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    serializer_class = TenantAdminSerializer

    def get_queryset(self):
        """Return all tenants with counts, newest first."""
        return list_tenants()
