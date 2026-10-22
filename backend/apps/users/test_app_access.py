"""App-access wiring tests (FBOS-011 §2/§3): effective permissions, OTP verify
payload, the entitlement endpoint, EntitlementRequired enforcement, and the
non-enumerating auto-provision behavior."""

from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, User
from apps.users.services import get_effective_permissions, get_user_permissions

FLAG_ON = {"app_access": True}


class AppAccessTestBase(APITestCase):
    """Shared fixtures: flagged-on tenant, owner, plan, member machinery."""

    def setUp(self) -> None:
        """Flag-on tenant + owner + plan; DEBUG+stub OTP settings.

        The LocMem cache survives between tests (Django keys LocMem backends
        by their settings spec, not the test), and rolled-back tests recycle
        pks/uuids — so counters like the OTP auto-create cap would leak from
        one test into the next. Clear it so every test starts empty.
        """
        cache.clear()
        self.tenant = provision_tenant(name="Hash Fit", contact_email="hash@local.test", features=FLAG_ON)
        self.owner = User.objects.create_user(
            email="owner@hash.local",
            password="F1tNati0n!",
            first_name="Own",
            last_name="Er",
            role=User.Role.GYM_OWNER,
            tenant=self.tenant,
            is_owner=True,
        )
        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly Unlimited",
            price=2500,
            duration_days=30,
        )
        stub = override_settings(
            DEBUG=True,
            OTP_SENDER="stub",
            OTP_RESEND_COOLDOWN_SECONDS=0,
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        )
        stub.enable()
        self.addCleanup(stub.disable)

    def create_customer_user(self, phone: str, email: str | None = None) -> User:
        """Create a customer user in the flagged tenant."""
        return User.objects.create_user(
            email=email or f"{phone.replace('+', '')}@fitnation.local",
            password="x",
            first_name="Mem",
            last_name="Ber",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone=phone,
        )

    def give_membership(self, user: User, *, end_offset: int = 20, plan: MembershipPlan | None = None) -> Membership:
        """Attach a customer profile + membership to a user."""
        customer = Customer.objects.for_tenant(self.tenant).filter(user=user).first()
        if customer is None:
            customer = Customer.objects.create(
                tenant=self.tenant,
                user=user,
                name=user.get_full_name() or "Member",
                phone=user.phone,
            )
        today = timezone.localdate()
        return Membership.objects.create(
            tenant=self.tenant,
            customer=customer,
            plan=plan or self.plan,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=end_offset),
        )

    def auth(self, user: User, tenant=None) -> None:
        """Authenticate the test client as ``user``."""
        tenant = tenant or user.tenant
        token = AuthToken.objects.create(user=user, tenant=tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def request_otp(self, phone: str, gym: str | None = None):
        """Request an OTP (DEBUG stub echoes the code)."""
        payload = {"phone": phone}
        if gym:
            payload["gym"] = gym
        return self.client.post("/api/v1/users/auth/otp/request/", payload, format="json")

    def verify_otp(self, phone: str, gym: str | None = None):
        """Request + verify an OTP in one step, returning the verify response."""
        issued = self.request_otp(phone, gym)
        assert issued.status_code == 200, issued.data
        payload = {"phone": phone, "otp": issued.data["otp"]}
        if gym:
            payload["gym"] = gym
        return self.client.post("/api/v1/users/auth/otp/verify/", payload, format="json")


class EffectivePermissionsTests(AppAccessTestBase):
    """app.access rides on the role set only while entitled (§2.2)."""

    def test_active_customer_gets_app_access(self) -> None:
        """Entitled customer → role set + app.access."""
        user = self.create_customer_user("+919900020001")
        self.give_membership(user)
        perms = get_effective_permissions(user, self.tenant)
        self.assertIn("app.access", perms)
        self.assertIn("workouts.view_workout", perms)  # role base kept

    def test_grace_customer_gets_app_access(self) -> None:
        """Grace (read-only) still carries app.access; read_only is in the
        entitlement payload, not a permission code."""
        user = self.create_customer_user("+919900020002")
        self.give_membership(user, end_offset=-2)
        perms = get_effective_permissions(user, self.tenant)
        self.assertIn("app.access", perms)

    def test_expired_customer_lacks_app_access(self) -> None:
        """Expired beyond grace → role set only."""
        user = self.create_customer_user("+919900020003")
        self.give_membership(user, end_offset=-30)
        perms = get_effective_permissions(user, self.tenant)
        self.assertNotIn("app.access", perms)
        self.assertEqual(perms, get_user_permissions(user))

    def test_membershipless_customer_lacks_app_access(self) -> None:
        """Auto-provisioned walk-in (no membership) → role set only."""
        user = self.create_customer_user("+919900020004")
        self.assertNotIn("app.access", get_effective_permissions(user, self.tenant))

    def test_flag_off_never_grants_app_access(self) -> None:
        """Legacy tenant (flag off) → app.access never appears."""
        unflagged = provision_tenant(name="Legacy", contact_email="legacy2@local.test")
        plan = MembershipPlan.objects.create(tenant=unflagged, name="M", price=1, duration_days=30)
        user = User.objects.create_user(
            email="legacymember@fitnation.local",
            password="x",
            first_name="L",
            last_name="M",
            role=User.Role.CUSTOMER,
            tenant=unflagged,
        )
        customer = Customer.objects.create(tenant=unflagged, user=user, name="LM")
        Membership.objects.create(
            tenant=unflagged,
            customer=customer,
            plan=plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=5),
        )
        self.assertNotIn("app.access", get_effective_permissions(user, unflagged))

    def test_staff_roles_unchanged(self) -> None:
        """Owner wildcard and manager set are untouched by entitlement."""
        self.assertEqual(get_effective_permissions(self.owner, self.tenant), ["*"])
        manager = User.objects.create_user(
            email="mgr@hash.local",
            password="x",
            first_name="M",
            last_name="G",
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )
        self.assertEqual(get_effective_permissions(manager, self.tenant), get_user_permissions(manager))


