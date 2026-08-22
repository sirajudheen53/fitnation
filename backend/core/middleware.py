from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin
from core.models import Tenant


class TenantMiddleware(MiddlewareMixin):
    """
    Resolves the current tenant from the authenticated user's tenant_id.
    Platform admins (superusers) can optionally pass ?tenant_id= to impersonate.

    Sets: request.tenant = Tenant instance (or None for platform admin without impersonation)
    """

    def process_request(self, request):
        request.tenant = None

        if hasattr(request, "user") and request.user.is_authenticated:
            if request.user.is_superuser:
                # Platform admin — can optionally impersonate a tenant
                tenant_id = request.GET.get("tenant_id")
                if tenant_id:
                    try:
                        request.tenant = Tenant.objects.get(id=tenant_id)
                    except Tenant.DoesNotExist:
                        raise PermissionDenied("Invalid tenant_id")
            elif request.user.tenant_id:
                request.tenant = request.user.tenant