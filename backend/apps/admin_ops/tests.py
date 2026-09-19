"""Admin ops tests (Sprint 10, issue #39)."""

from __future__ import annotations

from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token


class AdminTenantAPITests(APITestCase):
    """Superuser-only tenant listing with computed counts (issue #39)."""

    def setUp(self) -> None:
        """Create admin, regular owner, and two tenants."""
        self.admin = User.objects.create_superuser(
            email="root@fbos.test", password="pw123456!"
        )
        self.admin_token = issue_token(self.admin, None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        self.tenant = provision_tenant(name="Gym One", contact_email="owner1@gym.test")
        self.owner1 = create_owner_user(
            tenant=self.tenant,
            email="owner1@gym.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner One",
        )
        self.empty_tenant = provision_tenant(name="Gym Two", contact_email="owner2@gym.test")

    def _add_branch(self, tenant: Tenant, name: str) -> Branch:
        return Branch.objects.create(tenant=tenant, name=name, branch_type="gym")

    def _add_customer(self, tenant: Tenant, branch: Branch, email: str, phone: str) -> Customer:
        user = User.objects.create_user(
            email=email,
            password="pw123456!",
            first_name="C",
            last_name="X",
            role=User.Role.CUSTOMER,
            tenant=tenant,
        )
        return Customer.objects.create(
            tenant=tenant,
            branch=branch,
            user=user,
            name=f"Cust {email}",
            email=email,
            phone=phone,
        )

    def test_superuser_lists_tenants_with_counts(self) -> None:
        """Admin sees every tenant with correct member/branch counts."""
        branch = self._add_branch(self.tenant, "Main")
        self._add_customer(self.tenant, branch, "c1@gym.test", "+919999000001")
        self._add_customer(self.tenant, branch, "c2@gym.test", "+919999000002")

        response = self.client.get("/api/v1/admin/tenants/")
        assert response.status_code == 200

        results = response.data.get("results", response.data)
        rows = {r["name"]: r for r in results}
        assert rows["Gym One"]["member_count"] == 2
        assert rows["Gym One"]["branch_count"] == 1
        assert rows["Gym Two"]["member_count"] == 0
        assert rows["Gym Two"]["branch_count"] == 0

    def test_non_superuser_forbidden(self) -> None:
        """A regular owner cannot access the admin API."""
        token = issue_token(self.owner1, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/v1/admin/tenants/")
        assert response.status_code == 403

    def test_unauthenticated_unauthorized(self) -> None:
        """No credentials → 401."""
        self.client.credentials()
        response = self.client.get("/api/v1/admin/tenants/")
        assert response.status_code == 401

    def test_retrieve_single_tenant(self) -> None:
        """Admin can retrieve one tenant with counts."""
        branch = self._add_branch(self.tenant, "Main")
        self._add_customer(self.tenant, branch, "c1@gym.test", "+919999000001")
        response = self.client.get(f"/api/v1/admin/tenants/{self.tenant.pk}/")
        assert response.status_code == 200
        assert response.data["name"] == "Gym One"
        assert response.data["member_count"] == 1
        assert response.data["branch_count"] == 1