class OTPVerifyEntitlementTests(AppAccessTestBase):
    """OTP verify response: entitlement + effective permissions (§2.3a/§3)."""

    def test_entitled_member_response(self) -> None:
        """Active member → app.access + full entitlement object with gym."""
        user = self.create_customer_user("+919900030001")
        self.give_membership(user)
        response = self.verify_otp("+919900030001", gym=str(self.tenant.uuid))
        self.assertEqual(response.status_code, 200)
        self.assertIn("app.access", response.data["permissions"])
        entitlement = response.data["entitlement"]
        self.assertEqual(entitlement["status"], "active")
        self.assertFalse(entitlement["read_only"])
        self.assertEqual(entitlement["plan_name"], "Monthly Unlimited")
        self.assertEqual(entitlement["gym"]["name"], "Hash Fit")
        self.assertEqual(entitlement["gym"]["uuid"], str(self.tenant.uuid))

    def test_unknown_phone_auto_provision_gets_no_access_non_enumerating(self) -> None:
        """Unknown phone + anchor: identity created, entitlement none, and the
        response keys are IDENTICAL to a known member's (non-enumeration)."""
        known = self.verify_otp("+919900030002", gym=str(self.tenant.uuid))
        self.give_membership(User.objects.get(pk=known.data["user"]["id"]))
        entitled = self.verify_otp("+919900030002", gym=str(self.tenant.uuid))

        unknown = self.verify_otp("+919900030003", gym=str(self.tenant.uuid))
        self.assertEqual(unknown.status_code, 200)
        # byte-identical shape, modulo values (§3.1: no registration reveal)
        self.assertEqual(
            sorted(unknown.data.keys()),
            sorted(entitled.data.keys()),
        )
        self.assertEqual(
            sorted(unknown.data["entitlement"].keys()),
            sorted(entitled.data["entitlement"].keys()),
        )
        self.assertNotIn("app.access", unknown.data["permissions"])
        self.assertEqual(unknown.data["entitlement"]["status"], "none")
        # a usable token + customer row exist (auto-create keeps working)
        self.assertTrue(unknown.data["token"])
        user = User.objects.get(pk=unknown.data["user"]["id"])
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertTrue(user.email.endswith("@fitnation.local"))

    def test_known_phone_without_membership_gets_none(self) -> None:
        """Known phone, no membership (case c) → same none-gate shape."""
        self.create_customer_user("+919900030004")
        response = self.verify_otp("+919900030004", gym=str(self.tenant.uuid))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["entitlement"]["status"], "none")
        self.assertNotIn("app.access", response.data["permissions"])

    def test_grace_member_verify_payload_is_read_only(self) -> None:
        """Grace member sees status=grace + read_only=true at verify."""
        user = self.create_customer_user("+919900030005")
        self.give_membership(user, end_offset=-2)
        response = self.verify_otp("+919900030005", gym=str(self.tenant.uuid))
        entitlement = response.data["entitlement"]
        self.assertEqual(entitlement["status"], "grace")
        self.assertTrue(entitlement["read_only"])
        self.assertIsNotNone(entitlement["grace_end_date"])

    def test_unknown_phone_without_anchor_generic_400(self) -> None:
        """No anchor + zero matches → the unchanged generic 400 (§3.2)."""
        response = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "+919900030006", "otp": "123456"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Specify your gym", str(response.data))

    def test_same_phone_two_tenants_no_integrity_error(self) -> None:
        """The tenant-scoped synthetic email fixes the cross-gym 500 (§3.5)."""
        other = provision_tenant(name="Gym B", contact_email="b2@local.test", features=FLAG_ON)
        first = self.verify_otp("+919900030007", gym=str(self.tenant.uuid))
        second = self.verify_otp("+919900030007", gym=str(other.uuid))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(first.data["user"]["id"], second.data["user"]["id"])
        self.assertNotEqual(first.data["user"]["email"], second.data["user"]["email"])

    def test_auto_create_daily_cap_429(self) -> None:
        """Exhausting the tenant auto-create cap → generic 429."""
        cap = override_settings(APP_AUTOCREATE_DAILY_LIMIT=1)
        cap.enable()
        self.addCleanup(cap.disable)
        first = self.verify_otp("+919900030008", gym=str(self.tenant.uuid))
        self.assertEqual(first.status_code, 200)
        second = self.verify_otp("+919900030009", gym=str(self.tenant.uuid))
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.data, {"detail": "Too many requests. Try again later."})

    def test_auto_create_cap_isolation_between_tenants(self) -> None:
        """The cap counter is per tenant — one gym exhausting it leaves the
        next gym with a fresh cap (keyed by uuid, never a recyclable pk)."""
        other = provision_tenant(name="Flex Fit", contact_email="flex@local.test", features=FLAG_ON)
        self.assertNotEqual(other.pk, self.tenant.pk)  # sanity: distinct rows
        cap = override_settings(APP_AUTOCREATE_DAILY_LIMIT=1)
        cap.enable()
        self.addCleanup(cap.disable)
        first_here = self.verify_otp("+919900030012", gym=str(self.tenant.uuid))
        self.assertEqual(first_here.status_code, 200)
        # Same day, same counter state — a different tenant still auto-creates.
        first_other_gym = self.verify_otp("+919900030013", gym=str(other.uuid))
        self.assertEqual(first_other_gym.status_code, 200)
        # And each tenant is capped against its own usage, not the other's.
        self.assertEqual(self.verify_otp("+919900030014", gym=str(self.tenant.uuid)).status_code, 429)
        self.assertEqual(self.verify_otp("+919900030015", gym=str(other.uuid)).status_code, 429)

    def test_known_phone_not_counted_against_auto_create_cap(self) -> None:
        """Existing members log in even with the cap exhausted (cap counts
        CREATIONS only)."""
        self.create_customer_user("+919900030010")
        filler = self.verify_otp("+919900030011", gym=str(self.tenant.uuid))
        self.assertEqual(filler.status_code, 200)
        cap = override_settings(APP_AUTOCREATE_DAILY_LIMIT=1)
        cap.enable()
        self.addCleanup(cap.disable)
        known = self.verify_otp("+919900030010", gym=str(self.tenant.uuid))
        self.assertEqual(known.status_code, 200)


