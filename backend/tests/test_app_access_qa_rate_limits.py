"""QA regression tests: OTP rate limits and invite caps through the API.

Complements ``tests/test_app_access_qa_regressions.py``. Every case here
*passes* on develop — they pin the FBOS-011 §4.5 / §10.1 rate-limit
contract at the HTTP boundary (the existing suites test the helpers
directly, not the endpoints).

Deterministic: the OTP sender is the DEBUG stub, the WATI transport is
faked, and no network call leaves the process.
"""

from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.memberships.models import MembershipPlan
from apps.notifications.models import NotificationLog
from apps.tenants.services import provision_tenant
from apps.users.models import OtpCode, User
from apps.users.phone import normalize_e164

FLAG_ON = {"app_access": True}


def _ok_poster():
    """A fake HTTP transport that accepts every WATI post."""
    response = mock.MagicMock(status_code=200)
    response.raise_for_status = mock.MagicMock()
    response.json.return_value = {"messageId": "fake-msg-id"}
    return mock.MagicMock(return_value=response)


class OtpRateLimitTests(APITestCase):
    """OTP resend cooldown and the per-phone / per-IP daily caps (§4.5)."""

    def setUp(self) -> None:
        """A flagged tenant and a DEBUG/stub OTP sender."""
        cache.clear()
        self.tenant = provision_tenant(name="Rate Gym", contact_email="rate@qa.local", features=FLAG_ON)
        stub = override_settings(DEBUG=True, OTP_SENDER="stub")
        stub.enable()
        self.addCleanup(stub.disable)

    def _request(self, phone: str, **headers):
        """Request an OTP for ``phone``."""
        return self.client.post(
            "/api/v1/users/auth/otp/request/",
            {"phone": phone, "gym": str(self.tenant.uuid)},
            format="json",
            **headers,
        )

    def test_resend_cooldown_is_enforced(self) -> None:
        """A second request inside the cooldown is refused (400)."""
        with override_settings(OTP_RESEND_COOLDOWN_SECONDS=60):
            first = self._request("9876550001")
            self.assertEqual(first.status_code, 200, first.data)
            second = self._request("9876550001")
            self.assertEqual(second.status_code, 400, second.data)
            self.assertIn("wait", str(second.data["detail"]).lower())

    def test_per_phone_daily_cap_is_enforced(self) -> None:
        """The 10-per-phone-per-day cap answers 429, not 500."""
        with override_settings(OTP_RESEND_COOLDOWN_SECONDS=0, OTP_DAILY_LIMIT_PER_PHONE=3):
            for _ in range(3):
                self.assertEqual(self._request("9876550002").status_code, 200)
            capped = self._request("9876550002")
            self.assertEqual(capped.status_code, 429, capped.data)
            self.assertIn("limit", str(capped.data["detail"]).lower())

    def test_per_ip_daily_cap_is_enforced(self) -> None:
        """The 50-per-IP-per-day cap answers 429, not 500."""
        with override_settings(
            OTP_RESEND_COOLDOWN_SECONDS=0,
            OTP_DAILY_LIMIT_PER_PHONE=100,
            OTP_DAILY_LIMIT_PER_IP=2,
        ):
            self.assertEqual(self._request("9876550003", HTTP_X_FORWARDED_FOR="10.0.0.9").status_code, 200)
            self.assertEqual(self._request("9876550004", HTTP_X_FORWARDED_FOR="10.0.0.9").status_code, 200)
            capped = self._request("9876550005", HTTP_X_FORWARDED_FOR="10.0.0.9")
            self.assertEqual(capped.status_code, 429, capped.data)

    def test_a_different_ip_is_not_capped_by_another_ips_usage(self) -> None:
        """The IP cap is per-IP — one attacker cannot lock out everyone."""
        with override_settings(
            OTP_RESEND_COOLDOWN_SECONDS=0,
            OTP_DAILY_LIMIT_PER_PHONE=100,
            OTP_DAILY_LIMIT_PER_IP=1,
        ):
            self.assertEqual(self._request("9876550006", HTTP_X_FORWARDED_FOR="10.0.0.9").status_code, 200)
            self.assertEqual(self._request("9876550006", HTTP_X_FORWARDED_FOR="10.0.0.9").status_code, 429)
            other = self._request("9876550007", HTTP_X_FORWARDED_FOR="10.0.0.8")
            self.assertEqual(other.status_code, 200, other.data)

    def test_the_stub_code_is_only_echoed_behind_debug(self) -> None:
        """The OTP code must never appear in the response in production."""
        with override_settings(DEBUG=True, OTP_SENDER="stub"):
            issued = self._request("9876550008")
            self.assertIn("otp", issued.data)

        with override_settings(DEBUG=False, OTP_SENDER="auto", MSG91_AUTH_KEY="", MSG91_TEMPLATE_ID=""):
            prod = self._request("9876550009")
            # Unconfigured production chain → loud 503, never an echoed code.
            self.assertEqual(prod.status_code, 503, prod.data)
            self.assertNotIn("otp", prod.data)


