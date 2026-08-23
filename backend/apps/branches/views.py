"""Branch API views."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.branches.models import Branch
from apps.branches.serializers import BranchSerializer
from apps.permissions.permissions import RolePermission
from apps.tenants.permissions import IsTenantMember
from apps.users.authentication import TenantTokenAuthentication


class BranchListCreateView(APIView):
    """List or create branches for the current tenant."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "branches.view_branch"
    method_permissions = {
        "GET": "branches.view_branch",
        "POST": "branches.create_branch",
    }

    def get(self, request: Request) -> Response:
        """List tenant branches."""
        branches = Branch.objects.for_tenant(request.tenant)
        serializer = BranchSerializer(branches, many=True)
        return Response(serializer.data)

    def post(self, request: Request) -> Response:
        """Create a new branch."""
        serializer = BranchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = serializer.save(tenant=request.tenant)
        return Response(BranchSerializer(branch).data, status=status.HTTP_201_CREATED)


class BranchRetrieveUpdateView(APIView):
    """Retrieve or update a tenant branch."""

    authentication_classes = [TenantTokenAuthentication]
    permission_classes = [IsAuthenticated, IsTenantMember, RolePermission]
    required_permission = "branches.view_branch"
    method_permissions = {
        "GET": "branches.view_branch",
        "PATCH": "branches.edit_branch",
        "PUT": "branches.edit_branch",
    }

    def get(self, request: Request, pk: int) -> Response:
        """Retrieve a branch."""
        try:
            branch = Branch.objects.for_tenant(request.tenant).get(id=pk)
        except Branch.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = BranchSerializer(branch)
        return Response(serializer.data)

    def patch(self, request: Request, pk: int) -> Response:
        """Update a branch."""
        try:
            branch = Branch.objects.for_tenant(request.tenant).get(id=pk)
        except Branch.DoesNotExist:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = BranchSerializer(branch, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
