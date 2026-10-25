"""Firebase phone-auth login tests (FBOS-011 §3): the mobile contract at
``POST /api/v1/auth/firebase/`` — payload parity with OTP verify, verdict
mapping (401/429/503), the tenant anchor ladder, and the env-contract fail-
loud behavior of the verifier module. The Firebase verifier is MOCKED in the
endpoint tests — no network, no real tokens."""

import os
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

import requests
from firebase_admin import exceptions as fb_exceptions

from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.tenants.services import provision_tenant
from apps.users.auth import AuthToken
from apps.users.firebase_auth import (
    FirebaseRateLimited,
    FirebaseTokenError,
    FirebaseVerifierUnavailableError,
    firebase_verify_phone,
    get_firebase_app,
    reset_firebase_app,
    throttle_failed_verification,
)
from apps.users.models import User

FLAG_ON = {"app_access": True}

# The endpoint must fail closed when NEITHER credential source exists — the
# explicit override keeps the case hermetic against local env leakage.
FIREBASE_UNCONFIGURED = {"FIREBASE_CREDENTIALS": ""}


def _without_adc_env() -> dict:
    """A copy of the process env with the ADC variable stripped."""
    env = dict(os.environ)
    env.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    return env


class FirebaseAuthEndpointTests(APITestCase):
    """POST /api/v1/auth/firebase/: the OTP-verify contract over a Firebase
    ID token (verifier mocked — the convergence path is what's under test)."""

    def setUp(self) -> None:
        """Fresh tenant + plan; cleared cache and Firebase app cache.

        The LocMem cache survives between tests while rolled-back tests
        recycle pks/uuids, so throttle counters would leak — clear it. The
        firebase_admin SDK app registry is global too; ``reset_firebase_app``
        re-arms it for the next test's settings.
        """
        cache.clear()
        reset_firebase_app()
        self.addCleanup(reset_firebase_app)
        self.tenant = provision_tenant(name="Hash Fit", contact_email="hash@local.test", features=FLAG_ON)
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
        )
        stub.enable()
        self.addCleanup(stub.disable)

    # ── helpers ───────────────────────────────────────────────────────────

    def otp_verify(self, phone: str, gym: str | None = None):
        """Run the real OTP request+verify flow and return the response."""
        payload = {"phone": phone}
        if gym:
            payload["gym"] = gym
        issued = self.client.post("/api/v1/users/auth/otp/request/", payload, format="json")
        assert issued.status_code == 200, issued.data
        payload["otp"] = issued.data["otp"]
        return self.client.post("/api/v1/users/auth/otp/verify/", payload, format="json")

    def firebase_login(self, phone: str, gym: str | None = None, device_type: str | None = None):
        """POST the firebase route with the verifier mocked to return ``phone``."""
        payload = {"id_token": "firebase-id-token"}
        if gym:
            payload["gym"] = gym
        if device_type:
            payload["device_type"] = device_type
        with patch("apps.users.views.firebase_verify_phone", return_value=phone) as verifier:
            response = self.client.post("/api/v1/auth/firebase/", payload, format="json")
        verifier.assert_called_once_with("firebase-id-token")
        return response

    def failed_firebase_login(self, error: Exception, gym: str | None = None):
        """POST the firebase route with the verifier raising ``error``."""
        payload = {"id_token": "firebase-id-token"}
        if gym:
            payload["gym"] = gym
        with patch("apps.users.views.firebase_verify_phone", side_effect=error):
            return self.client.post("/api/v1/auth/firebase/", payload, format="json")

    def create_member(self, phone: str, tenant=None, with_membership: bool = True) -> User:
        """Create a customer user (optionally with an active membership)."""
        tenant = tenant or self.tenant
        user = User.objects.create_user(
            email=f"{phone.replace('+', '')}.{tenant.uuid}@fitnation.local",
            password="x",
            first_name="Mem",
            last_name="Ber",
            role=User.Role.CUSTOMER,
            tenant=tenant,
            phone=phone,
        )
        Customer.objects.create(tenant=tenant, user=user, name="Mem Ber", phone=phone)
        if with_membership:
            Membership.objects.create(
                tenant=tenant,
                customer=user.customer_profile,
                plan=self.plan,
                start_date=timezone.localdate() - timedelta(days=10),
                end_date=timezone.localdate() + timedelta(days=20),
            )
        return user

    # ── response parity with OTP verify ──────────────────────────────────

    def test_valid_token_returns_identical_payload_as_otp_verify(self) -> None:
        """The same phone+anchor converges to the SAME user, permissions and
        entitlement object whichever route carried the credential."""
        phone = "+919900600001"
        gym = str(self.tenant.uuid)
        self.create_member(phone)

        otp_response = self.otp_verify(phone, gym=gym)
        firebase_response = self.firebase_login(phone, gym=gym)

        self.assertEqual(firebase_response.status_code, 200)
        self.assertEqual(sorted(firebase_response.data.keys()), sorted(otp_response.data.keys()))
        self.assertEqual(firebase_response.data["user"], otp_response.data["user"])
        self.assertEqual(firebase_response.data["permissions"], otp_response.data["permissions"])
        self.assertEqual(firebase_response.data["entitlement"], otp_response.data["entitlement"])
        self.assertTrue(firebase_response.data["token"])

    def test_unknown_phone_auto_provisions_with_identical_shape(self) -> None:
        """Unknown phone: identity created, entitlement none, and the response
        keys are IDENTICAL to an entitled member's (no registration reveal)."""
        gym = str(self.tenant.uuid)
        self.create_member("+919900600002")
        entitled = self.firebase_login("+919900600002", gym=gym)

        unknown = self.firebase_login("+919900600003", gym=gym)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(sorted(unknown.data.keys()), sorted(entitled.data.keys()))
        self.assertEqual(
            sorted(unknown.data["entitlement"].keys()),
            sorted(entitled.data["entitlement"].keys()),
        )
        self.assertNotIn("app.access", unknown.data["permissions"])
        self.assertEqual(unknown.data["entitlement"]["status"], "none")

        # The issued token is a real session (customer role + tenant context).
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {unknown.data['token']}")
        me = self.client.get("/api/v1/users/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["user"]["id"], unknown.data["user"]["id"])
        user = User.objects.get(pk=unknown.data["user"]["id"])
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(user.phone, "+919900600003")

    def test_device_type_defaults_android_and_honors_explicit(self) -> None:
        """The mobile-path default is android; an explicit type is honored."""
        gym = str(self.tenant.uuid)
        default = self.firebase_login("+919900600004", gym=gym)
        self.assertEqual(
            AuthToken.objects.get(key=default.data["token"]).device_type,
            AuthToken.DeviceType.ANDROID,
        )
        explicit = self.firebase_login("+919900600004", gym=gym, device_type=AuthToken.DeviceType.IOS)
        self.assertEqual(
            AuthToken.objects.get(key=explicit.data["token"]).device_type,
            AuthToken.DeviceType.IOS,
        )

    # ── token verdict mapping ────────────────────────────────────────────

    def test_invalid_expired_and_forged_tokens_are_401(self) -> None:
        """Every unverifiable token maps to 401 and creates NOTHING."""
        gym = str(self.tenant.uuid)
        failures = [
            FirebaseTokenError("Firebase ID token has invalid signature."),
            FirebaseTokenError("Firebase ID token has expired."),
            FirebaseTokenError("Firebase ID token has incorrect aud claim."),
        ]
        for error in failures:
            with self.subTest(error=str(error)):
                response = self.failed_firebase_login(error, gym=gym)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.data["detail"], str(error))
        self.assertEqual(User.objects.filter(phone__startswith="+919900601").count(), 0)
        self.assertEqual(AuthToken.objects.count(), 0)

    def test_verifier_runtime_failure_is_503(self) -> None:
        """A verifier broken at runtime (transport/backend) is a loud 503,
        never a 401 masquerading as a rejected token."""
        response = self.failed_firebase_login(
            FirebaseVerifierUnavailableError("public cert fetch failed"),
            gym=str(self.tenant.uuid),
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "firebase_auth_unavailable")

    def test_unconfigured_verifier_fails_closed_with_loud_503(self) -> None:
        """No credentials anywhere → loud 503 naming the env contract, plus a
        CRITICAL log entry for ops (fail closed — never accept the wrong
        project's tokens)."""
        with (
            override_settings(**FIREBASE_UNCONFIGURED),
            patch.dict(os.environ, _without_adc_env(), clear=True),
            self.assertLogs("apps.users.views", level="CRITICAL") as logs,
        ):
            response = self.client.post("/api/v1/auth/firebase/", {"id_token": "x"}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "firebase_auth_misconfigured")
        self.assertIn("FIREBASE_CREDENTIALS", str(response.data["detail"]))
        self.assertTrue(any("Firebase auth misconfigured" in line for line in logs.output))

    # ── tenant anchor ladder (same semantics as the OTP views) ───────────

    def test_phone_at_two_gyms_returns_select_gym_disambiguation(self) -> None:
        """No anchor + phone registered at several gyms → the same 200
        select_gym payload as OTP verify (never a token)."""
        other = provision_tenant(name="Gym B", contact_email="b@local.test", features=FLAG_ON)
        phone = "+919900600005"
        self.create_member(phone, tenant=self.tenant, with_membership=False)
        self.create_member(phone, tenant=other, with_membership=False)

        response = self.firebase_login(phone)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["action"], "select_gym")
        self.assertCountEqual(
            [g["tenant"] for g in response.data["gyms"]],
            [str(self.tenant.uuid), str(other.uuid)],
        )
        self.assertNotIn("token", response.data)

    def test_unknown_phone_without_anchor_is_generic_400(self) -> None:
        """No anchor + zero matches → the unchanged non-enumerating 400."""
        response = self.firebase_login("+919900600006")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Specify your gym", str(response.data))

    def test_unknown_gym_anchor_is_400(self) -> None:
        """A bogus anchor is rejected, never silently ignored."""
        response = self.firebase_login("+919900600007", gym=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["gym"], "Unknown gym.")

    # ── failed-verification rate limit ───────────────────────────────────

    def test_failures_429_past_daily_cap(self) -> None:
        """Past ``FIREBASE_VERIFY_DAILY_LIMIT_PER_IP`` failures the route
        answers 429 with the same generic copy as the OTP caps."""
        cap = override_settings(FIREBASE_VERIFY_DAILY_LIMIT_PER_IP=2)
        cap.enable()
        self.addCleanup(cap.disable)
        gym = str(self.tenant.uuid)

        self.assertEqual(self.failed_firebase_login(FirebaseTokenError("bad"), gym=gym).status_code, 401)
        self.assertEqual(self.failed_firebase_login(FirebaseTokenError("bad"), gym=gym).status_code, 401)
        limited = self.failed_firebase_login(FirebaseTokenError("bad"), gym=gym)

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.data, {"detail": "Too many requests. Try again later."})

    def test_successful_logins_never_count_toward_failure_cap(self) -> None:
        """Successes never increment the counter — a shared gym NAT cannot be
        locked out by legitimate members logging in."""
        cap = override_settings(FIREBASE_VERIFY_DAILY_LIMIT_PER_IP=1)
        cap.enable()
        self.addCleanup(cap.disable)
        gym = str(self.tenant.uuid)

        self.assertEqual(self.firebase_login("+919900600008", gym=gym).status_code, 200)
        # One failure fits under the cap (cap is on FAILURES only)…
        self.assertEqual(self.failed_firebase_login(FirebaseTokenError("bad"), gym=gym).status_code, 401)
        # …the second failure trips it.
        self.assertEqual(self.failed_firebase_login(FirebaseTokenError("bad"), gym=gym).status_code, 429)