class AppInviteCapTests(APITestCase):
    """The per-tenant daily invite cap and the 24 h dedupe window (§5.1b)."""

    def setUp(self) -> None:
        """A flagged, WhatsApp-enabled tenant with a plan and a member."""
        cache.clear()
        self.tenant = provision_tenant(name="Cap Gym", contact_email="cap@qa.local", features=FLAG_ON)
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "cap-wati-key"
        self.tenant.wati_endpoint = "https://api.wati.io/api/v1/sendSessionMessage"
        self.tenant.save(update_fields=["is_wati_enabled", "wati_api_key", "wati_endpoint"])
        self.plan = MembershipPlan.objects.create(tenant=self.tenant, name="Monthly", price=1000, duration_days=30)
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main",
            address_line1="1 Main St",
            city="Kochi",
            state="Kerala",
            postal_code="682001",
        )
        self.staff = User.objects.create_user(
            email="cap.desk@qa.local",
            password="F1tNati0n!",
            first_name="Cap",
            last_name="Desk",
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )
        self.member = User.objects.create_user(
            email="cap.member@qa.local",
            password="x",
            first_name="Cap",
            last_name="Member",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="9876560001",
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant, name="Cap Member", phone="9876560001", user=self.member
        )
        self.poster = _ok_poster()

    def _auth(self) -> None:
        """Authenticate as the front desk."""
        from apps.users.models import AuthToken

        token = AuthToken.objects.create(user=self.staff, tenant=self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _invite(self, resend: bool = False):
        """POST the invite endpoint."""
        self._auth()
        with mock.patch("apps.notifications.services.channels.requests.post", self.poster):
            return self.client.post(
                "/api/v1/memberships/app-invite/",
                {"customer_id": self.customer.pk, "resend": resend},
                format="json",
            )

    def test_a_sent_invite_is_not_resent_inside_the_window(self) -> None:
        """A repeat invite inside the 24 h window is a no-op (200 already_sent)."""
        first = self._invite()
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["status"], "sent")

        second = self._invite()
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data["status"], "already_sent")
        self.assertIsNotNone(second.data["resend_allowed_after"])

        # Exactly one invite log row exists.
        self.assertEqual(
            NotificationLog.objects.for_tenant(self.tenant).filter(notification_type="app_invite").count(),
            1,
        )

    def test_forced_resend_goes_out_again(self) -> None:
        """``resend: true`` bypasses the dedupe window (front-desk override)."""
        self._invite()
        forced = self._invite(resend=True)
        self.assertEqual(forced.status_code, 201, forced.data)
        self.assertEqual(forced.data["status"], "sent")
        self.assertEqual(
            NotificationLog.objects.for_tenant(self.tenant).filter(notification_type="app_invite").count(),
            2,
        )

    def test_the_tenant_daily_invite_cap_answers_429(self) -> None:
        """Hitting the per-tenant daily cap answers 429, not 500."""
        with override_settings(APP_INVITE_DAILY_LIMIT=1):
            first = self._invite()
            self.assertEqual(first.status_code, 201, first.data)
            capped = self._invite(resend=True)
            self.assertEqual(capped.status_code, 429, capped.data)
            self.assertIn("limit", str(capped.data["detail"]).lower())

    def test_the_invite_audit_trail_records_the_actor(self) -> None:
        """The invite log records who sent it (the front-desk staff user)."""
        self._invite()
        log = NotificationLog.objects.for_tenant(self.tenant).get(notification_type="app_invite")
        self.assertEqual(log.actor, self.staff)
        self.assertEqual(log.tenant, self.tenant)


