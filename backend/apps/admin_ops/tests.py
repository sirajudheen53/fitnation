"""Admin ops tests (Sprint 10, issue #39)."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.hashers import make_password
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token
from apps.vendors.models import SubscriptionPlan


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


class AdminOnboardGymTests(APITestCase):
    """Admin-driven gym provisioning (issue #40)."""

    def setUp(self) -> None:
        """Create admin, a subscription plan, and the onboarding payload."""
        self.admin = User.objects.create_superuser(email="root@fbos.test", password="pw123456!")
        self.admin_token = issue_token(self.admin, None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.plan = SubscriptionPlan.objects.create(
            code="starter",
            name="Starter",
            price_monthly=Decimal("999.00"),
            price_yearly=Decimal("9999.00"),
            max_branches=2,
            max_customers=100,
            max_trainers=5,
        )
        self.payload = {
            "gym_name": "Iron Temple",
            "contact_name": "Ravi Kumar",
            "owner_email": "owner@irontemple.test",
            "branch_name": "Main Branch",
            "plan_code": "starter",
        }

    def test_onboard_creates_tenant_owner_branch(self) -> None:
        """POST onboard → 201 with tenant, owner credentials, branch."""
        response = self.client.post("/api/v1/admin/tenants/onboard/", self.payload, format="json")
        assert response.status_code == 201
        assert response.data["tenant_name"] == "Iron Temple"
        assert response.data["owner_email"] == "owner@irontemple.test"
        assert len(response.data["owner_password"]) >= 16
        assert Tenant.objects.filter(name="Iron Temple").exists()

    def test_owner_can_login_with_generated_password(self) -> None:
        """The generated password works immediately on the login endpoint."""
        onboard = self.client.post("/api/v1/admin/tenants/onboard/", self.payload, format="json")
        password = onboard.data["owner_password"]
        login = self.client.post(
            "/api/v1/users/auth/login/",
            {"email": self.payload["owner_email"], "password": password},
            format="json",
        )
        assert login.status_code == 200
        assert login.data.get("token")

    def test_duplicate_owner_email_rejected(self) -> None:
        """Same owner email (case-insensitive) → 400."""
        self.client.post("/api/v1/admin/tenants/onboard/", self.payload, format="json")
        dup = {**self.payload, "gym_name": "Another Gym", "owner_email": self.payload["owner_email"].upper()}
        response = self.client.post("/api/v1/admin/tenants/onboard/", dup, format="json")
        assert response.status_code == 400
        assert "owner_email" in response.data

    def test_duplicate_gym_name_rejected(self) -> None:
        """Same gym name → 400."""
        self.client.post("/api/v1/admin/tenants/onboard/", self.payload, format="json")
        dup = {**self.payload, "owner_email": "other@irontemple.test"}
        response = self.client.post("/api/v1/admin/tenants/onboard/", dup, format="json")
        assert response.status_code == 400
        assert "gym_name" in response.data

    def test_unknown_plan_rejected(self) -> None:
        """Invalid plan code → 400."""
        response = self.client.post(
            "/api/v1/admin/tenants/onboard/", {**self.payload, "plan_code": "gold"}, format="json"
        )
        assert response.status_code == 400

    def test_non_superuser_forbidden(self) -> None:
        """A gym owner cannot onboard other gyms."""
        some_tenant = provision_tenant(name="Some Gym", contact_email="someowner@gym.test")
        owner = create_owner_user(
            tenant=some_tenant,
            email="someowner@gym.test",
            password_hash=make_password("pw123456!"),
            contact_name="S O",
        )
        token = issue_token(owner, some_tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post("/api/v1/admin/tenants/onboard/", self.payload, format="json")
        assert response.status_code == 403


class GymSuspensionTests(APITestCase):
    """Gym suspension and reactivation (issue #43)."""

    def setUp(self) -> None:
        """Create admin, an active tenant, and an owner with a real password."""
        self.admin = User.objects.create_superuser(email="root@fbos.test", password="pw123456!")
        self.admin_token = issue_token(self.admin, None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.tenant = provision_tenant(name="Suspend Gym", contact_email="owner@suspend.test")
        self.tenant.status = Tenant.Status.ACTIVE
        self.tenant.save(update_fields=["status"])
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@suspend.test",
            password_hash=make_password("pw123456!"),
            contact_name="Suspend Owner",
        )

    def _login(self):
        """POST the owner's credentials to the login endpoint."""
        return self.client.post(
            "/api/v1/users/auth/login/",
            {"email": "owner@suspend.test", "password": "pw123456!"},
            format="json",
        )

    def test_suspend_blocks_owner_login(self) -> None:
        """Suspending a gym rejects its owner's login with 403."""
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "suspended"}, format="json"
        )
        assert response.status_code == 200
        assert response.data["status"] == "suspended"
        assert self._login().status_code == 403

    def test_reactivate_restores_login(self) -> None:
        """Reactivation unblocks owner login."""
        self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "suspended"}, format="json"
        )
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "active"}, format="json"
        )
        assert response.status_code == 200
        assert response.data["status"] == "active"
        login = self._login()
        assert login.status_code == 200
        assert login.data["token"]

    def test_suspension_revokes_existing_tokens(self) -> None:
        """Tokens issued before suspension stop authenticating immediately."""
        owner_token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        assert self.client.get("/api/v1/users/auth/me/").status_code == 200

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "suspended"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        response = self.client.get("/api/v1/users/auth/me/")
        # 401, not 403: raised inside the authenticator, which advertises a
        # WWW-Authenticate challenge (DRF renders 403 only without one).
        assert response.status_code == 401
        assert response.data["detail"] == "Tenant is suspended"

    def test_invalid_status_rejected(self) -> None:
        """Only active/suspended are accepted via this endpoint."""
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "trial"}, format="json"
        )
        assert response.status_code == 400
        self.tenant.refresh_from_db()
        assert self.tenant.status == Tenant.Status.ACTIVE

    def test_non_admin_cannot_suspend(self) -> None:
        """A gym owner cannot suspend their own (or any) gym."""
        owner_token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "suspended"}, format="json"
        )
        assert response.status_code == 403


