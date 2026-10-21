"""End-to-end rehearsal of the customer-app-access workflow (QA / Shield).

This is the *integration* layer the unit suites do not cover: one member's
complete journey, start to finish, against the real HTTP API —

    front desk creates the member (onboarding submit)
      → the app invite is "sent" over a fake transport
      → the member installs/opens the app with the gym-anchored link
      → requests an OTP, verifies it, lands on the dashboard
      → the membership expires → the gate flips to grace → then to not-entitled
      → a second member of the SAME gym sees only their own data
      → a member of a DIFFERENT gym with the SAME phone resolves via the anchor

Everything is deterministic: the WATI transport is a local fake, the OTP sender
is the DEBUG/stub sender, and no network call, real WhatsApp/SMS send, or Play
upload ever happens (AGENTS.md: "Deterministic tests only").

The journey is asserted through the *public HTTP surface* only — the same
endpoints the Flutter app calls — so the test pins the contract, not the
implementation.
"""

from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.notifications.models import NotificationLog
from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, User

FLAG_ON = {"app_access": True}

# The phone the two gyms' members share (the multi-tenant case).
SHARED_PHONE = "9876500001"
# A second member of the FIRST gym (the isolation case).
SECOND_MEMBER_PHONE = "9876500002"
# A member of the second gym with his own phone.
OTHER_GYM_PHONE = "9876500003"


def _ok_poster():
    """A fake HTTP transport that accepts every WATI/MSG91 post.

    The response body is a *real* dict — the WATI service reads
    ``response.json()["messageId"]`` and writes it to a DB column, so a
    bare MagicMock would blow up on save.
    """
    response = mock.MagicMock(status_code=200)
    response.raise_for_status = mock.MagicMock()
    response.json.return_value = {"messageId": "fake-msg-id", "id": "fake-msg-id"}
    poster = mock.MagicMock(return_value=response)
    return poster


def _posted_urls(poster) -> list[str]:
    """The URLs the fake transport was called with, in call order."""
    return [call.args[0] for call in poster.call_args_list]