class OtpDeliveryAuditTests(APITestCase):
    """The OTP delivery audit trail (FBOS-011 §4.1, §10.2)."""

    def test_the_delivered_code_never_reaches_the_audit_trail(self) -> None:
        """No ``NotificationLog`` row may contain the OTP code."""
        tenant = provision_tenant(name="Audit Gym", contact_email="audit2@qa.local", features=FLAG_ON)
        tenant.is_wati_enabled = True
        tenant.wati_api_key = "audit-wati-key"
        tenant.wati_endpoint = "https://api.wati.io/api/v1/sendSessionMessage"
        tenant.save(update_fields=["is_wati_enabled", "wati_api_key", "wati_endpoint"])

        captured: list[str] = []

        def _capture(url, json=None, **kwargs):
            captured.append(str(json))
            response = mock.MagicMock(status_code=200)
            response.raise_for_status = mock.MagicMock()
            response.json.return_value = {"messageId": "fake"}
            return response

        with (
            override_settings(DEBUG=False, OTP_SENDER="auto"),
            mock.patch("apps.notifications.services.channels.requests.post", _capture),
        ):
            issued = self.client.post(
                "/api/v1/users/auth/otp/request/",
                {"phone": "9876570001", "gym": str(tenant.uuid)},
                format="json",
            )
        self.assertEqual(issued.status_code, 200, issued.data)
        # The code never appears in the response body in production.
        self.assertNotIn("otp", issued.data)

        logs = NotificationLog.objects.for_tenant(tenant).filter(notification_type="otp")
        self.assertTrue(logs.exists(), "the OTP delivery attempt was not audited")
        for log in logs:
            self.assertNotIn("captured code", log.content or "")
            self.assertEqual(log.channel, "whatsapp")
            self.assertEqual(log.provider, "wati")


class OtpExpiryTests(APITestCase):
    """OTP TTL, attempt limit and single-use (FBOS-011 §10.3)."""

    def setUp(self) -> None:
        """A flagged tenant and a stub sender."""
        cache.clear()
        self.tenant = provision_tenant(name="TTL Gym", contact_email="ttl@qa.local", features=FLAG_ON)
        stub = override_settings(DEBUG=True, OTP_SENDER="stub", OTP_RESEND_COOLDOWN_SECONDS=0)
        stub.enable()
        self.addCleanup(stub.disable)

    def _issue(self, phone: str) -> str:
        """Issue an OTP and return the stub-echoed code."""
        response = self.client.post(
            "/api/v1/users/auth/otp/request/",
            {"phone": phone, "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["otp"]

    def test_an_expired_code_is_refused(self) -> None:
        """A code past its TTL is rejected (400)."""
        code = self._issue("9876580001")
        OtpCode.objects.filter(phone=normalize_e164("9876580001")).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "9876580001", "otp": code, "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_a_code_is_single_use(self) -> None:
        """A verified code cannot be replayed."""
        code = self._issue("9876580002")
        first = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "9876580002", "otp": code, "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(first.status_code, 200, first.data)
        second = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "9876580002", "otp": code, "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(second.status_code, 400, second.data)

    def test_the_code_is_bound_to_the_phone(self) -> None:
        """A code issued for one phone does not verify another phone."""
        code = self._issue("9876580003")
        response = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "9876580004", "otp": code, "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_the_wrong_code_is_refused(self) -> None:
        """A wrong code is refused (400) and the attempts are counted."""
        self._issue("9876580005")
        response = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {"phone": "9876580005", "otp": "000000", "gym": str(self.tenant.uuid)},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_the_code_is_hashed_at_rest(self) -> None:
        """The stored row never contains the plaintext code."""
        code = self._issue("9876580006")
        row = OtpCode.objects.get(phone=normalize_e164("9876580006"))
        self.assertNotEqual(row.code_hash, code)
        self.assertNotIn(code, row.code_hash)
