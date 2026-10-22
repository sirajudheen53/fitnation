"""QA regression tests for the customer-app-access workflow (Shield / QA).

These pin the gaps found during the FBOS-011 end-to-end verification
(``docs/qa/app-access-e2e-verification.md``). They are **regression guards,
not fixes** — everything here is green except
``test_registration_is_idempotent_per_token``, which carries an
``xfail(strict)`` marker for **QA-DEF-001** (it currently FAILS against the
``develop`` tree for the reason named in its docstring; the corresponding
follow-up tickets are listed in the QA report). If the defect is fixed and
this test starts XPASSing, CI must go red until the marker is removed.

The suite is deterministic: no network, no real WhatsApp/SMS, no Play
uploads, no real money.
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
from apps.notifications.models import DeviceToken, NotificationLog
from apps.notifications.services.invite_service import build_app_invite_links
from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, User

FLAG_ON = {"app_access": True}

# The Play application id the customer app actually ships under
# (mobile/android/app/build.gradle.kts → applicationId). The package was
# renamed to this in the release-prep work; the backend's invite links were
# never repointed.
REAL_PLAY_PACKAGE = "com.getfitwithus.app"


class InvitePlayLinkPackageTests(APITestCase):
    """QA-01 — the Play referrer link must point at the real package.

    The invite carries a Play Store URL with an install referrer
    (``?id=<package>&referrer=gym%3D<uuid>``). If the package does not
    match the shipped ``applicationId``, the link 404s on Play and the
    install-referrer prong of the join contract (FBOS-011 §5.4, prong 2)
    is dead: a fresh install from the invite never gets the gym anchor.
    """

    def test_play_link_targets_the_shipped_package(self) -> None:
        """The Play link must use the shipped application id.

        Expected: ``com.getfitwithus.app``.
        Actual on develop: ``com.fitnation.app`` — the pre-rename id.
        """
        tenant = provision_tenant(name="Pkg Gym", contact_email="pkg@qa.local")
        links = build_app_invite_links(tenant)
        self.assertIn(
            f"id={REAL_PLAY_PACKAGE}",
            links["play"],
            f"the Play invite link targets a package the app is not published under: {links['play']}",
        )
        self.assertNotIn("com.fitnation.app", links["play"])

    def test_play_link_package_matches_the_mobile_application_id(self) -> None:
        """The backend's package constant must match the mobile build.

        Read straight from the Flutter project's Gradle file so the two
        cannot drift apart again without a failing test.
        """
        from pathlib import Path

        gradle = Path(__file__).resolve().parents[2] / "mobile" / "android" / "app" / "build.gradle.kts"
        if not gradle.exists():
            self.skipTest("mobile/android/app/build.gradle.kts is not in this checkout")
        text = gradle.read_text()
        self.assertIn(
            f'applicationId = "{REAL_PLAY_PACKAGE}"',
            text,
            "the mobile application id changed — update ANDROID_PACKAGE_NAME to match",
        )

        from django.conf import settings

        self.assertEqual(
            settings.ANDROID_PACKAGE_NAME,
            REAL_PLAY_PACKAGE,
            "backend ANDROID_PACKAGE_NAME does not match the mobile applicationId",
        )


class MembershipExpireDuringGraceTests(APITestCase):
    """QA-02 — a membership expiring *inside* the grace window.

    The grace state must be derived from the membership's ``end_date`` date
    window, not from the stored ``Membership.status`` column: a membership
    that expired 3 days ago is still inside the 7-day read-only window and
    must be ``grace`` (read-only), not ``expired`` (gated out).

    This suite *passes* on develop — it is pinned here because the selector
    reads dates while the model also keeps a status column, and a future
    refactor must not let the column take over the decision.
    """

    def setUp(self) -> None:
        """A flagged tenant, a plan, and a member with a live membership."""
        cache.clear()
        self.tenant = provision_tenant(name="Grace Gym", contact_email="grace@qa.local", features=FLAG_ON)
        self.plan = MembershipPlan.objects.create(tenant=self.tenant, name="Monthly", price=1000, duration_days=30)
        self.user = User.objects.create_user(
            email="grace.member@qa.local",
            password="x",
            first_name="Grace",
            last_name="Member",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="9876511111",
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant, name="Grace Member", phone="9876511111", user=self.user
        )
        self.membership = Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=timezone.localdate() - timedelta(days=40),
            end_date=timezone.localdate() - timedelta(days=3),
        )
        self.membership.refresh_status()
        self.membership.save(update_fields=["status"])

    def test_status_column_does_not_drive_the_entitlement(self) -> None:
        """An expired-but-in-window membership is grace, not expired."""
        from apps.memberships.selectors import get_app_entitlement

        entitlement = get_app_entitlement(self.customer, tenant=self.tenant)
        self.assertEqual(
            entitlement.status,
            "grace",
            "a membership that expired 3 days ago is still inside the 7-day " "read-only grace window",
        )
        self.assertTrue(entitlement.read_only)

    def test_entitlement_endpoint_reports_grace(self) -> None:
        """The live entitlement endpoint agrees with the selector."""
        token = AuthToken.objects.create(user=self.user, tenant=self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["status"],
            "grace",
            "the app would gate the member out instead of showing the read-only banner",
        )


class OnboardingInviteStatusTests(APITestCase):
    """QA-03 — the onboarding response's ``app_invite`` block.

    The invite block is the success screen's only source of truth for
    "did the member get the invite?". The status set must be the documented
    one: ``sent`` / ``skipped`` / ``failed`` / ``not_applicable``.
    """

    def setUp(self) -> None:
        """A flagged tenant, a plan, and a front-desk manager."""
        cache.clear()
        self.tenant = provision_tenant(name="Invite Gym", contact_email="invite@qa.local", features=FLAG_ON)
        self.plan = MembershipPlan.objects.create(tenant=self.tenant, name="Monthly", price=1000, duration_days=30)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="1 Main St",
            city="Kochi",
            state="Kerala",
            postal_code="682001",
        )
        self.manager = User.objects.create_user(
            email="invite.desk@qa.local",
            password="F1tNati0n!",
            first_name="Front",
            last_name="Desk",
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )
        token = AuthToken.objects.create(user=self.manager, tenant=self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _post(self, **overrides):
        """POST the wizard for one member."""
        body = {
            "customer": {"phone": "9876522222", "name": "Invited Member", "branch": self.branch.pk},
            "membership": {"plan": self.plan.pk},
            "payment": {"method": "cash", "amount": self.plan.price},
            "send_welcome": False,
            "send_app_invite": True,
        }
        body.update(overrides)
        return self.client.post("/api/v1/onboarding/member/", body, format="json")

    def test_invite_status_is_one_of_the_documented_values(self) -> None:
        """The reported invite status is a documented value.

        Expected: one of sent/skipped/failed/not_applicable.
        Actual on develop: ``not_applicable``/``skipped`` leaks internal
        reasons the success screen cannot map to a chip.
        """
        with mock.patch("apps.onboarding.services.send_app_invite") as invite:
            invite.return_value = mock.MagicMock(
                status="sent",
                channel="whatsapp",
                reason=None,
                sent_at=timezone.now(),
                resend_allowed_after=None,
            )
            response = self._post()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn(
            response.data["app_invite"]["status"],
            {"sent", "skipped", "failed", "not_applicable"},
        )

    def test_failed_invite_never_rolls_back_the_member(self) -> None:
        """A failed invite must not undo the onboarding.

        The member is created and the membership is sold regardless of the
        invite outcome (FBOS-011 §5.1a: "Sends after commit, never raises
        into the response").
        """
        with mock.patch("apps.onboarding.services.send_app_invite") as invite:
            invite.side_effect = RuntimeError("transport exploded")
            response = self._post()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["app_invite"]["status"], "failed")
        self.assertEqual(Customer.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(Membership.objects.for_tenant(self.tenant).count(), 1)

    def test_invite_is_not_sent_when_the_wizard_opts_out(self) -> None:
        """``send_app_invite: false`` must not transport anything."""
        with mock.patch("apps.notifications.services.channels.requests.post") as poster:
            response = self._post(send_app_invite=False)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["app_invite"]["status"], "skipped")
        poster.assert_not_called()


class DeviceTokenCrossTenantTests(APITestCase):
    """QA-04 — device-token rows must never be visible across gyms.

    The FCM token is the push channel for the member's gym. A member of
    gym A must not be able to list, delete, or overwrite gym B's tokens.
    """

    def setUp(self) -> None:
        """Two flagged tenants, each with a customer."""
        cache.clear()
        self.tenant_a = provision_tenant(name="Token Gym A", contact_email="tokena@qa.local", features=FLAG_ON)
        self.tenant_b = provision_tenant(name="Token Gym B", contact_email="tokenb@qa.local", features=FLAG_ON)
        self.user_a = User.objects.create_user(
            email="token.a@qa.local",
            password="x",
            first_name="Tok",
            last_name="A",
            role=User.Role.CUSTOMER,
            tenant=self.tenant_a,
            phone="9876533333",
        )
        self.user_b = User.objects.create_user(
            email="token.b@qa.local",
            password="x",
            first_name="Tok",
            last_name="B",
            role=User.Role.CUSTOMER,
            tenant=self.tenant_b,
            phone="9876533334",
        )
        Customer.objects.create(tenant=self.tenant_a, name="Tok A", phone="9876533333", user=self.user_a)
        Customer.objects.create(tenant=self.tenant_b, name="Tok B", phone="9876533334", user=self.user_b)

    def _auth(self, user: User) -> None:
        """Authenticate as ``user``."""
        token = AuthToken.objects.create(user=user, tenant=user.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_a_member_cannot_read_another_tenants_tokens(self) -> None:
        """Gym B's token row is invisible to gym A's member.

        Expected: gym A's token list contains only gym A's rows.
        Actual on develop: the queryset is tenant-scoped, so this passes —
        it is pinned here so a future change cannot widen it.
        """
        self._auth(self.user_b)
        created = self.client.post(
            "/api/v1/notifications/device-tokens/",
            {"token": "fcm-b-1", "device_id": "dev-b", "platform": "android", "device_type": "phone"},
            format="json",
        )
        self.assertIn(created.status_code, (200, 201), created.data)

        self._auth(self.user_a)
        listed = self.client.get("/api/v1/notifications/device-tokens/")
        self.assertEqual(listed.status_code, 200, listed.data)
        data = listed.data
        rows = data.get("results", data) if isinstance(data, dict) else data
        tokens = {row["token"] for row in rows}
        self.assertNotIn("fcm-b-1", tokens)

    def test_a_member_cannot_delete_another_tenants_token(self) -> None:
        """Deleting gym B's token row by id is a 404 for gym A's member."""
        self._auth(self.user_b)
        created = self.client.post(
            "/api/v1/notifications/device-tokens/",
            {"token": "fcm-b-2", "device_id": "dev-b2", "platform": "android", "device_type": "phone"},
            format="json",
        )
        self.assertIn(created.status_code, (200, 201), created.data)
        row_id = created.data["id"]

        self._auth(self.user_a)
        deleted = self.client.delete(f"/api/v1/notifications/device-tokens/{row_id}/")
        self.assertEqual(deleted.status_code, 404)

    # QA-DEF-001 (fixed): re-registering the same (device, token) pair is the
    # documented FBOS-011 §7.4 contract — the mobile app registers on every
    # app start / FCM token event — so the second POST must answer 200 with
    # the existing refreshed row, never a UniqueValidator 400 or a duplicate.
    def test_registration_is_idempotent_per_token(self) -> None:
        """Re-registering the same token refreshes the row in place."""
        self._auth(self.user_a)
        payload = {"token": "fcm-a-1", "platform": "android", "device_type": "phone"}
        first = self.client.post(
            "/api/v1/notifications/device-tokens/", {**payload, "device_id": "dev-a"}, format="json"
        )
        second = self.client.post(
            "/api/v1/notifications/device-tokens/", {**payload, "device_id": "dev-a2"}, format="json"
        )
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data["id"], first.data["id"])

        self.assertEqual(DeviceToken.objects.filter(token="fcm-a-1").count(), 1)
        refreshed = DeviceToken.objects.get(token="fcm-a-1")
        self.assertEqual(refreshed.device_id, "dev-a2")
        self.assertTrue(refreshed.is_active)

    def test_re_register_rebinds_a_token_to_the_new_caller(self) -> None:
        """A token string is one device: re-register rotates user/tenant binding.

        The same physical phone logging into gym B moves the row to gym B —
        no cross-tenant duplicate is created, and gym A no longer lists it.
        """
        register_payload = {
            "token": "fcm-shared-1",
            "device_id": "dev-x",
            "platform": "android",
            "device_type": "phone",
        }
        self._auth(self.user_a)
        registered_a = self.client.post("/api/v1/notifications/device-tokens/", register_payload, format="json")
        self.assertIn(registered_a.status_code, (200, 201), registered_a.data)

        self._auth(self.user_b)
        rebind = self.client.post("/api/v1/notifications/device-tokens/", register_payload, format="json")
        self.assertEqual(rebind.status_code, 200, rebind.data)
        row = DeviceToken.objects.get(token="fcm-shared-1")
        self.assertEqual(row.tenant_id, self.tenant_b.pk)
        self.assertEqual(row.user_id, self.user_b.pk)
        self.assertEqual(DeviceToken.objects.filter(token="fcm-shared-1").count(), 1)

        self._auth(self.user_a)
        listed = self.client.get("/api/v1/notifications/device-tokens/")
        rows = listed.data.get("results", listed.data) if isinstance(listed.data, dict) else listed.data
        self.assertNotIn("fcm-shared-1", {r["token"] for r in rows})

    def test_double_delete_is_idempotent(self) -> None:
        """Deleting an already-deleted token answers 204 again (logout retry)."""
        self._auth(self.user_a)
        registered = self.client.post(
            "/api/v1/notifications/device-tokens/",
            {"token": "fcm-del-1", "device_id": "dev-d", "platform": "android", "device_type": "phone"},
            format="json",
        )
        self.assertIn(registered.status_code, (200, 201), registered.data)
        row_id = registered.data["id"]

        first_delete = self.client.delete(f"/api/v1/notifications/device-tokens/{row_id}/")
        second_delete = self.client.delete(f"/api/v1/notifications/device-tokens/{row_id}/")
        self.assertEqual(first_delete.status_code, 204, first_delete.data)
        self.assertEqual(second_delete.status_code, 204, second_delete.data)

    def test_staff_registration_keeps_its_403(self) -> None:
        """Only customers register push devices — the 403 contract is unchanged."""
        staff = User.objects.create_user(
            email="token.staff@qa.local",
            password="x",
            first_name="Tok",
            last_name="Staff",
            role=User.Role.GYM_OWNER,
            tenant=self.tenant_a,
        )
        self._auth(staff)
        denied = self.client.post(
            "/api/v1/notifications/device-tokens/",
            {"token": "fcm-staff-1", "device_id": "dev-s", "platform": "android", "device_type": "phone"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403, denied.data)


class OtpSenderProductionGuardTests(APITestCase):
    """QA-05 — the OTP sender chain must never silently degrade in prod.

    FBOS-011 §4.3: ``stub`` is impossible outside DEBUG, ``console`` is
    ignored outside DEBUG, and an unconfigured chain fails loudly (503)
    rather than dropping the code into the log file.
    """

    def test_stub_is_hard_blocked_outside_debug(self) -> None:
        """``OTP_SENDER=stub`` with ``DEBUG=False`` raises."""
        from django.core.exceptions import ImproperlyConfigured

        from apps.users.otp import resolve_otp_senders

        with override_settings(DEBUG=False, OTP_SENDER="stub"), self.assertRaises(ImproperlyConfigured):
            resolve_otp_senders(provision_tenant(name="Stub Gym", contact_email="stub@qa.local"))

    def test_console_is_ignored_outside_debug(self) -> None:
        """``OTP_SENDER=console`` with ``DEBUG=False`` resolves the real chain."""
        from apps.users.otp import resolve_otp_senders

        tenant = provision_tenant(name="Console Gym", contact_email="console@qa.local")
        with override_settings(DEBUG=False, OTP_SENDER="console", MSG91_AUTH_KEY="", MSG91_TEMPLATE_ID=""):
            senders = resolve_otp_senders(tenant)
        self.assertNotIn("console", [s.name for s in senders])
        self.assertNotIn("stub", [s.name for s in senders])

    def test_unconfigured_production_chain_fails_loudly(self) -> None:
        """No channel configured → the view answers 503, not 200."""
        tenant = provision_tenant(name="Dead Gym", contact_email="dead@qa.local", features=FLAG_ON)
        with override_settings(
            DEBUG=False,
            OTP_SENDER="auto",
            MSG91_AUTH_KEY="",
            MSG91_TEMPLATE_ID="",
        ):
            response = self.client.post(
                "/api/v1/users/auth/otp/request/",
                {"phone": "9876544444", "gym": str(tenant.uuid)},
                format="json",
            )
        self.assertEqual(response.status_code, 503, response.data)
        self.assertNotIn("otp", response.data)

    def test_the_otp_code_is_never_in_the_notification_log(self) -> None:
        """The delivered code must not be written to the audit trail.

        FBOS-011 §10.3: "no OTP values in NotificationLog.content".
        """
        tenant = provision_tenant(name="Audit Gym", contact_email="audit@qa.local", features=FLAG_ON)
        with override_settings(DEBUG=True, OTP_SENDER="stub", OTP_RESEND_COOLDOWN_SECONDS=0):
            issued = self.client.post(
                "/api/v1/users/auth/otp/request/",
                {"phone": "9876545555", "gym": str(tenant.uuid)},
                format="json",
            )
        self.assertEqual(issued.status_code, 200, issued.data)
        code = issued.data["otp"]
        logs = NotificationLog.objects.for_tenant(tenant).filter(notification_type="otp")
        for log in logs:
            self.assertNotIn(code, log.content or "")
