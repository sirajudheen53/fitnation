"""Platform admin API views — cross-tenant, superuser only."""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.admin_ops.selectors import list_tenants
from apps.admin_ops.services import onboard_gym
from apps.admin_ops.serializers import (
    AdminOnboardGymSerializer,
    SubscriptionPlanAdminSerializer,
    TenantAdminSerializer,
    TenantStatusUpdateSerializer,
)
from apps.permissions.permissions import IsPlatformAdmin
from apps.users.authentication import TenantTokenAuthentication
from apps.vendors.models import SubscriptionPlan


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

    def partial_update(self, request: Any, pk: int | None = None) -> Response:
        """Suspend or reactivate a gym (issue #43).

        Suspension immediately blocks the gym's API tokens (see
        ``TenantTokenAuthentication``) and owner logins.
        """
        tenant = self.get_object()
        serializer = TenantStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant.status = serializer.validated_data["status"]
        tenant.save(update_fields=["status"])
        # Re-fetch through the annotated queryset so counts stay populated.
        tenant = list_tenants().get(pk=tenant.pk)
        return Response(TenantAdminSerializer(tenant).data)

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


class AdminPlanViewSet(ModelViewSet):
    """Subscription plan catalog management (issue #44).

    DELETE is a soft delete: it flips ``is_active`` so historical tenants
    keep a resolvable plan code.
    """

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    serializer_class = SubscriptionPlanAdminSerializer

    def get_queryset(self):
        """Return every plan (including inactive), catalog order."""
        return SubscriptionPlan.objects.all()

    def destroy(self, request: Any, pk: int | None = None) -> Response:
        """Deactivate a plan instead of deleting the row."""
        plan = self.get_object()
        plan.is_active = False
        plan.save(update_fields=["is_active"])
        return Response(SubscriptionPlanAdminSerializer(plan).data)
