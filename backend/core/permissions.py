from rest_framework.permissions import BasePermission


class IsTenantMember(BasePermission):
    """
    Allows access only if the user belongs to the request's tenant.
    Platform admins bypass this check.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.tenant is not None and request.user.tenant_id == request.tenant.id