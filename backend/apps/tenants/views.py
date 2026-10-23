"""Tenant API views."""

from typing import Any, ClassVar

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.permissions import RolePermission
from apps.tenants.features import apply_feature_overrides
from apps.tenants.models import Tenant
from apps.tenants.permissions import IsTenantMember
from apps.tenants.selectors import tenant_get_by_id
from apps.tenants.serializers import (
    TenantFeatureSettingsSerializer,
    TenantFeatureUpdateSerializer,
    TenantSerializer,
    WhatsappTestSendSerializer,
    tenant_feature_settings_payload,
)
from apps.tenants.services import (
    send_whatsapp_test,
    throttle_gym_lookup,
    whatsapp_status_counts,
)
from apps.users.authentication import TenantTokenAuthentication


def _client_ip(request: Any) -> str | None:
    """Client IP for rate limits (Cloud Run sets X-Forwarded-For)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR") or None


class TenantDetailView(APIView):
    """Retrieve current tenant details / update its WhatsApp config (owner/admin)."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "tenants.view_tenant"
    # Only gym owners / platform admins may change tenant settings; every other
    # role lacks "tenants.change_tenant" in RolePermission's matrix → 403.
    method_permissions: ClassVar[dict] = {"PATCH": "tenants.change_tenant"}

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

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    # Owner/platform-admin only (same gate as config changes).
    required_permission = "tenants.change_tenant"

    def post(self, request: Any) -> Response:
        """Handle ``{phone, provider?}`` and dispatch the welcome-template test message.

        ``provider`` (``wati`` default | ``gupshup``, issue #66/#67) selects
        the WhatsApp BSP under test — the chosen provider's own outcome is
        reported, never a fallback to the other one.

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
            provider=body.validated_data.get("provider", "wati"),
        )
        return Response({"status": log.status, "detail": log.error_message})


class WhatsappStatusView(APIView):
    """Today's WhatsApp usage counters for the settings page (FBOS-011 §6)."""

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "tenants.view_tenant"

    def get(self, request: Any) -> Response:
        """Return ``{otp_sent_today, invites_sent_today, daily_cap}``.

        Args:
            request: The incoming DRF request.

        Returns:
            Counters matching the frontend's ``WhatsappStatus`` interface.
        """
        return Response(whatsapp_status_counts(request.tenant))


class TenantFeatureSettingsView(APIView):
    """Gym-level module toggles (issue #46) — read + set ``Tenant.features``.

    ``GET`` returns every registered module flag resolved for the gym plus the
    settings-page catalog; every authenticated gym member may read it (the
    mobile/ERP use it to hide a disabled module's surface). ``PATCH`` merges
    ``{flags: {key: bool}}`` overrides and is owner/platform-admin only
    (``tenants.change_tenant``), mirroring the rest of the settings page.
    """

    authentication_classes: ClassVar[list] = [TenantTokenAuthentication]
    permission_classes: ClassVar[list] = [IsAuthenticated, IsTenantMember, RolePermission]
    method_permissions: ClassVar[dict] = {"PATCH": "tenants.change_tenant"}

    def get(self, request: Any) -> Response:
        """Return the resolved module-flag map and toggle catalog.

        Args:
            request: The incoming DRF request.

        Returns:
            ``{flags, catalog}`` (see ``TenantFeatureSettingsSerializer``).
        """
        payload = tenant_feature_settings_payload(request.tenant)
        return Response(TenantFeatureSettingsSerializer(payload).data)

    def patch(self, request: Any) -> Response:
        """Merge validated module-flag overrides into the gym's features.

        Args:
            request: The incoming DRF request.

        Returns:
            The refreshed ``{flags, catalog}`` payload after persistence.
        """
        body = TenantFeatureUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        tenant = request.tenant
        apply_feature_overrides(tenant, body.validated_data["flags"])
        tenant.save(update_fields=["features", "updated_at"])
        return Response(TenantFeatureSettingsSerializer(tenant_feature_settings_payload(tenant)).data)


class TenantLookupView(APIView):
    """Unauthenticated gym lookup by code for the mobile install flow.

    Serves members who install the app from Play without an invite link
    (FBOS-011): ``GET /api/v1/tenants/lookup/?code=CODE`` → ``{uuid, name}``.
    Public by necessity, hence IP-throttled; unknown or missing codes get the
    same generic 404 so the endpoint cannot be used to enumerate gyms.
    """

    authentication_classes: ClassVar[list[str]] = []
    permission_classes: ClassVar[list] = [AllowAny]

    def get(self, request: Any) -> Response:
        """Handle a code lookup.

        Args:
            request: The incoming DRF request.

        Returns:
            ``{uuid, name}`` for the gym, or a generic 404 / 429 response.
        """
        throttle_gym_lookup(_client_ip(request))
        # Codes are uppercase alphanumerics (safe alphabet); members type them
        # by hand, so strip spaces/punctuation before the exact match
        # ("hash fit", "px3-ctjy" → canonical form). Stored codes match as-is.
        raw = (request.query_params.get("code") or "").strip().upper()
        code = "".join(ch for ch in raw if ch.isalnum())
        if not code:
            return Response({"detail": "Gym not found."}, status=404)
        tenant = Tenant.objects.filter(gym_code=code).first()
        if tenant is None:
            return Response({"detail": "Gym not found."}, status=404)
        return Response({"uuid": str(tenant.uuid), "name": tenant.name})