class AdminPlanManagementTests(APITestCase):
    """Subscription plan CRUD for platform admins (issue #44)."""

    def setUp(self) -> None:
        """Create admin token and one existing plan."""
        self.admin = User.objects.create_superuser(email="root@fbos.test", password="pw123456!")
        self.admin_token = issue_token(self.admin, None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.plan = SubscriptionPlan.objects.create(
            code="starter",
            name="Starter",
            price_monthly=Decimal("999.00"),
            price_yearly=Decimal("9999.00"),
            max_branches=2,
            max_customers=100,
            max_trainers=5,
            features={"whatsapp": False},
            sort_order=1,
        )

    def test_list_plans(self) -> None:
        """Admin lists the whole catalog including inactive plans."""
        SubscriptionPlan.objects.create(
            code="professional",
            name="Professional",
            price_monthly=Decimal("2499.00"),
            price_yearly=Decimal("24999.00"),
            max_branches=5,
            max_customers=1000,
            max_trainers=50,
            is_active=False,
        )
        response = self.client.get("/api/v1/admin/plans/")
        assert response.status_code == 200
        results = response.data.get("results", response.data)
        assert {plan["code"] for plan in results} == {"starter", "professional"}

    def test_retrieve_plan(self) -> None:
        """Admin retrieves a single plan."""
        response = self.client.get(f"/api/v1/admin/plans/{self.plan.pk}/")
        assert response.status_code == 200
        assert response.data["code"] == "starter"
        assert response.data["features"] == {"whatsapp": False}

    def test_create_plan(self) -> None:
        """Admin creates a plan with the full field set."""
        response = self.client.post(
            "/api/v1/admin/plans/",
            {
                "code": "enterprise",
                "name": "Enterprise",
                "price_monthly": "4999.00",
                "price_yearly": "49999.00",
                "max_branches": 50,
                "max_customers": 10000,
                "max_trainers": 500,
                "features": {"api": True},
                "sort_order": 3,
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.data["code"] == "enterprise"
        assert SubscriptionPlan.objects.filter(code="enterprise").exists()

    def test_create_duplicate_code_rejected(self) -> None:
        """Plan codes are unique."""
        response = self.client.post(
            "/api/v1/admin/plans/",
            {
                "code": "starter",
                "name": "Starter Again",
                "price_monthly": "1.00",
                "price_yearly": "10.00",
                "max_branches": 1,
                "max_customers": 10,
                "max_trainers": 1,
            },
            format="json",
        )
        assert response.status_code == 400

    def test_update_plan(self) -> None:
        """Admin patches pricing and limits."""
        response = self.client.patch(
            f"/api/v1/admin/plans/{self.plan.pk}/",
            {"price_monthly": "1299.00", "max_customers": 250},
            format="json",
        )
        assert response.status_code == 200
        self.plan.refresh_from_db()
        assert str(self.plan.price_monthly) == "1299.00"
        assert self.plan.max_customers == 250

    def test_delete_deactivates(self) -> None:
        """DELETE soft-deactivates; the row survives."""
        response = self.client.delete(f"/api/v1/admin/plans/{self.plan.pk}/")
        assert response.status_code == 200
        assert response.data["is_active"] is False
        self.plan.refresh_from_db()
        assert self.plan.is_active is False
        assert SubscriptionPlan.objects.filter(pk=self.plan.pk).exists()

    def test_non_admin_forbidden(self) -> None:
        """Gym owners cannot manage plans (list or create)."""
        tenant = provision_tenant(name="Plan Gym", contact_email="owner@plan.test")
        owner = create_owner_user(
            tenant=tenant,
            email="owner@plan.test",
            password_hash=make_password("pw123456!"),
            contact_name="Plan Owner",
        )
        owner_token = issue_token(owner, tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        assert self.client.get("/api/v1/admin/plans/").status_code == 403
        assert self.client.post("/api/v1/admin/plans/", {}, format="json").status_code == 403
