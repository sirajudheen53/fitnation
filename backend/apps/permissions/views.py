"""Permissions API views."""

from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class UserPermissionsView(APIView):
    """Return the permission list for the authenticated user."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request: Any) -> Response:
        """Return the list of permissions available to the current user.

        Args:
            request: The incoming DRF request.

        Returns:
            JSON array of permission codes.
        """
        matrix = RolePermission.ROLE_PERMISSION_MATRIX
        perms = matrix.get(request.user.role, set())
        if perms == "*":
            return Response({"permissions": ["*"]})
        return Response({"permissions": sorted(perms)})