class FirebaseVerifierModuleTests(TestCase):
    """firebase_auth.py unit behavior: env-contract failures are LOUD and
    verdicts map 1:1 to their HTTP class (no network anywhere)."""

    def setUp(self) -> None:
        cache.clear()
        reset_firebase_app()
        self.addCleanup(reset_firebase_app)

    def _stub_admin_app(self) -> None:
        """Stub the SDK app so no credential resolution is exercised."""
        patcher = patch("apps.users.firebase_auth.get_firebase_app", return_value=object())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_credentials_anywhere_is_loud(self) -> None:
        """Neither FIREBASE_CREDENTIALS nor ADC → ImproperlyConfigured."""
        with (
            override_settings(**FIREBASE_UNCONFIGURED),
            patch.dict(os.environ, _without_adc_env(), clear=True),
            self.assertRaises(ImproperlyConfigured) as caught,
        ):
            get_firebase_app()
        self.assertIn("No Firebase credentials configured", str(caught.exception))

    def test_missing_credentials_file_is_loud(self) -> None:
        """A FIREBASE_CREDENTIALS path that doesn't exist fails loudly."""
        with override_settings(FIREBASE_CREDENTIALS="/nonexistent/service-account.json"):
            with self.assertRaises(ImproperlyConfigured) as caught:
                get_firebase_app()
        self.assertIn("missing service-account file", str(caught.exception))

    def test_invalid_inline_credentials_json_is_loud(self) -> None:
        """Inline JSON that doesn't parse is a config error, not a token one."""
        with override_settings(FIREBASE_CREDENTIALS='{"type": "service_account",'):
            with self.assertRaises(ImproperlyConfigured):
                get_firebase_app()

    def test_missing_adc_file_is_loud(self) -> None:
        """GOOGLE_APPLICATION_CREDENTIALS pointing nowhere fails loudly."""
        env = _without_adc_env()
        env["GOOGLE_APPLICATION_CREDENTIALS"] = "/nonexistent/adc.json"
        with (
            override_settings(**FIREBASE_UNCONFIGURED),
            patch.dict(os.environ, env, clear=True),
            self.assertRaises(ImproperlyConfigured) as caught,
        ):
            get_firebase_app()
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", str(caught.exception))

    def test_empty_project_id_is_loud(self) -> None:
        """An empty FIREBASE_PROJECT_ID is rejected before any credential use."""
        with (
            override_settings(FIREBASE_PROJECT_ID=""),
            patch("apps.users.firebase_auth._resolve_credential", return_value=object()),
            self.assertRaises(ImproperlyConfigured) as caught,
        ):
            get_firebase_app()
        self.assertIn("FIREBASE_PROJECT_ID", str(caught.exception))

    def test_valid_token_returns_e164_phone(self) -> None:
        """The phone_number claim is returned as-is (already E.164)."""
        self._stub_admin_app()
        decoded = {"sub": "firebase-uid", "phone_number": "+919876543210"}
        with patch("firebase_admin.auth.verify_id_token", return_value=decoded):
            self.assertEqual(firebase_verify_phone("tok"), "+919876543210")

    def test_token_without_phone_claim_is_rejected(self) -> None:
        """Non-phone-auth logins (email/google) never converge an identity."""
        self._stub_admin_app()
        with patch("firebase_admin.auth.verify_id_token", return_value={"sub": "uid", "email": "x@y.z"}):
            with self.assertRaises(FirebaseTokenError) as caught:
                firebase_verify_phone("tok")
        self.assertIn("phone_number", str(caught.exception))

    def test_sdk_invalid_token_maps_to_401_class(self) -> None:
        """Invalid/expired/revoked (InvalidArgumentError family) → token error."""
        self._stub_admin_app()
        with patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=fb_exceptions.InvalidArgumentError("Token has expired."),
        ):
            with self.assertRaises(FirebaseTokenError):
                firebase_verify_phone("tok")

    def test_sdk_backend_error_maps_to_503_class(self) -> None:
        """Firebase backend errors are availability failures, not rejections."""
        self._stub_admin_app()
        with patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=fb_exceptions.FirebaseError("INTERNAL", "boom", None),
        ):
            with self.assertRaises(FirebaseVerifierUnavailableError):
                firebase_verify_phone("tok")

    def test_transport_error_maps_to_503_class(self) -> None:
        """Cert-fetch transport problems are availability failures too."""
        self._stub_admin_app()
        with patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=requests.ConnectionError("no route to host"),
        ):
            with self.assertRaises(FirebaseVerifierUnavailableError):
                firebase_verify_phone("tok")


