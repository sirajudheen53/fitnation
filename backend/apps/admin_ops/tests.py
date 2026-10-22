"""Admin ops tests (Sprint 10, issue #39)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.access.models import BiometricDevice
from apps.admin_ops.models import ImpersonationLog
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.payments.models import Payment
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.auth import AuthToken
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token
from apps.vendors.models import SubscriptionPlan


class AdminTenantAPITests(APITestCase):
    """Superuser-only tenant listing with computed counts (issue #39)."""

    def setUp(self) -> None:
        """Create admin, regular owner, and two tenants."""
        self.admin = User.objects.create_superuser(email="root@fbos.test", password="pw123456!")
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
        response = self.client.patch(f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "suspended"}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "suspended"
        assert self._login().status_code == 403

    def test_reactivate_restores_login(self) -> None:
        """Reactivation unblocks owner login."""
        self.client.patch(f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "suspended"}, format="json")
        response = self.client.patch(f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "active"}, format="json")
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
        self.client.patch(f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "suspended"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        response = self.client.get("/api/v1/users/auth/me/")
        # 401, not 403: raised inside the authenticator, which advertises a
        # WWW-Authenticate challenge (DRF renders 403 only without one).
        assert response.status_code == 401
        assert response.data["detail"] == "Tenant is suspended"

    def test_invalid_status_rejected(self) -> None:
        """Only active/suspended are accepted via this endpoint."""
        response = self.client.patch(f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "trial"}, format="json")
        assert response.status_code == 400
        self.tenant.refresh_from_db()
        assert self.tenant.status == Tenant.Status.ACTIVE

    def test_non_admin_cannot_suspend(self) -> None:
        """A gym owner cannot suspend their own (or any) gym."""
        owner_token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        response = self.client.patch(f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "suspended"}, format="json")
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


