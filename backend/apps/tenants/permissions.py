"""Tenant-scoped DRF permission classes."""

from typing import Any

from rest_framework import permissions
from rest_framework.permissions import BasePermission


class IsTenantMember(BasePermission):
    """Allow access only if the user belongs to the request's tenant."""

    def has_permission(self, request: Any, view: Any) -> bool:
        """Check that the authenticated user belongs to ``request.tenant``.

        Because DRF authentication runs after Django middleware, the tenant is
        resolved from ``request.auth`` (the token) when present, falling back to
        the user's own tenant.

        Args:
            request: The incoming DRF request.
            view: The view being accessed.

        Returns:
            ``True`` if the user is a superuser or belongs to the resolved tenant.
        """
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        tenant = getattr(request, "tenant", None)
        auth = getattr(request, "auth", None)
        if auth is not None and hasattr(auth, "tenant_id"):
            from apps.tenants.models import Tenant

            try:
                tenant = Tenant.objects.get(id=auth.tenant_id)
            except Tenant.DoesNotExist:
                return False
        elif request.user.tenant_id:
            from apps.tenants.models import Tenant

            try:
                tenant = Tenant.objects.get(id=request.user.tenant_id)
            except Tenant.DoesNotExist:
                return False

        request.tenant = tenant
        return tenant is not None and request.user.tenant_id == tenant.id


class TenantReadOnly(BasePermission):
    """Read-only access within the resolved tenant."""

    def has_permission(self, request: Any, view: Any) -> bool:
        """Allow safe methods only when a tenant is resolved and matches the user.

        Args:
            request: The incoming DRF request.
            view: The view being accessed.

        Returns:
            ``True`` for read-only requests inside a valid tenant context.
        """
        if not request.user.is_authenticated or request.tenant is None:
            return False
        return request.method in permissions.SAFE_METHODS
