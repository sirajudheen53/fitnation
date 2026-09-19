"""Platform admin API views — cross-tenant, superuser only."""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.admin_ops.selectors import list_tenants
from apps.admin_ops.services import onboard_gym
from apps.admin_ops.serializers import AdminOnboardGymSerializer, TenantAdminSerializer
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

    @action(detail=False, methods=["post"], url_path="onboard")
    def onboard_gym(self, request: Any) -> Response:
        """Provision a gym instantly — no email verification (issue #40).

        Returns the generated owner password exactly once for handover.
        """
        serializer = AdminOnboardGymSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = onboard_gym(**serializer.validated_data)
        return Response(
            {
                "tenant_id": result["tenant"].id,
                "tenant_name": result["tenant"].name,
                "owner_email": result["owner"].email,
                "owner_password": result["password"],
                "branch_name": result["branch"].name,
                "plan_code": result["tenant"].subscription_plan,
            },
            status=status.HTTP_201_CREATED,
        )