class MeAndEntitlementEndpointTests(AppAccessTestBase):
    """MeView + GET /auth/entitlement/ contracts (§2.3b/§2.3c)."""

    def test_me_carries_permissions_and_entitlement(self) -> None:
        """/auth/me/ shows effective permissions + the entitlement object."""
        user = self.create_customer_user("+919900040001")
        self.give_membership(user)
        self.auth(user)
        response = self.client.get("/api/v1/users/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("app.access", response.data["permissions"])
        self.assertEqual(response.data["entitlement"]["status"], "active")

    def test_me_staff_entitlement_null(self) -> None:
        """Staff /auth/me/ keeps role permissions, entitlement null."""
        self.auth(self.owner)
        response = self.client.get("/api/v1/users/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["permissions"], ["*"])
        self.assertIsNone(response.data["entitlement"])

    def test_entitlement_endpoint_active(self) -> None:
        """The resume-time endpoint returns the entitlement object directly."""
        user = self.create_customer_user("+919900040002")
        self.give_membership(user)
        self.auth(user)
        response = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "active")
        self.assertFalse(response.data["read_only"])
        self.assertEqual(response.data["gym"]["uuid"], str(self.tenant.uuid))

    def test_entitlement_endpoint_grace_and_expired(self) -> None:
        """Grace → read_only true; expired → status expired."""
        user = self.create_customer_user("+919900040003")
        self.give_membership(user, end_offset=-2)
        self.auth(user)
        response = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(response.data["status"], "grace")
        self.assertTrue(response.data["read_only"])

        user.refresh_from_db()
        membership = user.customer_profile.memberships.first()
        membership.end_date = timezone.localdate() - timedelta(days=30)
        membership.save(update_fields=["end_date"])
        response = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(response.data["status"], "expired")

    def test_entitlement_endpoint_requires_auth(self) -> None:
        """Anonymous calls are 401 (IsAuthenticated)."""
        response = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(response.status_code, 401)

    def test_entitlement_keys_match_mobile_contract(self) -> None:
        """Pin the exact key set the mobile Dart model parses (entitlement.dart).

        The shipped contract: ``status``, ``read_only``, ``plan_name``,
        ``end_date``, ``grace_end_date`` and ``gym: {uuid, name}``, with
        ``status`` drawn from the EntitlementStatus vocabulary. Any backend
        change to these keys breaks the member app's gate.
        """
        from apps.memberships.selectors import EntitlementStatus

        user = self.create_customer_user("+919900040005")
        self.give_membership(user)
        self.auth(user)

        expected_keys = {"status", "read_only", "plan_name", "end_date", "grace_end_date", "gym"}
        expected_statuses = {
            EntitlementStatus.ACTIVE,
            EntitlementStatus.GRACE,
            EntitlementStatus.EXPIRED,
            EntitlementStatus.NONE,
        }

        response = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(set(response.data.keys()), expected_keys)
        self.assertEqual(set(response.data["gym"].keys()), {"uuid", "name"})
        self.assertIn(response.data["status"], expected_statuses)

        me_response = self.client.get("/api/v1/users/auth/me/")
        self.assertEqual(set(me_response.data["entitlement"].keys()), expected_keys)
        self.assertIn(me_response.data["entitlement"]["status"], expected_statuses)


class EntitlementRequiredTests(TestCase):
    """The customer-content gate (§2.4): grace read-only, expired blocked."""

    def setUp(self) -> None:
        """Flagged-on tenant + a gated-content surface (memberships list is
        NOT gated; workouts IS)."""
        from rest_framework.test import APIRequestFactory

        from apps.permissions.entitlements import EntitlementRequired

        self.factory = APIRequestFactory()
        self.permission = EntitlementRequired()
        self.tenant = provision_tenant(name="Hash Fit 2", contact_email="hash2@local.test", features=FLAG_ON)
        self.plan = MembershipPlan.objects.create(tenant=self.tenant, name="M", price=1, duration_days=30)

    def _customer_request(self, *, method: str = "get", end_offset: int | None = 20, role: str = "customer"):
        """Build a request + user in the given entitlement state."""
        user = User.objects.create_user(
            email=f"gate-{role}-{method}-{end_offset}@fitnation.local",
            password="x",
            first_name="G",
            last_name="U",
            role=role,
            tenant=self.tenant,
            phone="+919900050000",
        )
        if end_offset is not None and role == "customer":
            customer = Customer.objects.create(tenant=self.tenant, user=user, name="GU", phone="+919900050000")
            Membership.objects.create(
                tenant=self.tenant,
                customer=customer,
                plan=self.plan,
                start_date=timezone.localdate() - timedelta(days=5),
                end_date=timezone.localdate() + timedelta(days=end_offset),
            )
        request = getattr(self.factory, method)("/")
        request.user = user
        request.tenant = self.tenant

        class View:  # a minimal stand-in for a gated viewset
            action = None

        return request, View()

    def test_active_allows_writes(self) -> None:
        """Active member → every method allowed."""
        request, view = self._customer_request(method="post")
        self.assertTrue(self.permission.has_permission(request, view))

    def test_grace_read_allowed_write_denied_with_code(self) -> None:
        """Grace: GET allowed; POST → 403 body carries app_access_read_only."""
        from rest_framework.exceptions import PermissionDenied

        request, view = self._customer_request(method="get", end_offset=-2)
        self.assertTrue(self.permission.has_permission(request, view))
        request, view = self._customer_request(method="post", end_offset=-2)
        with self.assertRaises(PermissionDenied) as ctx:
            self.permission.has_permission(request, view)
        self.assertEqual(ctx.exception.detail["code"], "app_access_read_only")

    def test_expired_read_denied_with_code(self) -> None:
        """Expired: even GET → 403 body carries app_access_required."""
        from rest_framework.exceptions import PermissionDenied

        request, view = self._customer_request(method="get", end_offset=-30)
        with self.assertRaises(PermissionDenied) as ctx:
            self.permission.has_permission(request, view)
        self.assertEqual(ctx.exception.detail["code"], "app_access_required")

    def test_staff_always_allowed(self) -> None:
        """Non-customer roles pass through (their gate is RBAC)."""
        for role in ("gym_owner", "manager", "trainer"):
            request, view = self._customer_request(method="delete", end_offset=-30, role=role)
            self.assertTrue(self.permission.has_permission(request, view), role)

    def test_flag_off_short_circuits_allow(self) -> None:
        """Legacy tenant (flag off) → gate invisible, expired member passes."""
        unflagged = provision_tenant(name="Legacy 2", contact_email="legacy3@local.test")
        plan = MembershipPlan.objects.create(tenant=unflagged, name="M", price=1, duration_days=30)
        user = User.objects.create_user(
            email="legacygate@fitnation.local",
            password="x",
            first_name="L",
            last_name="G",
            role="customer",
            tenant=unflagged,
        )
        customer = Customer.objects.create(tenant=unflagged, user=user, name="LG")
        Membership.objects.create(
            tenant=unflagged,
            customer=customer,
            plan=plan,
            start_date=timezone.localdate() - timedelta(days=90),
            end_date=timezone.localdate() - timedelta(days=60),
        )
        request = self.factory.post("/")
        request.user = user
        request.tenant = unflagged
        self.assertTrue(self.permission.has_permission(request, type("V", (), {"action": None})()))

    def test_exempt_actions_bypass_the_gate(self) -> None:
        """CustomerViewSet profile-domain actions stay usable when expired."""
        user = User.objects.create_user(
            email="exempt@fitnation.local",
            password="x",
            first_name="E",
            last_name="X",
            role="customer",
            tenant=self.tenant,
        )
        request = self.factory.get("/")
        request.user = user
        request.tenant = self.tenant
        view = type("V", (), {"action": "health_profile", "entitlement_exempt_actions": {"health_profile"}})()
        self.assertTrue(self.permission.has_permission(request, view))
        view = type("V", (), {"action": "progress_photos", "entitlement_exempt_actions": {"health_profile"}})()
        with self.assertRaises(Exception):  # noqa: B017 — broad by design — keeps test semantics
            self.permission.has_permission(request, view)
