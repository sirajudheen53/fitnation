"""Tests for the permissions app and RBAC matrix."""

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.permissions.models import Permission, Role, RolePermission
from apps.permissions.permissions import (
    IsPlatformAdmin,
)
from apps.permissions.permissions import RolePermission as RolePermissionClass
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, create_user, issue_token


class RoleAndPermissionModelTests(TestCase):
    """Unit tests for Role, Permission, and RolePermission models."""

    def test_system_role_code_unique(self) -> None:
        """System roles must have globally unique codes."""
        Role.objects.create(
            code="platform_admin",
            name="Platform Admin",
            is_system_role=True,
            is_tenant_custom=False,
        )
        with self.assertRaises(Exception):
            Role.objects.create(
                code="platform_admin",
                name="Duplicate",
                is_system_role=True,
                is_tenant_custom=False,
            )

    def test_permission_unique_by_app_action_resource(self) -> None:
        """Permissions are unique by app, action, and resource."""
        Permission.objects.create(
            code="branches.create_branch",
            name="Create branch",
            app_label="branches",
            action="create",
            resource="branch",
        )
        with self.assertRaises(Exception):
            Permission.objects.create(
                code="branches.create_branch_2",
                name="Duplicate permission",
                app_label="branches",
                action="create",
                resource="branch",
            )

    def test_role_permission_unique(self) -> None:
        """RolePermission mappings are unique by role and permission."""
        role = Role.objects.create(code="manager", name="Manager")
        perm = Permission.objects.create(
            code="branches.view_branch",
            name="View branch",
            app_label="branches",
            action="view",
            resource="branch",
        )
        RolePermission.objects.create(role=role, permission=perm)
        with self.assertRaises(Exception):
            RolePermission.objects.create(role=role, permission=perm)


class RolePermissionMatrixTests(TestCase):
    """Tests for the static role-permission matrix."""

    def test_gym_owner_wildcard(self) -> None:
        """Gym owners are granted wildcard access."""
        perm_class = RolePermissionClass()
        request = self._build_request(role=User.Role.GYM_OWNER)
        view = type("View", (), {"required_permission": "branches.delete_branch"})()
        self.assertTrue(perm_class.has_permission(request, view))

    def test_manager_limited_permissions(self) -> None:
        """Managers can view branches but not delete them."""
        perm_class = RolePermissionClass()
        request = self._build_request(role=User.Role.MANAGER)

        view_create = type("View", (), {"required_permission": "branches.create_branch"})()
        view_view = type("View", (), {"required_permission": "branches.view_branch"})()

        self.assertFalse(perm_class.has_permission(request, view_create))
        self.assertTrue(perm_class.has_permission(request, view_view))

    def test_customer_cannot_view_branches(self) -> None:
        """Customers do not have branch access."""
        perm_class = RolePermissionClass()
        request = self._build_request(role=User.Role.CUSTOMER)
        view = type("View", (), {"required_permission": "branches.view_branch"})()
        self.assertFalse(perm_class.has_permission(request, view))

    def test_object_level_tenant_isolation(self) -> None:
        """Users cannot access objects from another tenant."""
        tenant_a = provision_tenant(name="A", contact_email="a@local.test")
        tenant_b = provision_tenant(name="B", contact_email="b@local.test")
        owner_a = create_owner_user(
            tenant=tenant_a,
            email="owner@local.test",
            password_hash="hashed",
            contact_name="Owner",
        )
        branch_b = Branch.objects.create(
            tenant=tenant_b,
            name="B Branch",
            address_line1="B",
        )

        perm_class = RolePermissionClass()
        request = self._build_request(role=User.Role.GYM_OWNER, tenant=tenant_a, user=owner_a)
        view = type("View", (), {"required_permission": "branches.view_branch"})()
        self.assertFalse(perm_class.has_object_permission(request, view, branch_b))

    def test_platform_admin_detection(self) -> None:
        """IsPlatformAdmin returns True only for superusers."""
        admin = User.objects.create_superuser(
            email="admin@local.test",
            password="F1tNati0n!",
            first_name="Admin",
            last_name="User",
        )
        request = self._build_request(user=admin)
        self.assertTrue(IsPlatformAdmin().has_permission(request, None))

    def _build_request(
        self,
        role: str = User.Role.CUSTOMER,
        tenant: object | None = None,
        user: User | None = None,
    ) -> object:
        """Build a minimal request-like object for permission checks."""
        if user is None:
            user = User.objects.create_user(
                email=f"{role}@local.test",
                password="F1tNati0n!",
                first_name="Test",
                last_name="User",
                role=role,
            )
            user.tenant = tenant
        return type("Request", (), {"user": user})()


class RBACAPITests(APITestCase):
    """Integration tests for role-based access on API endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, and branch for access tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="hashed",
            contact_name="Owner User",
        )
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="MG Road",
        )

    def test_owner_can_create_branch(self) -> None:
        """Gym owners can create branches."""
        token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(
            "/api/v1/branches/",
            {
                "name": "New Branch",
                "address_line1": "Street",
                "city": "City",
                "state": "State",
                "postal_code": "000000",
            },
        )
        self.assertEqual(response.status_code, 201)

    def test_customer_cannot_list_branches(self) -> None:
        """Customers are denied branch access."""
        customer = create_user(
            tenant=self.tenant,
            email="customer@local.test",
            first_name="Customer",
            last_name="One",
            role=User.Role.CUSTOMER,
            branch_id=self.branch.id,
        )
        token = issue_token(customer, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/v1/branches/")
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_request_rejected(self) -> None:
        """Requests without a token are rejected."""
        self.client.credentials()
        response = self.client.get("/api/v1/branches/")
        self.assertEqual(response.status_code, 401)