class FailedVerificationThrottleTests(TestCase):
    """The per-IP daily cap on FAILED verifications (cache counter, fail-open
    on cache loss — the same contract as the OTP per-IP caps)."""

    def setUp(self) -> None:
        cache.clear()

    def test_raises_past_cap(self) -> None:
        """The (cap+1)-th failure for one IP raises; the cap-th passes."""
        with override_settings(FIREBASE_VERIFY_DAILY_LIMIT_PER_IP=2):
            throttle_failed_verification("1.2.3.4")
            throttle_failed_verification("1.2.3.4")
            with self.assertRaises(FirebaseRateLimited):
                throttle_failed_verification("1.2.3.4")

    def test_ips_are_independent(self) -> None:
        """One exhausted IP never locks out another."""
        with override_settings(FIREBASE_VERIFY_DAILY_LIMIT_PER_IP=1):
            throttle_failed_verification("1.1.1.1")
            with self.assertRaises(FirebaseRateLimited):
                throttle_failed_verification("1.1.1.1")
            throttle_failed_verification("2.2.2.2")  # fresh IP: fine

    def test_missing_ip_skips_the_throttle(self) -> None:
        """No client IP (proxy edge case) → nothing counted, nothing raised."""
        with override_settings(FIREBASE_VERIFY_DAILY_LIMIT_PER_IP=0):
            throttle_failed_verification(None)