class ImpersonationTests(APITestCase):
    """Admin impersonation of gym owners (issue #45)."""

    def setUp(self) -> None:
        """Create admin, tenant, and its owner."""
        self.admin = User.objects.create_superuser(email="root@fbos.test", password="pw123456!")
        self.admin_token = issue_token(self.admin, None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.tenant = provision_tenant(name="Impersonate Gym", contact_email="owner@imp.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@imp.test",
            password_hash=make_password("pw123456!"),
            contact_name="Imp Owner",
        )

    def test_admin_impersonates_owner(self) -> None:
        """The issued token authenticates as the gym owner and is audited."""
        response = self.client.post(f"/api/v1/admin/tenants/{self.tenant.pk}/impersonate/", format="json")
        assert response.status_code == 200
        assert response.data["owner_email"] == "owner@imp.test"
        assert response.data["token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
        me = self.client.get("/api/v1/users/auth/me/")
        assert me.status_code == 200
        assert me.data["user"]["email"] == "owner@imp.test"
        assert me.data["user"]["tenant_id"] == self.tenant.pk

        assert ImpersonationLog.objects.filter(admin=self.admin, owner=self.owner, tenant=self.tenant).exists()

    def test_impersonation_token_expires_in_30_minutes(self) -> None:
        """The token carries a ~30 minute absolute expiry."""
        from django.utils import timezone as dj_timezone

        before = dj_timezone.now()
        response = self.client.post(f"/api/v1/admin/tenants/{self.tenant.pk}/impersonate/", format="json")
        after = dj_timezone.now()
        expires_at = response.data["expires_at"]
        assert (before + timedelta(minutes=30)) <= expires_at <= (after + timedelta(minutes=30))

    def test_tenant_without_owner_returns_404(self) -> None:
        """A gym with no owner user cannot be impersonated."""
        orphan = provision_tenant(name="No Owner Gym", contact_email="x@noowner.test")
        response = self.client.post(f"/api/v1/admin/tenants/{orphan.pk}/impersonate/", format="json")
        assert response.status_code == 404

    def test_non_admin_forbidden(self) -> None:
        """A gym owner cannot impersonate anyone."""
        owner_token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        response = self.client.post(f"/api/v1/admin/tenants/{self.tenant.pk}/impersonate/", format="json")
        assert response.status_code == 403


class GymEditTests(APITestCase):
    """Admin edit of gym details — name, contact, plan (platform gap fix)."""

    def setUp(self) -> None:
        """Create admin, two plans, an active tenant, and its owner."""
        self.admin = User.objects.create_superuser(email="root@fbos.test", password="pw123456!")
        self.admin_token = issue_token(self.admin, None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        SubscriptionPlan.objects.create(
            code="starter",
            name="Starter",
            price_monthly=Decimal("999.00"),
            price_yearly=Decimal("9999.00"),
            max_branches=2,
            max_customers=100,
            max_trainers=5,
        )
        SubscriptionPlan.objects.create(
            code="professional",
            name="Professional",
            price_monthly=Decimal("2499.00"),
            price_yearly=Decimal("24999.00"),
            max_branches=5,
            max_customers=1000,
            max_trainers=50,
        )
        self.tenant = provision_tenant(name="Edit Gym", contact_email="owner@edit.test")
        self.tenant.status = Tenant.Status.ACTIVE
        self.tenant.save(update_fields=["status"])
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@edit.test",
            password_hash=make_password("pw123456!"),
            contact_name="Edit Owner",
        )

    def test_patch_updates_details(self) -> None:
        """PATCH updates name and phone; status is untouched."""
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/",
            {"name": "Renamed Gym", "contact_phone": "+919999000009"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["name"] == "Renamed Gym"
        assert response.data["contact_phone"] == "+919999000009"
        self.tenant.refresh_from_db()
        assert self.tenant.name == "Renamed Gym"
        assert self.tenant.status == Tenant.Status.ACTIVE

    def test_patch_plan_to_valid_code(self) -> None:
        """PATCH switches the subscription plan to a valid plan code."""
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/",
            {"subscription_plan": "professional"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["subscription_plan"] == "professional"
        self.tenant.refresh_from_db()
        assert self.tenant.subscription_plan == "professional"

    def test_patch_invalid_plan_rejected(self) -> None:
        """Unknown plan code → 400; the current plan is unchanged."""
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/",
            {"subscription_plan": "gold"},
            format="json",
        )
        assert response.status_code == 400
        assert "subscription_plan" in response.data
        self.tenant.refresh_from_db()
        assert self.tenant.subscription_plan == "starter"

    def test_duplicate_contact_email_rejected(self) -> None:
        """A contact_email already used by another gym → 400."""
        other = provision_tenant(name="Other Gym", contact_email="other@edit.test")
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/",
            {"contact_email": other.contact_email},
            format="json",
        )
        assert response.status_code == 400
        assert "contact_email" in response.data

    def test_keep_own_contact_email_allowed(self) -> None:
        """Resubmitting the gym's own contact email passes (self excluded)."""
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/",
            {"contact_email": "owner@edit.test"},
            format="json",
        )
        assert response.status_code == 200

    def test_contact_email_normalized_to_lowercase(self) -> None:
        """Contact emails are lowercased like onboarding does."""
        response = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/",
            {"contact_email": "Owner@Edit.Test"},
            format="json",
        )
        assert response.status_code == 200
        self.tenant.refresh_from_db()
        assert self.tenant.contact_email == "owner@edit.test"

    def test_suspend_then_edit(self) -> None:
        """Suspension and editing compose: a suspended gym stays suspended."""
        suspended = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/", {"status": "suspended"}, format="json"
        )
        assert suspended.status_code == 200
        edited = self.client.patch(
            f"/api/v1/admin/tenants/{self.tenant.pk}/", {"name": "Suspended Rename"}, format="json"
        )
        assert edited.status_code == 200
        assert edited.data["status"] == "suspended"
        self.tenant.refresh_from_db()
        assert self.tenant.name == "Suspended Rename"
        assert self.tenant.status == Tenant.Status.SUSPENDED

    def test_put_full_update(self) -> None:
        """PUT replaces the editable fields (name/contact required)."""
        response = self.client.put(
            f"/api/v1/admin/tenants/{self.tenant.pk}/",
            {
                "name": "Put Gym",
                "contact_email": "newowner@edit.test",
                "contact_phone": "+919999000010",
                "subscription_plan": "professional",
            },
            format="json",
        )
        assert response.status_code == 200
        self.tenant.refresh_from_db()
        assert self.tenant.name == "Put Gym"
        assert self.tenant.contact_email == "newowner@edit.test"
        assert self.tenant.subscription_plan == "professional"

    def test_counts_populated_after_edit(self) -> None:
        """The response keeps annotated member/branch counts."""
        branch = Branch.objects.create(tenant=self.tenant, name="Main", branch_type="gym")
        user = User.objects.create_user(
            email="c1@edit.test",
            password="pw123456!",
            first_name="C",
            last_name="X",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        Customer.objects.create(
            tenant=self.tenant,
            branch=branch,
            user=user,
            name="Cust One",
            email="c1@edit.test",
            phone="+919999000011",
        )
        response = self.client.patch(f"/api/v1/admin/tenants/{self.tenant.pk}/", {"name": "Counted Gym"}, format="json")
        assert response.status_code == 200
        assert response.data["member_count"] == 1
        assert response.data["branch_count"] == 1

    def test_non_admin_forbidden(self) -> None:
        """A gym owner cannot edit their own gym via the admin API."""
        owner_token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        response = self.client.patch(f"/api/v1/admin/tenants/{self.tenant.pk}/", {"name": "Hacked"}, format="json")
        assert response.status_code == 403


class RotateOwnerCredentialsTests(APITestCase):
    """Owner credential rotation — lost-password recovery (platform gap fix)."""

    def setUp(self) -> None:
        """Create admin, an active tenant, and its owner with a known password."""
        self.admin = User.objects.create_superuser(email="root@fbos.test", password="pw123456!")
        self.admin_token = issue_token(self.admin, None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.tenant = provision_tenant(name="Rotate Gym", contact_email="owner@rotate.test")
        self.tenant.status = Tenant.Status.ACTIVE
        self.tenant.save(update_fields=["status"])
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@rotate.test",
            password_hash=make_password("old-pass-123!"),
            contact_name="Rotate Owner",
        )

    def _rotate(self):
        """POST the rotate-credentials action."""
        return self.client.post(f"/api/v1/admin/tenants/{self.tenant.pk}/rotate-credentials/", format="json")

    def _login(self, password: str):
        """POST the owner's credentials to the login endpoint."""
        return self.client.post(
            "/api/v1/users/auth/login/",
            {"email": "owner@rotate.test", "password": password},
            format="json",
        )

    def test_rotate_returns_one_time_password(self) -> None:
        """The response carries the owner email and a generated password."""
        response = self._rotate()
        assert response.status_code == 200
        assert response.data["owner_email"] == "owner@rotate.test"
        assert len(response.data["owner_password"]) >= 16

    def test_new_password_logs_in(self) -> None:
        """The rotated password works on the login endpoint immediately."""
        password = self._rotate().data["owner_password"]
        login = self._login(password)
        assert login.status_code == 200
        assert login.data["token"]

    def test_old_password_rejected(self) -> None:
        """The pre-rotation password stops working."""
        self._rotate()
        assert self._login("old-pass-123!").status_code == 403

    def test_old_owner_token_rejected(self) -> None:
        """Tokens issued before rotation stop authenticating immediately."""
        owner_token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        assert self.client.get("/api/v1/users/auth/me/").status_code == 200

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self._rotate()

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        response = self.client.get("/api/v1/users/auth/me/")
        assert response.status_code == 401
        assert response.data["detail"] == "Invalid or expired token"

    def test_all_owner_tokens_deactivated(self) -> None:
        """Every active AuthToken row for the owner is deactivated."""
        web_token = issue_token(self.owner, self.tenant, device_type="web")
        mobile_token = issue_token(self.owner, self.tenant, device_type="android")
        self._rotate()
        assert not AuthToken.objects.filter(user=self.owner, is_active=True).exists()
        web_token.refresh_from_db()
        mobile_token.refresh_from_db()
        assert web_token.is_active is False
        assert mobile_token.is_active is False

    def test_password_hashed_in_db(self) -> None:
        """The plaintext is never persisted — only a working hash is stored."""
        from django.contrib.auth.hashers import check_password, identify_hasher

        password = self._rotate().data["owner_password"]
        self.owner.refresh_from_db()
        assert self.owner.password != password
        # Stored value must parse as a Django password hash (test settings
        # use md5; production uses pbkdf2 — identify_hasher accepts both).
        assert identify_hasher(self.owner.password) is not None
        assert check_password(password, self.owner.password)

    def test_password_never_logged(self) -> None:
        """The plaintext password does not appear in any log output."""

        class Capture(logging.Handler):
            """Collect every log record emitted during the request."""

            def __init__(self) -> None:
                super().__init__(level=logging.DEBUG)
                self.records: list[logging.LogRecord] = []

            def emit(self, record: logging.LogRecord) -> None:
                self.records.append(record)

        capture = Capture()
        root = logging.getLogger()
        root.addHandler(capture)
        previous_level = root.level
        root.setLevel(logging.DEBUG)
        try:
            response = self._rotate()
        finally:
            root.removeHandler(capture)
            root.setLevel(previous_level)

        password = response.data["owner_password"]
        emitted = " ".join(record.getMessage() for record in capture.records)
        assert password not in emitted

    def test_tenant_without_owner_returns_404(self) -> None:
        """A gym with no owner user has nothing to rotate."""
        orphan = provision_tenant(name="No Rotate Gym", contact_email="x@norotate.test")
        response = self.client.post(f"/api/v1/admin/tenants/{orphan.pk}/rotate-credentials/", format="json")
        assert response.status_code == 404

    def test_non_admin_forbidden(self) -> None:
        """A gym owner cannot rotate their own credentials."""
        owner_token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        assert self._rotate().status_code == 403


class ArchiveGymTests(APITestCase):
    """Gym archive (soft delete) — platform gap fix."""

    def setUp(self) -> None:
        """Create admin, an active tenant with data, and its owner."""
        self.admin = User.objects.create_superuser(email="root@fbos.test", password="pw123456!")
        self.admin_token = issue_token(self.admin, None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.tenant = provision_tenant(name="Archive Gym", contact_email="owner@archive.test")
        self.tenant.status = Tenant.Status.ACTIVE
        self.tenant.save(update_fields=["status"])
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@archive.test",
            password_hash=make_password("pw123456!"),
            contact_name="Archive Owner",
        )

    def _delete(self):
        """DELETE the tenant (archive)."""
        return self.client.delete(f"/api/v1/admin/tenants/{self.tenant.pk}/")

    def test_delete_archives_and_returns_payload(self) -> None:
        """DELETE flips the status to archived and returns the payload."""
        response = self._delete()
        assert response.status_code == 200
        assert response.data["status"] == "archived"
        assert response.data["name"] == "Archive Gym"
        self.tenant.refresh_from_db()
        assert self.tenant.status == Tenant.Status.ARCHIVED
        assert Tenant.objects.filter(pk=self.tenant.pk).exists()

    def test_archived_owner_token_rejected(self) -> None:
        """Tokens stop authenticating once the gym is archived."""
        owner_token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        assert self.client.get("/api/v1/users/auth/me/").status_code == 200

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self._delete()

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        response = self.client.get("/api/v1/users/auth/me/")
        assert response.status_code == 401
        assert response.data["detail"] == "Tenant is archived"

    def test_archived_owner_login_blocked(self) -> None:
        """The owner cannot log in to an archived gym."""
        self._delete()
        response = self.client.post(
            "/api/v1/users/auth/login/",
            {"email": "owner@archive.test", "password": "pw123456!"},
            format="json",
        )
        assert response.status_code == 403

    def test_archived_tenant_still_listed(self) -> None:
        """Archived gyms remain visible in the admin list."""
        self._delete()
        response = self.client.get("/api/v1/admin/tenants/")
        assert response.status_code == 200
        results = response.data.get("results", response.data)
        rows = {r["name"]: r for r in results}
        assert rows["Archive Gym"]["status"] == "archived"

    def test_archive_keeps_data(self) -> None:
        """No hard delete: branches/members survive and counts stay populated."""
        branch = Branch.objects.create(tenant=self.tenant, name="Main", branch_type="gym")
        user = User.objects.create_user(
            email="c1@archive.test",
            password="pw123456!",
            first_name="C",
            last_name="X",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        Customer.objects.create(
            tenant=self.tenant,
            branch=branch,
            user=user,
            name="Cust One",
            email="c1@archive.test",
            phone="+919999000012",
        )
        response = self._delete()
        assert response.status_code == 200
        assert response.data["branch_count"] == 1
        assert response.data["member_count"] == 1
        assert Branch.objects.filter(tenant=self.tenant).count() == 1
        assert Customer.objects.filter(tenant=self.tenant).count() == 1

    def test_non_admin_cannot_archive(self) -> None:
        """A gym owner cannot archive their own gym."""
        owner_token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {owner_token.key}")
        response = self._delete()
        assert response.status_code == 403
        self.tenant.refresh_from_db()
        assert self.tenant.status == Tenant.Status.ACTIVE


class PlatformStatsTests(APITestCase):
    """Platform-wide stats endpoint (issue #47) — superuser only."""

    stats_url = "/api/v1/admin/stats/"

    def setUp(self) -> None:
        """Create the platform admin and its token."""
        self.admin = User.objects.create_superuser(email="root@fbos.test", password="pw123456!")
        self.admin_token = issue_token(self.admin, None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.today = timezone.localdate()

    def _aware_day_start(self, day: datetime.date) -> datetime.datetime:
        """Timezone-aware midnight of a date (test-local tz)."""
        return timezone.make_aware(datetime.combine(day, datetime.min.time()))

    def _owner(self, tenant: Tenant, email: str) -> User:
        """Create an owner user for a tenant."""
        return create_owner_user(
            tenant=tenant,
            email=email,
            password_hash="pbkdf2_sha256$hashed",
            contact_name="O",
        )

    def _member(self, tenant: Tenant, branch: Branch, email: str) -> Customer:
        """Create a customer (user + profile) for a tenant."""
        user = User.objects.create_user(
            email=email,
            password="pw123456!",
            first_name="C",
            last_name="X",
            role=User.Role.CUSTOMER,
            tenant=tenant,
        )
        return Customer.objects.create(tenant=tenant, branch=branch, user=user, name=email, email=email)

    def test_unauthenticated_unauthorized(self) -> None:
        """No credentials → 401."""
        self.client.credentials()
        assert self.client.get(self.stats_url).status_code == 401

    def test_gym_owner_forbidden(self) -> None:
        """A gym owner cannot read platform stats."""
        tenant = provision_tenant(name="Stats Gym", contact_email="owner@stats.test")
        token = issue_token(self._owner(tenant, "owner@stats.test"), tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        assert self.client.get(self.stats_url).status_code == 403

    def test_empty_platform_shape(self) -> None:
        """An empty platform renders zeroed cards and 6 months of zero points."""
        response = self.client.get(self.stats_url)
        assert response.status_code == 200
        data = response.data
        assert data["gyms"]["total"] == 0
        assert data["gyms"]["active"] == 0
        assert data["gyms"]["suspended"] == 0
        assert data["members"]["total"] == 0
        assert data["users"]["total"] == 1  # the platform admin itself
        assert data["users"]["platform_admins"] == 1
        assert data["memberships"] == {"total": 0, "active": 0, "expired": 0, "cancelled": 0}
        assert data["devices"] == {"total": 0, "active": 0}
        assert data["revenue"]["data_available"] is False
        assert data["revenue"]["total_collected"] == "0.00"
        assert len(data["gyms"]["by_month"]) == 6
        assert all(point["count"] == 0 for point in data["gyms"]["by_month"])
        assert len(data["growth"]["new_members_by_month"]) == 6
        assert data["window_months"] == 6

    def test_gym_counts_and_monthly_growth(self) -> None:
        """Gym totals respect lifecycle status; growth buckets by created month."""
        active = provision_tenant(name="Active Gym", contact_email="a@stats.test")
        active_tenant = provision_tenant(name="Second Gym", contact_email="d@stats.test")
        suspended = provision_tenant(name="Suspended Gym", contact_email="b@stats.test")
        provision_tenant(name="Old Gym", contact_email="c@stats.test")
        for tenant, status in (
            (active, Tenant.Status.ACTIVE),
            (active_tenant, Tenant.Status.ACTIVE),
            (suspended, Tenant.Status.SUSPENDED),
        ):
            tenant.status = status
            tenant.save(update_fields=["status"])
        # Backdate one gym into the previous month (auto_now_add bypassed).
        previous_month = self.today - timedelta(days=40)
        Tenant.objects.filter(pk=active.pk).update(created_at=self._aware_day_start(previous_month))

        response = self.client.get(self.stats_url)
        assert response.status_code == 200
        gyms = response.data["gyms"]
        assert gyms["total"] == 4
        assert gyms["active"] == 2
        assert gyms["suspended"] == 1
        assert gyms["new_this_month"] == 3
        by_month = {point["month"]: point["count"] for point in gyms["by_month"]}
        assert by_month[f"{previous_month.year:04d}-{previous_month.month:02d}"] == 1
        current_month_key = f"{self.today.year:04d}-{self.today.month:02d}"
        assert by_month[current_month_key] == 3
        assert response.data["growth"]["new_gyms_by_month"] == gyms["by_month"]

    def test_members_users_devices_memberships_summary(self) -> None:
        """Member/user/device totals and the membership lifecycle split."""
        tenant = provision_tenant(name="Cockpit Gym", contact_email="owner@cockpit.test")
        branch = Branch.objects.create(tenant=tenant, name="Main", branch_type="gym")
        self._member(tenant, branch, "c1@cockpit.test")
        self._member(tenant, branch, "c2@cockpit.test")
        self._owner(tenant, "owner@cockpit.test")

        plan = MembershipPlan.objects.create(
            tenant=tenant,
            name="Monthly",
            price=Decimal("1999.00"),
            duration_days=30,
        )
        member_user = User.objects.get(email="c1@cockpit.test")
        Membership.objects.create(
            tenant=tenant,
            customer=member_user.customer_profile,
            plan=plan,
            start_date=self.today - timedelta(days=10),
            end_date=self.today + timedelta(days=20),  # active
        )
        expired_member = self._member(tenant, branch, "c3@cockpit.test")
        Membership.objects.create(
            tenant=tenant,
            customer=expired_member,
            plan=plan,
            start_date=self.today - timedelta(days=60),
            end_date=self.today - timedelta(days=30),  # auto-expired on save
        )

        BiometricDevice.objects.create(
            tenant=tenant,
            branch=branch,
            vendor="zkteco",
            model="SpeedFace",
            serial_number="SN-001",
            name="Main Entrance",
            connection_type="webhook",
            is_active=True,
        )
        BiometricDevice.objects.create(
            tenant=tenant,
            branch=branch,
            vendor="essl",
            model="e9c",
            serial_number="SN-002",
            name="Back Door",
            connection_type="agent",
            is_active=False,
        )

        response = self.client.get(self.stats_url)
        assert response.status_code == 200
        data = response.data
        assert data["members"]["total"] == 3
        assert data["members"]["new_this_month"] == 3
        assert data["users"]["total"] == 5  # admin + owner + 3 members
        assert data["users"]["customers"] == 3
        assert data["users"]["staff"] == 1
        assert data["users"]["platform_admins"] == 1
        assert data["memberships"] == {"total": 2, "active": 1, "expired": 1, "cancelled": 0}
        assert data["devices"] == {"total": 2, "active": 1}

    def test_revenue_summary_and_series(self) -> None:
        """Completed/pending/failed payments roll up into the revenue block."""
        today = self.today
        tenant = provision_tenant(name="Payroll Gym", contact_email="owner@payroll.test")
        branch = Branch.objects.create(tenant=tenant, name="Main", branch_type="gym")
        member = self._member(tenant, branch, "c1@payroll.test")
        member2 = self._member(tenant, branch, "c2@payroll.test")

        Payment.objects.create(
            tenant=tenant,
            customer=member,
            amount=Decimal("1500.00"),
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
            paid_at=self._aware_day_start(today),  # completed this month
        )
        Payment.objects.create(  # completed last month
            tenant=tenant,
            customer=member,
            amount=Decimal("500.00"),
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
            paid_at=self._aware_day_start(today - timedelta(days=40)),  # completed last month
        )
        Payment.objects.create(
            tenant=tenant,
            customer=member2,
            amount=Decimal("250.00"),
            payment_method=Payment.PaymentMethod.UPI,
            status=Payment.Status.PENDING,
        )
        Payment.objects.create(
            tenant=tenant,
            customer=member2,
            amount=Decimal("99.00"),
            payment_method=Payment.PaymentMethod.CARD,
            status=Payment.Status.FAILED,
        )

        response = self.client.get(self.stats_url)
        assert response.status_code == 200
        revenue = response.data["revenue"]
        assert revenue["data_available"] is True
        assert revenue["total_collected"] == "2000.00"
        assert revenue["collected_this_month"] == "1500.00"
        assert revenue["pending_amount"] == "250.00"
        assert revenue["failed_count"] == 1
        by_month = {point["month"]: point["total"] for point in revenue["by_month"]}
        assert by_month[f"{today.year:04d}-{today.month:02d}"] == "1500.00"
        previous_month = today - timedelta(days=40)
        assert by_month[f"{previous_month.year:04d}-{previous_month.month:02d}"] == "500.00"
        assert len(revenue["by_month"]) == 6

    def test_revenue_bundles_members_and_admission_kinds(self) -> None:
        """Membership-kind payments carry no special casing in the totals."""
        today = self.today
        tenant = provision_tenant(name="Kinds Gym", contact_email="owner@kinds.test")
        branch = Branch.objects.create(tenant=tenant, name="Main", branch_type="gym")
        member = self._member(tenant, branch, "c1@kinds.test")
        Payment.objects.create(
            tenant=tenant,
            customer=member,
            amount=Decimal("100.00"),
            payment_method=Payment.PaymentMethod.CASH,
            status=Payment.Status.COMPLETED,
            kind=Payment.Kind.ADMISSION,
            paid_at=timezone.make_aware(datetime.combine(today, datetime.min.time())),
        )
        assert self.client.get(self.stats_url).data["revenue"]["total_collected"] == "100.00"
