"""WhatsApp test-send + status endpoints (FBOS-011 §6).

Contract = ``frontend/lib/api.ts``:
- ``WhatsappTestResult`` → ``{status, detail?, provider, provider_status?,
  message_id?}`` where ``status`` is the ``NotificationLog`` status
  ("sent"/"failed"/"skipped"), failure modes are non-500, and
  ``provider_status``/``message_id`` echo the provider's verbatim response
  (issue #73).
- ``WhatsappStatus`` → ``{otp_sent_today, invites_sent_today, daily_cap}``.
"""

import json
from datetime import timedelta
from unittest import mock
from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.notifications.models import NotificationLog
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, User

TEST_URL = "/api/v1/tenants/whatsapp/test/"
STATUS_URL = "/api/v1/tenants/whatsapp/status/"

# The Gupshup test-send template is settings-driven (approved per tenant in
# the Gupshup console); the tests pin it so defaults can't drift silently.
TEST_TEMPLATE_SETTINGS = {
    "GUPSHUP_TEST_TEMPLATE_NAME": "fitnation_test_welcome",
    "GUPSHUP_TEST_TEMPLATE_PARAMS": "Test Runner,Test Gym",
}


class WhatsappActionTestBase(APITestCase):
    """Shared fixtures: configured tenant + owner + a staff non-owner."""

    def setUp(self) -> None:
        """Provision the tenant, owner, and manager; clear the throttle cache."""
        cache.clear()
        self.tenant = provision_tenant(name="Hash Fit", contact_email="hash@local.test")
        self.owner = User.objects.create_user(
            email="owner@hash.local",
            password="F1tNati0n!",
            first_name="Own",
            last_name="Er",
            role=User.Role.GYM_OWNER,
            tenant=self.tenant,
            is_owner=True,
        )
        self.manager = User.objects.create_user(
            email="manager@hash.local",
            password="F1tNati0n!",
            first_name="Man",
            last_name="Ager",
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )

    def auth(self, user: User) -> None:
        """Authenticate the test client as ``user``."""
        token = AuthToken.objects.create(user=user, tenant=user.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def configure_wati(self, tenant: Tenant) -> None:
        """Turn the tenant into a fully configured WATI setup."""
        tenant.is_wati_enabled = True
        tenant.wati_endpoint = "https://wati.example.com/api/v1/sendSessionMessage"
        tenant.wati_api_key = "secret-wati-key"
        tenant.save()


@override_settings(TENANT_WATI_OTP_DAILY_CAP=200)
class WhatsappTestSendTests(WhatsappActionTestBase):
    """POST /tenants/whatsapp/test/ — sends, logs, and never 500s on WATI issues."""

    def test_test_send_success(self) -> None:
        """A configured tenant gets status=sent and a logged attempt."""
        self.configure_wati(self.tenant)
        self.auth(self.owner)
        with mock.patch("apps.notifications.services.wati_service.requests.post") as post:
            post.return_value.raise_for_status = MagicMock()
            post.return_value.json = MagicMock(return_value={"messageId": "wamid.test"})
            response = self.client.post(TEST_URL, {"phone": "+919876543210"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "sent")
        self.assertEqual(response.data["provider"], "wati")
        self.assertEqual(response.data["message_id"], "wamid.test")

        log = NotificationLog.objects.for_tenant(self.tenant).latest("id")
        self.assertEqual(log.notification_type, NotificationLog.NotificationType.WELCOME)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.wati_message_id, "wamid.test")
        self.assertEqual(log.actor_id, self.owner.id)
        self.assertIsNone(log.customer)
        self.assertIn("+919876543210", log.content)

    def test_test_send_targets_the_request_phone(self) -> None:
        """The WATI payload's recipient is the submitted phone (no customer)."""
        self.configure_wati(self.tenant)
        self.auth(self.owner)
        with mock.patch(
            "apps.notifications.services.wati_service.requests.post",
        ) as post:
            post.return_value.raise_for_status = MagicMock()
            post.return_value.json = MagicMock(return_value={})
            response = self.client.post(TEST_URL, {"phone": "+919876543210"}, format="json")

        self.assertEqual(response.status_code, 200)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["to"], "+919876543210")

    def test_unconfigured_tenant_gets_clean_response(self) -> None:
        """WATI off → skipped (with detail), HTTP 200, logged, never a 500."""
        self.auth(self.owner)
        response = self.client.post(TEST_URL, {"phone": "+919876543210"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "skipped")
        self.assertIn("not enabled", response.data["detail"])
        log = NotificationLog.objects.for_tenant(self.tenant).latest("id")
        self.assertEqual(log.status, NotificationLog.Status.SKIPPED)

    def test_missing_api_key_gets_clean_response(self) -> None:
        """Enabled but keyless → status=failed with a meaningful detail."""
        self.tenant.is_wati_enabled = True
        self.tenant.save()
        self.auth(self.owner)
        response = self.client.post(TEST_URL, {"phone": "+919876543210"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "failed")
        self.assertIn("API key is not configured", response.data["detail"])

    def test_provider_error_gets_clean_failed_response(self) -> None:
        """A WATI transport failure becomes status=failed (never a 500)."""
        self.configure_wati(self.tenant)
        self.auth(self.owner)
        with mock.patch("apps.notifications.services.wati_service.requests.post") as post:
            post.side_effect = RuntimeError("connection refused")
            response = self.client.post(TEST_URL, {"phone": "+919876543210"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "failed")
        self.assertIn("connection refused", response.data["detail"])
        log = NotificationLog.objects.for_tenant(self.tenant).latest("id")
        self.assertEqual(log.status, NotificationLog.Status.FAILED)

    def test_phone_is_required(self) -> None:
        """An empty/missing phone is a 400, not a send."""
        self.configure_wati(self.tenant)
        self.auth(self.owner)
        response = self.client.post(TEST_URL, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            NotificationLog.objects.for_tenant(self.tenant)
            .filter(notification_type=NotificationLog.NotificationType.WELCOME)
            .exists()
        )

    def test_non_owner_gets_403(self) -> None:
        """A manager cannot trigger test sends."""
        self.configure_wati(self.tenant)
        self.auth(self.manager)
        response = self.client.post(TEST_URL, {"phone": "+919876543210"}, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            NotificationLog.objects.for_tenant(self.tenant)
            .filter(notification_type=NotificationLog.NotificationType.WELCOME)
            .count(),
            0,
        )

    def test_requires_authentication(self) -> None:
        """Anonymous test sends are rejected."""
        response = self.client.post(TEST_URL, {"phone": "+919876543210"}, format="json")

        self.assertEqual(response.status_code, 401)


@override_settings(TENANT_WATI_OTP_DAILY_CAP=200, **TEST_TEMPLATE_SETTINGS)
class GupshupTestSendTests(WhatsappActionTestBase):
    """provider=gupshup test sends (issue #66/#67) — the chosen BSP's own
    outcome, never a silent fallback to WATI."""

    def configure_gupshup(self, tenant: Tenant, **overrides) -> None:
        """Turn the tenant into a fully configured Gupshup setup."""
        defaults = {
            "is_gupshup_enabled": True,
            "gupshup_api_key": "secret-gup-key",
            "gupshup_source": "911234567890",
            "gupshup_app_name": "hash-fit-app",
        }
        defaults.update(overrides)
        for field, value in defaults.items():
            setattr(tenant, field, value)
        tenant.save()

    def test_gupshup_test_send_success(self) -> None:
        """provider=gupshup on a Gupshup-only tenant → sent + audited.

        (issue #73) The response carries the provider's verbatim status word.
        """
        self.configure_gupshup(self.tenant)
        self.auth(self.owner)
        with mock.patch("apps.notifications.services.channels.requests.post") as post:
            post.return_value.raise_for_status = MagicMock()
            post.return_value.json = MagicMock(return_value={"status": "success"})
            response = self.client.post(
                TEST_URL,
                {"phone": "+919876543210", "provider": "gupshup"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "sent")
        self.assertEqual(response.data["provider"], "gupshup")
        self.assertEqual(response.data["provider_status"], "success")
        _, kwargs = post.call_args
        self.assertEqual(kwargs["data"]["destination"], "919876543210")
        self.assertEqual(kwargs["data"]["source"], "911234567890")
        self.assertEqual(kwargs["headers"], {"apikey": "secret-gup-key"})
        log = NotificationLog.objects.for_tenant(self.tenant).latest("id")
        self.assertEqual(log.provider, "gupshup")
        self.assertEqual(log.channel, "whatsapp")

    def test_gupshup_test_send_delivers_an_approved_template_payload(self) -> None:
        """The gupshup leg sends a TEMPLATE message — not freeform text (issue #73).

        Freeform business-initiated text is provider-ACKed but silently never
        delivered; the approved template is what the tenant's real sends ride.
        """
        self.configure_gupshup(self.tenant)
        self.auth(self.owner)
        with mock.patch("apps.notifications.services.channels.requests.post") as post:
            post.return_value.raise_for_status = MagicMock()
            post.return_value.json = MagicMock(return_value={"status": "submitted", "messageId": "gs-1"})
            response = self.client.post(
                TEST_URL,
                {"phone": "+919876543210", "provider": "gupshup"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "sent")
        # The provider response verbatim on the wire + audited.
        self.assertEqual(response.data["provider_status"], "submitted")
        self.assertEqual(response.data["message_id"], "gs-1")
        _, kwargs = post.call_args
        sent_message = json.loads(kwargs["data"]["message"])
        self.assertEqual(sent_message["type"], "template")
        self.assertEqual(sent_message["name"], TEST_TEMPLATE_SETTINGS["GUPSHUP_TEST_TEMPLATE_NAME"])
        self.assertEqual(
            sent_message["params"],
            TEST_TEMPLATE_SETTINGS["GUPSHUP_TEST_TEMPLATE_PARAMS"].split(","),
        )
        log = NotificationLog.objects.for_tenant(self.tenant).latest("id")
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.wati_message_id, "gs-1")
        self.assertEqual(log.provider, "gupshup")

    def test_gupshup_test_send_fails_on_a_non_accepted_body_with_verbatim_text(self) -> None:
        """HTTP 2xx whose body is not an acceptance → failed, provider text verbatim."""
        self.configure_gupshup(self.tenant)
        self.auth(self.owner)
        with mock.patch("apps.notifications.services.channels.requests.post") as post:
            post.return_value.raise_for_status = MagicMock()
            post.return_value.json = MagicMock(
                return_value={"status": "error", "message": "Invalid message type"}
            )
            response = self.client.post(
                TEST_URL,
                {"phone": "+919876543210", "provider": "gupshup"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "failed")
        self.assertEqual(response.data["provider_status"], "error")
        self.assertIn("Invalid message type", response.data["detail"])
        log = NotificationLog.objects.for_tenant(self.tenant).latest("id")
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn("Invalid message type", log.error_message)

    def test_gupshup_test_send_surfaces_the_provider_error_body_verbatim(self) -> None:
        """A transport failure carries the provider's response body verbatim."""
        import requests as requests_lib

        self.configure_gupshup(self.tenant)
        self.auth(self.owner)
        http_error = requests_lib.HTTPError("500 Server Error for url")
        http_error.response = MagicMock(text='{"message": {"message": "Gupshup upstream exploded"}}')
        with mock.patch("apps.notifications.services.channels.requests.post") as post:
            post.side_effect = http_error
            response = self.client.post(
                TEST_URL,
                {"phone": "+919876543210", "provider": "gupshup"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "failed")
        # The verbatim provider body, not the requests exception summary.
        self.assertIn("Gupshup upstream exploded", response.data["detail"])
        log = NotificationLog.objects.for_tenant(self.tenant).latest("id")
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn("Gupshup upstream exploded", log.error_message)

    def test_gupshup_test_send_does_not_fall_back_to_wati(self) -> None:
        """provider=gupshup with Gupshup off → skipped even though WATI works."""
        self.configure_wati(self.tenant)
        self.auth(self.owner)
        with mock.patch("apps.notifications.services.wati_service.requests.post") as wati_post:
            response = self.client.post(
                TEST_URL,
                {"phone": "+919876543210", "provider": "gupshup"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "skipped")
        self.assertEqual(response.data["provider"], "gupshup")
        self.assertIn("Gupshup is not enabled", response.data["detail"])
        wati_post.assert_not_called()

    def test_gupshup_half_configured_fails_clean(self) -> None:
        """Enabled + key but no source number → failed with a named detail."""
        self.configure_gupshup(self.tenant, gupshup_source="", gupshup_app_name="")
        self.auth(self.owner)
        response = self.client.post(TEST_URL, {"phone": "+919876543210", "provider": "gupshup"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "failed")
        self.assertIn("source number", response.data["detail"])

    def test_default_provider_is_wati(self) -> None:
        """No provider in the body → the original WATI contract is kept."""
        self.configure_wati(self.tenant)
        self.auth(self.owner)
        with mock.patch("apps.notifications.services.wati_service.requests.post") as post:
            post.return_value.raise_for_status = MagicMock()
            post.return_value.json = MagicMock(return_value={"messageId": "wamid.w"})
            response = self.client.post(TEST_URL, {"phone": "+919876543210"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "sent")
        log = NotificationLog.objects.for_tenant(self.tenant).latest("id")
        self.assertEqual(log.provider, "wati")

    def test_invalid_provider_is_400(self) -> None:
        """An unknown provider name is a clean 400."""
        self.configure_wati(self.tenant)
        self.auth(self.owner)
        response = self.client.post(TEST_URL, {"phone": "+919876543210", "provider": "postmark"}, format="json")
        self.assertEqual(response.status_code, 400)


class WhatsappStatusTests(WhatsappActionTestBase):
    """GET /tenants/whatsapp/status/ returns today's three counters."""

    def test_status_returns_the_three_counters(self) -> None:
        """Counters reflect today's OTP/invite logs; cap comes from settings."""
        NotificationLog.objects.create(
            tenant=self.tenant,
            notification_type=NotificationLog.NotificationType.OTP,
            status=NotificationLog.Status.SENT,
        )
        NotificationLog.objects.create(
            tenant=self.tenant,
            notification_type=NotificationLog.NotificationType.OTP,
            status=NotificationLog.Status.FAILED,
        )
        NotificationLog.objects.create(
            tenant=self.tenant,
            notification_type=NotificationLog.NotificationType.APP_INVITE,
            status=NotificationLog.Status.SENT,
        )
        stale = NotificationLog.objects.create(
            tenant=self.tenant,
            notification_type=NotificationLog.NotificationType.OTP,
            status=NotificationLog.Status.SENT,
        )
        NotificationLog.objects.filter(id=stale.id).update(
            created_at=timezone.now() - timedelta(days=1),
        )
        # Another tenant's rows must not leak into the counters.
        other = provision_tenant(name="Other Gym", contact_email="other@local.test")
        NotificationLog.objects.create(
            tenant=other,
            notification_type=NotificationLog.NotificationType.OTP,
            status=NotificationLog.Status.SENT,
        )

        self.auth(self.owner)
        response = self.client.get(STATUS_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["otp_sent_today"], 2)
        self.assertEqual(response.data["invites_sent_today"], 1)
        self.assertEqual(response.data["daily_cap"], 200)
        for key in ("otp_sent_today", "invites_sent_today", "daily_cap"):
            self.assertIsInstance(response.data[key], int, key)

    def test_status_requires_authentication(self) -> None:
        """Anonymous status requests are rejected."""
        response = self.client.get(STATUS_URL)

        self.assertEqual(response.status_code, 401)
