"""Tenant resolution middleware."""

from typing import Any

from django.core.exceptions import PermissionDenied

from apps.tenants.models import Tenant


class TenantMiddleware:
    """Resolve the current tenant from authentication and attach it to the request."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        """Attach ``request.tenant`` for the remainder of the request lifecycle.

        Resolution priority:
        1. Token tenant (set by authentication backend on ``user._tenant_from_token``).
        2. Platform admin impersonation via ``?tenant_id=`` or ``X-Tenant-ID``.
        3. The authenticated user's own tenant.

        Args:
            request: The incoming Django request.

        Returns:
            The response produced by the next middleware / view.
        """
        request.tenant = None

        if not hasattr(request, "user") or not request.user.is_authenticated:
            return self.get_response(request)

        user = request.user

        if hasattr(user, "_tenant_from_token"):
            request.tenant = user._tenant_from_token
        elif user.is_superuser:
            tenant_id = request.GET.get("tenant_id") or request.headers.get(
                "X-Tenant-ID"
            )
            if tenant_id:
                try:
                    request.tenant = Tenant.objects.get(id=int(tenant_id))
                except (Tenant.DoesNotExist, ValueError) as exc:
                    raise PermissionDenied("Invalid tenant_id") from exc
        elif user.tenant_id:
            request.tenant = user.tenant

        return self.get_response(request)
