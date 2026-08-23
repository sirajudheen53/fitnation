"""Tests for the branches app."""

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.branches.models import Branch, BranchAmenity
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, create_user, issue_token


class BranchModelTests(TestCase):
    """Unit tests for branch models and tenant isolation."""

    def setUp(self) -> None:
        """Create two isolated tenants."""
        self.tenant_a = provision_tenant(name="Gym A", contact_email="a@local.test")
        self.tenant_b = provision_tenant(name="Gym B", contact_email="b@local.test")

    def test_branch_requires_tenant(self) -> None:
        """Saving a branch without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            Branch.objects.create(name="Orphan Branch", address_line1="Address")

    def test_branch_name_unique_within_tenant(self) -> None:
        """Branch names are unique within a tenant but reusable across tenants."""
        Branch.objects.create(
            tenant=self.tenant_a,
            name="Main Branch",
            address_line1="MG Road",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Branch.objects.create(
                tenant=self.tenant_a,
                name="Main Branch",
                address_line1="Other Road",
            )
        Branch.objects.create(
            tenant=self.tenant_b,
            name="Main Branch",
            address_line1="MG Road B",
        )

    def test_for_tenant_isolation(self) -> None:
        """Tenant A cannot see Tenant B's branches."""
        Branch.objects.create(tenant=self.tenant_a, name="A Branch", address_line1="A")
        Branch.objects.create(tenant=self.tenant_b, name="B Branch", address_line1="B")

        a_branches = Branch.objects.for_tenant(self.tenant_a)
        b_branches = Branch.objects.for_tenant(self.tenant_b)

        self.assertEqual(a_branches.count(), 1)
        self.assertEqual(b_branches.count(), 1)
        self.assertEqual(a_branches.first().name, "A Branch")
        self.assertEqual(b_branches.first().name, "B Branch")

    def test_branch_amenity_unique_within_branch(self) -> None:
        """Amenity names are unique per branch."""
        branch = Branch.objects.create(
            tenant=self.tenant_a,
            name="Main Branch",
            address_line1="MG Road",
        )
        BranchAmenity.objects.create(branch=branch, name="Parking")
        with self.assertRaises(IntegrityError), transaction.atomic():
            BranchAmenity.objects.create(branch=branch, name="Parking")


class BranchAPITests(APITestCase):
    """Integration tests for branch management endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, and auth token."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_create_branch(self) -> None:
        """Owners can create a branch."""
        response = self.client.post(
            "/api/v1/branches/",
            {
                "name": "Kochi Main",
                "branch_type": "main",
                "address_line1": "MG Road",
                "city": "Kochi",
                "state": "Kerala",
                "postal_code": "682011",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Kochi Main")

    def test_list_branches_tenant_scoped(self) -> None:
        """Branch list is filtered to the authenticated user's tenant."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        Branch.objects.create(
            tenant=self.tenant, name="Owned Branch", address_line1="A"
        )
        Branch.objects.create(
            tenant=other_tenant, name="Other Branch", address_line1="B"
        )

        response = self.client.get("/api/v1/branches/")
        self.assertEqual(response.status_code, 200)
        names = {b["name"] for b in response.data}
        self.assertIn("Owned Branch", names)
        self.assertNotIn("Other Branch", names)

    def test_retrieve_branch(self) -> None:
        """Owners can retrieve branch details."""
        branch = Branch.objects.create(
            tenant=self.tenant,
            name="Kochi Main",
            address_line1="MG Road",
        )
        response = self.client.get(f"/api/v1/branches/{branch.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Kochi Main")

    def test_update_branch(self) -> None:
        """Owners can update branch details."""
        branch = Branch.objects.create(
            tenant=self.tenant,
            name="Old Name",
            address_line1="MG Road",
        )
        response = self.client.patch(
            f"/api/v1/branches/{branch.id}/",
            {"name": "New Name"},
        )
        self.assertEqual(response.status_code, 200)
        branch.refresh_from_db()
        self.assertEqual(branch.name, "New Name")

    def test_cross_tenant_branch_access_blocked(self) -> None:
        """Owners cannot access branches belonging to another tenant."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        branch = Branch.objects.create(
            tenant=other_tenant,
            name="Other Branch",
            address_line1="Other Road",
        )
        response = self.client.get(f"/api/v1/branches/{branch.id}/")
        self.assertEqual(response.status_code, 404)

    def test_manager_can_view_branches(self) -> None:
        """A manager can list branches with the view permission."""
        Branch.objects.create(tenant=self.tenant, name="Main", address_line1="A")
        manager = create_user(
            tenant=self.tenant,
            email="manager@local.test",
            first_name="Manager",
            last_name="One",
            role=User.Role.MANAGER,
        )
        token = issue_token(manager, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get("/api/v1/branches/")
        self.assertEqual(response.status_code, 200)

    def test_manager_cannot_create_branch(self) -> None:
        """A manager lacks permission to create branches."""
        manager = create_user(
            tenant=self.tenant,
            email="manager@local.test",
            first_name="Manager",
            last_name="One",
            role=User.Role.MANAGER,
        )
        token = issue_token(manager, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post(
            "/api/v1/branches/",
            {
                "name": "Unauthorized Branch",
                "address_line1": "Road",
                "city": "City",
                "state": "State",
                "postal_code": "000000",
            },
        )
        self.assertEqual(response.status_code, 403)