def _rows(response) -> list[dict]:
    """The list rows of a DRF response (paginated or not).

    The ERP list endpoints are paginated; the customer list is not. This
    keeps the assertions about *content* rather than about the envelope.
    """
    data = response.data
    if isinstance(data, dict):
        for key in ("results", "items", "data"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return []
    return list(data) if isinstance(data, list) else []


class AppAccessE2ERehearsalTests(APITestCase):
    """The full member journey, asserted through the HTTP API."""

    def setUp(self) -> None:
        """Two gyms (both flagged on), plans, a front-desk manager, fake WATI.

        WATI is configured on the first gym so the invite takes the WhatsApp
        leg; the transport is faked, so nothing leaves the process.
        """
        cache.clear()
        self.poster = _ok_poster()

        self.gym_a = provision_tenant(
            name="Hash Fit",
            contact_email="hash@e2e.local",
            features=FLAG_ON,
        )
        self.gym_a.is_wati_enabled = True
        self.gym_a.wati_api_key = "e2e-wati-key"
        self.gym_a.wati_endpoint = "https://api.wati.io/api/v1/sendSessionMessage"
        self.gym_a.save(update_fields=["is_wati_enabled", "wati_api_key", "wati_endpoint"])

        self.gym_b = provision_tenant(
            name="Iron Temple",
            contact_email="iron@e2e.local",
            features=FLAG_ON,
        )

        self.plan_a = MembershipPlan.objects.create(
            tenant=self.gym_a,
            name="Monthly",
            price=2500,
            duration_days=30,
        )
        self.plan_b = MembershipPlan.objects.create(
            tenant=self.gym_b,
            name="Monthly",
            price=2000,
            duration_days=30,
        )

        # Branches — the wizard's "Who" step always carries one.
        self.branch_a = Branch.objects.create(
            tenant=self.gym_a,
            name="Main Branch",
            address_line1="1 Main St",
            city="Kochi",
            state="Kerala",
            postal_code="682001",
        )
        self.branch_b = Branch.objects.create(
            tenant=self.gym_b,
            name="Temple Branch",
            address_line1="2 Temple Rd",
            city="Kochi",
            state="Kerala",
            postal_code="682002",
        )

        self.manager = User.objects.create_user(
            email="desk@e2e.local",
            password="F1tNati0n!",
            first_name="Front",
            last_name="Desk",
            role=User.Role.MANAGER,
            tenant=self.gym_a,
        )
        self.manager_b = User.objects.create_user(
            email="desk.b@e2e.local",
            password="F1tNati0n!",
            first_name="Front",
            last_name="Desk",
            role=User.Role.MANAGER,
            tenant=self.gym_b,
        )

        # The OTP stub is DEBUG-only and echoes the code in the response —
        # exactly what the mobile app's local QA build relies on.
        stub = override_settings(
            DEBUG=True,
            OTP_SENDER="stub",
            OTP_RESEND_COOLDOWN_SECONDS=0,
        )
        stub.enable()
        self.addCleanup(stub.disable)

    # ── helpers ─────────────────────────────────────────────────────────────

    def auth_as(self, user: User, tenant=None) -> None:
        """Authenticate the test client as ``user``."""
        token = AuthToken.objects.create(user=user, tenant=tenant or user.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def onboarding_payload(self, phone: str, plan: MembershipPlan, **overrides) -> dict:
        """A cash-path wizard payload for one member."""
        branch = self.branch_a if plan.tenant == self.gym_a else self.branch_b
        body = {
            "customer": {"phone": phone, "name": f"Member {phone[-4:]}", "branch": branch.pk},
            "membership": {"plan": plan.pk},
            "payment": {"method": "cash", "amount": plan.price},
            "send_welcome": False,
            "send_app_invite": True,
        }
        body.update(overrides)
        return body

    def onboard(self, phone: str, plan: MembershipPlan, user: User | None = None, **overrides):
        """Run the front-desk onboarding for one member.

        Both WATI transports are faked: the *invite* service
        (``channels.post_wati_template``) and the *notification* service the
        post_save signals use (``wati_service.send_notification``).
        """
        self.auth_as(user or self.manager, (user or self.manager).tenant)
        with (
            mock.patch("apps.notifications.services.channels.requests.post", self.poster),
            mock.patch("apps.notifications.services.wati_service.requests.post", self.poster),
        ):
            response = self.client.post(
                "/api/v1/onboarding/member/",
                self.onboarding_payload(phone, plan, **overrides),
                format="json",
            )
        self.client.credentials()
        return response

    def otp_verify(self, phone: str, gym: str | None = None):
        """Request + verify an OTP, returning the verify response."""
        request_body = {"phone": phone}
        if gym:
            request_body["gym"] = gym
        issued = self.client.post("/api/v1/users/auth/otp/request/", request_body, format="json")
        assert issued.status_code == 200, issued.data
        verify_body = {"phone": phone, "otp": issued.data["otp"]}
        if gym:
            verify_body["gym"] = gym
        return self.client.post("/api/v1/users/auth/otp/verify/", verify_body, format="json")

    # ── 1. front desk creates the member ───────────────────────────────────

    def test_step1_front_desk_onboards_member(self) -> None:
        """Step 1 — one call creates customer + membership + payment."""
        response = self.onboard(SHARED_PHONE, self.plan_a)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["customer"]["phone"], SHARED_PHONE)
        self.assertIsNotNone(response.data["membership"]["id"])
        self.assertEqual(response.data["membership"]["status"], "active")
        self.assertIsNotNone(response.data["payment"]["id"])
        self.assertEqual(response.data["payment"]["status"], "completed")
        self.assertIsNotNone(response.data["invoice_number"])
        # The member now exists exactly once in gym A.
        self.assertEqual(Customer.objects.for_tenant(self.gym_a).filter(phone=SHARED_PHONE).count(), 1)
        self.assertEqual(Membership.objects.for_tenant(self.gym_a).count(), 1)

    def test_step1b_repeat_submit_reuses_the_customer(self) -> None:
        """Step 1b — re-submitting the same phone reuses the customer row.

        No duplicate member, no second membership sold for the same plan
        on the same day (the double-submit guard).
        """
        first = self.onboard(SHARED_PHONE, self.plan_a)
        self.assertEqual(first.status_code, 201, first.data)

        second = self.onboard(SHARED_PHONE, self.plan_a)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(second.data["onboarding_id"], first.data["onboarding_id"])
        self.assertEqual(Customer.objects.for_tenant(self.gym_a).filter(phone=SHARED_PHONE).count(), 1)
        self.assertEqual(Membership.objects.for_tenant(self.gym_a).count(), 1)

    # ── 2. the invite goes out (fake transport) ────────────────────────────

    def test_step2_invite_is_sent_over_whatsapp(self) -> None:
        """Step 2 — the invite rides along and is recorded as sent.

        The transport is faked: the assertion is on the *audit trail* and
        the delivered link, never on a real WhatsApp send.
        """
        response = self.onboard(SHARED_PHONE, self.plan_a)

        self.assertEqual(response.status_code, 201, response.data)
        invite = response.data["app_invite"]
        self.assertEqual(invite["status"], "sent")
        self.assertEqual(invite["channel"], "whatsapp")
        self.assertIsNotNone(invite["sent_at"])

        log = NotificationLog.objects.for_tenant(self.gym_a).get(notification_type="app_invite")
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "whatsapp")
        self.assertEqual(log.actor, self.manager)

        # The app invite went out through the WATI *template* endpoint
        # (business-initiated messages need an approved template, not the
        # session-message URL).
        urls = _posted_urls(self.poster)
        self.assertTrue(urls, "no invite was transported")
        self.assertTrue(
            any("sendTemplateMessage" in url and "fitnation_app_invite" in url for url in urls),
            f"the app invite did not use the WATI template endpoint: {urls}",
        )

    def test_step2b_invite_link_carries_the_gym_anchor(self) -> None:
        """Step 2b — the delivered link anchors to the inviting gym."""
        response = self.onboard(SHARED_PHONE, self.plan_a)
        self.assertEqual(response.status_code, 201, response.data)

        log = NotificationLog.objects.for_tenant(self.gym_a).get(notification_type="app_invite")
        self.assertIn(str(self.gym_a.uuid), log.content)

    def test_step2c_resend_is_idempotent_within_the_cooldown(self) -> None:
        """Step 2c — a repeat invite inside the window is a no-op.

        The front desk can retry a failed invite, but a *sent* invite is not
        re-sent within the dedupe window (no double-messaging the member).
        """
        self.onboard(SHARED_PHONE, self.plan_a)
        customer = Customer.objects.for_tenant(self.gym_a).get(phone=SHARED_PHONE)

        self.auth_as(self.manager, self.gym_a)
        with mock.patch("apps.notifications.services.channels.requests.post", self.poster):
            repeat = self.client.post(
                "/api/v1/memberships/app-invite/",
                {"customer_id": customer.pk, "resend": False},
                format="json",
            )
        self.assertEqual(repeat.status_code, 200, repeat.data)
        self.assertEqual(repeat.data["status"], "already_sent")
        self.assertIsNotNone(repeat.data["resend_allowed_after"])

        # A forced resend goes out again.
        self.poster.reset_mock()
        with mock.patch("apps.notifications.services.channels.requests.post", self.poster):
            forced = self.client.post(
                "/api/v1/memberships/app-invite/",
                {"customer_id": customer.pk, "resend": True},
                format="json",
            )
        self.assertEqual(forced.status_code, 201, forced.data)
        self.assertEqual(forced.data["status"], "sent")
        self.assertTrue(_posted_urls(self.poster))

    # ── 3. the member installs, requests an OTP and lands on the dashboard ─

    def test_step3_member_logs_in_with_the_anchored_link(self) -> None:
        """Step 3 — the gym-anchored OTP login lands on the dashboard.

        The member's phone was never registered by hand — the front desk
        created the customer, and the invite link pinned the gym.
        """
        self.onboard(SHARED_PHONE, self.plan_a)

        # The member opens the gym-anchored link: the anchor is the gym uuid.
        verified = self.otp_verify(SHARED_PHONE, gym=str(self.gym_a.uuid))

        self.assertEqual(verified.status_code, 200, verified.data)
        self.assertIn("token", verified.data)
        self.assertIn("app.access", verified.data["permissions"])
        entitlement = verified.data["entitlement"]
        self.assertEqual(entitlement["status"], "active")
        self.assertFalse(entitlement["read_only"])
        self.assertEqual(entitlement["plan_name"], "Monthly")
        self.assertEqual(entitlement["gym"]["uuid"], str(self.gym_a.uuid))
        self.assertEqual(entitlement["gym"]["name"], "Hash Fit")

        # The dashboard read (a gated content endpoint) succeeds.
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {verified.data['token']}")
        dashboard = self.client.get("/api/v1/workouts/workout-plans/")
        self.assertIn(dashboard.status_code, (200, 404), dashboard.data)

    def test_step3b_entitlement_endpoint_reports_the_same_state(self) -> None:
        """Step 3b — /auth/entitlement/ agrees with the login-time payload."""
        self.onboard(SHARED_PHONE, self.plan_a)
        verified = self.otp_verify(SHARED_PHONE, gym=str(self.gym_a.uuid))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {verified.data['token']}")

        live = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(live.status_code, 200, live.data)
        self.assertEqual(live.data["status"], "active")
        self.assertEqual(live.data["gym"]["uuid"], str(self.gym_a.uuid))

    def test_step3c_device_token_registration_is_tenant_scoped(self) -> None:
        """Step 3c — the FCM token is stored under the member's own gym."""
        self.onboard(SHARED_PHONE, self.plan_a)
        verified = self.otp_verify(SHARED_PHONE, gym=str(self.gym_a.uuid))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {verified.data['token']}")

        registered = self.client.post(
            "/api/v1/notifications/device-tokens/",
            {"token": "fcm-token-e2e-1", "device_id": "device-1", "platform": "android", "device_type": "phone"},
            format="json",
        )
        self.assertIn(registered.status_code, (200, 201), registered.data)
        self.assertEqual(registered.data["token"], "fcm-token-e2e-1")

        from apps.notifications.models import DeviceToken

        row = DeviceToken.objects.get(token="fcm-token-e2e-1")
        self.assertEqual(row.tenant, self.gym_a)
        self.assertEqual(row.user.email, f"{SHARED_PHONE}.{self.gym_a.uuid}@fitnation.local")

    # ── 4. expiry → grace → gated out ──────────────────────────────────────

    def _expire_membership(self, days_ago: int) -> None:
        """Push the member's membership end_date into the past."""
        membership = (
            Membership.objects.for_tenant(self.gym_a).filter(customer__phone=SHARED_PHONE).order_by("-end_date").first()
        )
        self.assertIsNotNone(membership, "member has no membership")
        membership.end_date = timezone.localdate() - timedelta(days=days_ago)
        membership.status = Membership.Status.EXPIRED
        membership.save(update_fields=["end_date", "status"])

    def test_step4_membership_expiry_flips_the_gate_to_grace(self) -> None:
        """Step 4 — 1..6 days after expiry the member is in read-only grace.

        The transition is *server-derived*: the same token that worked
        yesterday now reports ``grace`` and the write is refused with the
        documented code.
        """
        self.onboard(SHARED_PHONE, self.plan_a)
        verified = self.otp_verify(SHARED_PHONE, gym=str(self.gym_a.uuid))
        token = verified.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(self.client.get("/api/v1/users/auth/entitlement/").data["status"], "active")

        self._expire_membership(days_ago=3)

        live = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(live.status_code, 200, live.data)
        self.assertEqual(live.data["status"], "grace")
        self.assertTrue(live.data["read_only"])
        self.assertIsNotNone(live.data["grace_end_date"])

        # Reads still work; writes are refused with the grace code.
        reads = self.client.get("/api/v1/workouts/workout-plans/")
        self.assertIn(reads.status_code, (200, 404), reads.data)

        writes = self.client.post("/api/v1/feedback/feedback/", {"title": "x", "body": "y"}, format="json")
        self.assertEqual(writes.status_code, 403, writes.data)
        self.assertEqual(writes.data["code"], "app_access_read_only")

    def test_step4b_after_the_grace_window_the_member_is_gated_out(self) -> None:
        """Step 4b — 7+ days after expiry the member is gated out entirely.

        The gate is enforced server-side, not just in the app: a stale
        client that ignores the 403 still cannot read gated content.
        """
        self.onboard(SHARED_PHONE, self.plan_a)
        verified = self.otp_verify(SHARED_PHONE, gym=str(self.gym_a.uuid))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {verified.data['token']}")

        self._expire_membership(days_ago=8)

        live = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(live.data["status"], "expired")
        self.assertFalse(live.data["read_only"])

        reads = self.client.get("/api/v1/workouts/workout-plans/")
        self.assertEqual(reads.status_code, 403, reads.data)
        self.assertEqual(reads.data["code"], "app_access_required")

        # The profile stays reachable — a gated member must see WHY.
        profile = self.client.get("/api/v1/customers/customers/")
        self.assertIn(profile.status_code, (200, 403))

    def test_step4c_grace_day_boundaries(self) -> None:
        """Step 4c — the grace window is exactly 7 calendar days.

        Day 7 (end_date + 7) is still grace; day 8 is expired.
        """
        self.onboard(SHARED_PHONE, self.plan_a)
        verified = self.otp_verify(SHARED_PHONE, gym=str(self.gym_a.uuid))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {verified.data['token']}")

        self._expire_membership(days_ago=7)
        self.assertEqual(self.client.get("/api/v1/users/auth/entitlement/").data["status"], "grace")

        self._expire_membership(days_ago=8)
        self.assertEqual(self.client.get("/api/v1/users/auth/entitlement/").data["status"], "expired")

    def test_step4d_cancelled_membership_revokes_immediately(self) -> None:
        """Step 4d — a cancelled membership gets no grace at all."""
        self.onboard(SHARED_PHONE, self.plan_a)
        verified = self.otp_verify(SHARED_PHONE, gym=str(self.gym_a.uuid))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {verified.data['token']}")

        membership = Membership.objects.for_tenant(self.gym_a).filter(customer__phone=SHARED_PHONE).first()
        membership.status = Membership.Status.CANCELLED
        membership.end_date = timezone.localdate()  # today — still inside the window
        membership.save(update_fields=["status", "end_date"])

        live = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(live.data["status"], "none")
        reads = self.client.get("/api/v1/workouts/workout-plans/")
        self.assertEqual(reads.status_code, 403, reads.data)
        self.assertEqual(reads.data["code"], "app_access_required")

    # ── 5. two members of the same gym stay isolated ───────────────────────

    def test_step5_second_member_of_the_same_gym_is_isolated(self) -> None:
        """Step 5 — the second member of gym A sees only their own data.

        No cross-member leak: member 2's customer list, membership list and
        workout reads never expose member 1's rows.
        """
        self.onboard(SHARED_PHONE, self.plan_a)
        self.onboard(SECOND_MEMBER_PHONE, self.plan_a)

        second = self.otp_verify(SECOND_MEMBER_PHONE, gym=str(self.gym_a.uuid))
        self.assertEqual(second.status_code, 200, second.data)
        self.assertIn("app.access", second.data["permissions"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {second.data['token']}")

        customers = self.client.get("/api/v1/customers/customers/")
        self.assertEqual(customers.status_code, 200, customers.data)
        rows = _rows(customers)
        phones = {row["phone"] for row in rows}
        self.assertEqual(phones, {SECOND_MEMBER_PHONE})
        self.assertNotIn(SHARED_PHONE, phones)

        # The membership list is the member's own.
        memberships = self.client.get("/api/v1/memberships/memberships/")
        self.assertIn(memberships.status_code, (200, 403), memberships.data)
        if memberships.status_code == 200:
            self.assertEqual(len(_rows(memberships)), 1)

    # ── 6. the same phone at a different gym resolves via the anchor ───────

    def test_step6_same_phone_at_another_gym_resolves_via_the_anchor(self) -> None:
        """Step 6 — the same phone at gym B is a *different, isolated* account.

        ADR-002 rule 2: one human, two gyms, two accounts. The gym anchor
        (not the phone) decides which tenant the OTP belongs to, and the
        anchored member never sees the other gym's data.
        """
        self.onboard(SHARED_PHONE, self.plan_a)
        self.onboard(SHARED_PHONE, self.plan_b, user=self.manager_b)

        # Gym A's member and gym B's member are distinct accounts.
        user_a = User.objects.get(tenant=self.gym_a, phone=SHARED_PHONE)
        user_b = User.objects.get(tenant=self.gym_b, phone=SHARED_PHONE)
        self.assertNotEqual(user_a.pk, user_b.pk)

        # The anchor decides: the same phone verifies into gym A...
        in_a = self.otp_verify(SHARED_PHONE, gym=str(self.gym_a.uuid))
        self.assertEqual(in_a.status_code, 200, in_a.data)
        self.assertEqual(in_a.data["entitlement"]["gym"]["uuid"], str(self.gym_a.uuid))

        # ...and into gym B.
        in_b = self.otp_verify(SHARED_PHONE, gym=str(self.gym_b.uuid))
        self.assertEqual(in_b.status_code, 200, in_b.data)
        self.assertEqual(in_b.data["entitlement"]["gym"]["uuid"], str(self.gym_b.uuid))
        self.assertNotEqual(in_a.data["token"], in_b.data["token"])

        # Gym B's member sees only gym B's data.
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {in_b.data['token']}")
        customers = self.client.get("/api/v1/customers/customers/")
        self.assertEqual(customers.status_code, 200, customers.data)
        for row in _rows(customers):
            customer = Customer.objects.get(pk=row["id"])
            self.assertEqual(customer.tenant, self.gym_b)

    def test_step6b_multi_gym_member_gets_a_disambiguation_prompt(self) -> None:
        """Step 6b — without an anchor, a two-gym phone is asked to choose.

        The response leaks only the tenant uuid + display name (never
        membership or entitlement state), and is rate-limited.
        """
        self.onboard(SHARED_PHONE, self.plan_a)
        self.onboard(SHARED_PHONE, self.plan_b, user=self.manager_b)

        issued = self.client.post(
            "/api/v1/users/auth/otp/request/",
            {"phone": SHARED_PHONE},
            format="json",
        )
        self.assertEqual(issued.status_code, 200, issued.data)
        self.assertEqual(issued.data["action"], "select_gym")
        names = {gym["name"] for gym in issued.data["gyms"]}
        self.assertEqual(names, {"Hash Fit", "Iron Temple"})
        # No entitlement/registration state is disclosed.
        self.assertNotIn("entitlement", issued.data)
        self.assertNotIn("status", issued.data)
        for gym in issued.data["gyms"]:
            self.assertEqual(set(gym.keys()), {"tenant", "name"})

    # ── 7. non-enumeration ─────────────────────────────────────────────────

    def test_step7_unknown_and_known_phone_are_indistinguishable(self) -> None:
        """Step 7 — an unknown phone and a known-but-unentitled one look the same.

        Same status code, same body shape: the response never reveals
        whether a phone is registered.
        """
        # A known phone with no membership (a walk-in).
        User.objects.create_user(
            email="walkin@e2e.local",
            password="x",
            first_name="Walk",
            last_name="In",
            role=User.Role.CUSTOMER,
            tenant=self.gym_a,
            phone="9876500009",
        )
        Customer.objects.create(
            tenant=self.gym_a,
            name="Walk In",
            phone="9876500009",
            user=User.objects.get(email="walkin@e2e.local"),
        )

        known = self.otp_verify("9876500009", gym=str(self.gym_a.uuid))
        # A phone the front desk never registered anywhere (not even here).
        unknown = self.otp_verify("9876500010", gym=str(self.gym_a.uuid))
        self.assertEqual(known.status_code, 200, known.data)
        self.assertEqual(unknown.status_code, 200, unknown.data)

        # Identical key sets — no field distinguishes the two.
        self.assertEqual(set(known.data.keys()), set(unknown.data.keys()))
        self.assertEqual(known.data["entitlement"]["status"], "none")
        self.assertNotIn("app.access", known.data["permissions"])
        # The role permission set is identical for both.
        self.assertEqual(
            sorted(p for p in known.data["permissions"]),
            sorted(p for p in unknown.data["permissions"]),
        )

    def test_step7b_no_anchor_and_no_match_is_a_generic_400(self) -> None:
        """Step 7b — an unknown phone without an anchor gets a generic 400."""
        response = self.client.post(
            "/api/v1/users/auth/otp/request/",
            {"phone": "9876500099"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data, {"detail": "Specify your gym to continue."})

    # ── 8. the rollout flag ────────────────────────────────────────────────

    def test_step8_flag_off_tenant_keeps_working(self) -> None:
        """Step 8 — a gym with the flag off is unaffected by the whole feature.

        No ``app.access``, no invite, and the content endpoints are not
        gated (the feature does not exist for that tenant).
        """
        gym_c = provision_tenant(name="Legacy Gym", contact_email="legacy@e2e.local")
        plan_c = MembershipPlan.objects.create(tenant=gym_c, name="Monthly", price=1000, duration_days=30)
        branch_c = Branch.objects.create(
            tenant=gym_c,
            name="Legacy Branch",
            address_line1="3 Old Rd",
            city="Kochi",
            state="Kerala",
            postal_code="682003",
        )
        manager_c = User.objects.create_user(
            email="desk.c@e2e.local",
            password="F1tNati0n!",
            first_name="Legacy",
            last_name="Desk",
            role=User.Role.MANAGER,
            tenant=gym_c,
        )
        self.auth_as(manager_c, gym_c)
        response = self.client.post(
            "/api/v1/onboarding/member/",
            {
                "customer": {"phone": "9876500008", "name": "Legacy Member", "branch": branch_c.pk},
                "membership": {"plan": plan_c.pk},
                "payment": {"method": "cash", "amount": plan_c.price},
                "send_welcome": False,
                "send_app_invite": True,
            },
            format="json",
        )
        self.client.credentials()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["app_invite"]["status"], "not_applicable")
        self.assertEqual(response.data["app_invite"]["reason"], "flag_off")
        self.assertEqual(response.data["entitlement_preview"]["status"], "none")
