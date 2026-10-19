"""Platform admin API views — cross-tenant, superuser only."""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.admin_ops.selectors import list_tenants
from apps.admin_ops.services import impersonate_owner, onboard_gym, rotate_owner_credentials
from apps.admin_ops.serializers import (
    AdminOnboardGymSerializer,
    SubscriptionPlanAdminSerializer,
    TenantAdminSerializer,
    TenantAdminUpdateSerializer,
)
from apps.permissions.permissions import IsPlatformAdmin
from apps.tenants.models import Tenant
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

    def update(self, request: Any, pk: int | None = None) -> Response:
        """Edit gym details — name, contact, plan (platform gap fix).

        PUT requires ``name`` and ``contact_email``; the response is the
        annotated ``TenantAdminSerializer`` payload so member/branch counts
        stay populated.
        """
        tenant = self.get_object()
        serializer = TenantAdminUpdateSerializer(tenant, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        tenant = list_tenants().get(pk=tenant.pk)
        return Response(TenantAdminSerializer(tenant).data)

    def partial_update(self, request: Any, pk: int | None = None) -> Response:
        """Edit gym details or suspend/reactivate (issue #43) — fields optional.

        Suspension immediately blocks the gym's API tokens (see
        ``TenantTokenAuthentication``) and owner logins. Archiving a gym is
        done via DELETE, not by patching ``status``.
        """
        tenant = self.get_object()
        serializer = TenantAdminUpdateSerializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Re-fetch through the annotated queryset so counts stay populated.
        tenant = list_tenants().get(pk=tenant.pk)
        return Response(TenantAdminSerializer(tenant).data)

    @action(detail=True, methods=["post"], url_path="rotate-credentials")
    def rotate_credentials(self, request: Any, pk: int | None = None) -> Response:
        """Rotate the gym owner's password (platform gap fix).

        Generates a new password (returned exactly once, same contract as
        onboard) and deactivates all of the owner's active tokens so old
        credentials and sessions stop working immediately.
        """
        tenant = self.get_object()
        result = rotate_owner_credentials(tenant=tenant)
        return Response(
            {
                "owner_email": result["owner"].email,
                "owner_password": result["password"],
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request: Any, pk: int | None = None) -> Response:
        """Archive a gym (soft delete — platform gap fix).

        The row is never hard-deleted (branches, members, and tokens
        reference it): the status flips to ``archived``, which blocks owner
        logins and API tokens exactly like suspension. Archived gyms stay
        visible in the admin list.
        """
        tenant = self.get_object()
        tenant.status = Tenant.Status.ARCHIVED
        tenant.save(update_fields=["status"])
        tenant = list_tenants().get(pk=tenant.pk)
        return Response(TenantAdminSerializer(tenant).data)

    @action(detail=True, methods=["post"], url_path="impersonate")
    def impersonate(self, request: Any, pk: int | None = None) -> Response:
        """Start a short-lived session as the gym's owner (issue #45).

        The issued token expires in 30 minutes and the action is recorded
        in the impersonation audit log.
        """
        tenant = self.get_object()
        result = impersonate_owner(admin=request.user, tenant=tenant)
        return Response(
            {
                "token": result["token"].key,
                "expires_at": result["token"].expires_at,
                "owner_email": result["owner"].email,
            },
            status=status.HTTP_200_OK,
        )

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
