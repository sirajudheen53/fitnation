"""Channel router tests (issue #66): the Gupshup transport contract, provider
ordering (WATI → Gupshup), recipient capability checks (synthetic emails are
never emailable), the WhatsApp fallback in ``send_notification``, and the
channel-aware verification delivery."""

import json
from unittest import mock
from unittest.mock import MagicMock

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.customers.models import Customer
from apps.notifications.models import NotificationLog
from apps.notifications.services import router as router_module
from apps.notifications.services.channels import GUPSHUP_MSG_URL, post_gupshup_template, post_gupshup_text
from apps.notifications.services.router import (
    gupshup_ready,
    is_emailable,
    send_verification_message,
    send_whatsapp_template,
    whatsapp_providers,
)
from apps.notifications.services.wati_service import send_notification
from apps.tenants.services import provision_tenant
from apps.users.models import User

GUPSHUP = {
    "is_gupshup_enabled": True,
    "gupshup_api_key": "gup-key",
    "gupshup_source": "911234567890",
    "gupshup_app_name": "hash-fit-app",
}


def _ok_poster():
    """A fake HTTP post that always succeeds."""
    poster = MagicMock()
    poster.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    return poster


def _posted_urls(poster) -> list[str]:
    """The URLs a fake poster was called with, in call order."""
    return [call.args[0] for call in poster.call_args_list]


class GupshupTransportTests(TestCase):
    """The Gupshup /wa/api/v1/msg HTTP contract (issue #66 requirement 2)."""

    def setUp(self) -> None:
        """A tenant with the full Gupshup configuration."""
        self.tenant = provision_tenant(name="Hash Fit", contact_email="hash@local.test", **GUPSHUP)

    def test_template_posts_form_encoded_contract(self) -> None:
        """channel/source/src.name/destination/message + apikey header."""
        poster = _ok_poster()
        post_gupshup_template(
            self.tenant,
            "fitnation_app_invite",
            "919900060001",
            ["Asha Nair", "Hash Fit", "Monthly", "https://app.example.com/g/x"],
            poster=poster,
        )
        args, kwargs = poster.call_args
        self.assertEqual(args[0], GUPSHUP_MSG_URL)
        body = kwargs["data"]
        self.assertEqual(body["channel"], "whatsapp")
        self.assertEqual(body["source"], "911234567890")
        self.assertEqual(body["src.name"], "hash-fit-app")
        self.assertEqual(body["destination"], "919900060001")
        self.assertEqual(
            json.loads(body["message"]),
            {
                "type": "template",
                "name": "fitnation_app_invite",
                "params": ["Asha Nair", "Hash Fit", "Monthly", "https://app.example.com/g/x"],
            },
        )
        self.assertEqual(kwargs["headers"], {"apikey": "gup-key"})

    def test_text_message_contract(self) -> None:
        """Session-window text rides the same endpoint with type=text."""
        poster = _ok_poster()
        post_gupshup_text(self.tenant, "919900060001", "Hi there 👋", poster=poster)
        _, kwargs = poster.call_args
        self.assertEqual(json.loads(kwargs["data"]["message"]), {"type": "text", "text": "Hi there 👋"})
        self.assertEqual(kwargs["headers"], {"apikey": "gup-key"})

    def test_provider_http_failure_raises(self) -> None:
        """raise_for_status is enforced here (callers decide the fallthrough)."""
        import requests

        poster = MagicMock()
        poster.return_value = MagicMock(
            status_code=500,
            raise_for_status=MagicMock(side_effect=requests.HTTPError("500")),
        )
        with self.assertRaises(requests.HTTPError):
            post_gupshup_template(self.tenant, "fitnation_otp", "919900060001", ["1", "2", "3"], poster=poster)


class ProviderOrderTests(TestCase):
    """whatsapp_providers: WATI first, then Gupshup; readiness gating."""

    def test_both_configured_order_wati_first(self) -> None:
        """Policy order is WATI → Gupshup regardless of configuration order."""
        tenant = provision_tenant(name="Both", contact_email="both@local.test", **GUPSHUP)
        tenant.is_wati_enabled = True
        tenant.wati_api_key = "wati-key"
        tenant.save()
        self.assertEqual(whatsapp_providers(tenant), ["wati", "gupshup"])
        self.assertEqual(whatsapp_providers(tenant, ready_only=True), ["wati", "gupshup"])

    def test_gupshup_only_tenant(self) -> None:
        """A Gupshup-only gym still gets a WhatsApp provider."""
        tenant = provision_tenant(name="Gup Only", contact_email="gup@local.test", **GUPSHUP)
        self.assertEqual(whatsapp_providers(tenant), ["gupshup"])

    def test_half_configured_gupshup_fails_readiness(self) -> None:
        """Enabled + key but no source/app is not ready (every send would fail)."""
        tenant = provision_tenant(
            name="Half",
            contact_email="half@local.test",
            is_gupshup_enabled=True,
            gupshup_api_key="gup-key",
        )
        self.assertFalse(gupshup_ready(tenant))
        self.assertEqual(whatsapp_providers(tenant), ["gupshup"])
        self.assertEqual(whatsapp_providers(tenant, ready_only=True), [])

    def test_disabled_channels_are_absent(self) -> None:
        """No channels enabled → empty list."""
        tenant = provision_tenant(name="Plain", contact_email="plain@local.test")
        self.assertEqual(whatsapp_providers(tenant), [])


class EmailableTests(TestCase):
    """The email capability check (synthetic OTP identities are excluded)."""

    def test_real_email_is_emailable(self) -> None:
        """A real mailbox passes."""
        self.assertTrue(is_emailable("trainer@gym.com"))

    def test_synthetic_email_is_never_emailable(self) -> None:
        """``…@fitnation.local`` identities have no mailbox behind them."""
        self.assertFalse(is_emailable("+919900000001.abc123@fitnation.local"))
        self.assertFalse(is_emailable("+919900000001@fitnation.local"))

    def test_blank_is_not_emailable(self) -> None:
        """No address → no email leg."""
        self.assertFalse(is_emailable(""))
        self.assertFalse(is_emailable(None))

    def test_domain_match_is_case_insensitive(self) -> None:
        """Casing tricks don't sneak a synthetic address past the check."""
        self.assertFalse(is_emailable("Someone@FitNation.Local"))


class SendWhatsappTemplateTests(TestCase):
    """send_whatsapp_template walks providers and reports the outcome."""

    def setUp(self) -> None:
        """A tenant with both WhatsApp providers ready."""
        self.tenant = provision_tenant(
            name="Both",
            contact_email="both2@local.test",
            is_wati_enabled=True,
            wati_api_key="wati-key",
            **GUPSHUP,
        )

    def test_wati_wins_when_it_delivers(self) -> None:
        """First provider that accepts short-circuits the walk."""
        poster = _ok_poster()
        attempt = send_whatsapp_template(self.tenant, "fitnation_app_invite", "919900060001", ["a"], poster=poster)
        self.assertTrue(attempt.sent)
        self.assertEqual(attempt.provider, "wati")
        urls = _posted_urls(poster)
        self.assertTrue(any("api.wati.io" in url for url in urls), urls)
        self.assertFalse(any("api.gupshup.io" in url for url in urls), urls)

    def test_wati_down_falls_to_gupshup(self) -> None:
        """A WATI transport failure is swallowed; Gupshup carries."""
        import requests

        def _post(url, **kwargs):
            if "api.wati.io" in url:
                raise requests.exceptions.ConnectionError("wati down")
            return MagicMock(status_code=200, raise_for_status=MagicMock())

        poster = MagicMock()
        poster.side_effect = _post
        attempt = send_whatsapp_template(self.tenant, "fitnation_app_invite", "919900060001", ["a"], poster=poster)
        self.assertTrue(attempt.sent)
        self.assertEqual(attempt.provider, "gupshup")
        self.assertEqual(attempt.error, "")

    def test_all_providers_down_reports_last_failure(self) -> None:
        """Everything failing → not sent, error from the last leg."""
        poster = MagicMock()
        poster.side_effect = RuntimeError("down")
        attempt = send_whatsapp_template(self.tenant, "fitnation_app_invite", "919900060001", ["a"], poster=poster)
        self.assertFalse(attempt.sent)
        self.assertEqual(attempt.provider, "gupshup")
        self.assertEqual(attempt.error, "down")

    def test_no_ready_provider_is_not_attempted(self) -> None:
        """Nothing configured → attempted=False (callers skip to SMS/email)."""
        plain = provision_tenant(name="Plain", contact_email="plain2@local.test")
        attempt = send_whatsapp_template(plain, "fitnation_app_invite", "919900060001", ["a"])
        self.assertFalse(attempt.attempted)
        self.assertFalse(attempt.sent)


class SendNotificationRoutingTests(TestCase):
    """send_notification as the WhatsApp channel router (signals/commands)."""

    def setUp(self) -> None:
        """A member with a phone on a tenant that starts with no channels."""
        self.tenant = provision_tenant(name="Route Gym", contact_email="route@local.test")
        user = User.objects.create_user(
            email="member@fitnation.local",
            password="x",
            first_name="R",
            last_name="M",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+919900070001",
        )
        self.customer = Customer.objects.create(tenant=self.tenant, user=user, name="RM", phone="+919900070001")

    def _configure_gupshup(self) -> None:
        """Turn on the tenant's Gupshup leg."""
        for field, value in GUPSHUP.items():
            setattr(self.tenant, field, value)
        self.tenant.save()

    def test_gupshup_only_tenant_sends_via_gupshup(self) -> None:
        """Only Gupshup configured → the send rides it, audited as such."""
        self._configure_gupshup()
        poster = _ok_poster()
        log = send_notification(self.tenant, self.customer, "check_in", {}, poster=poster)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "whatsapp")
        self.assertEqual(log.provider, "gupshup")
        self.assertEqual(_posted_urls(poster), [GUPSHUP_MSG_URL])
        _, kwargs = poster.call_args
        self.assertEqual(kwargs["data"]["destination"], "919900070001")

    def test_wati_failure_falls_through_to_gupshup(self) -> None:
        """WATI transport failing → Gupshup delivers; log names Gupshup."""
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "wati-key"
        self.tenant.save()
        self._configure_gupshup()
        failing_sender = MagicMock(side_effect=RuntimeError("wati down"))
        log = send_notification(self.tenant, self.customer, "check_in", {}, sender=failing_sender, poster=_ok_poster())
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.provider, "gupshup")

    def test_all_providers_failing_is_failed(self) -> None:
        """Every enabled provider failing → failed with the last error."""
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "wati-key"
        self.tenant.save()
        self._configure_gupshup()
        log = send_notification(
            self.tenant,
            self.customer,
            "check_in",
            {},
            sender=MagicMock(side_effect=RuntimeError("wati down")),
            poster=MagicMock(side_effect=RuntimeError("gupshup down")),
        )
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertEqual(log.provider, "gupshup")
        self.assertIn("gupshup down", log.error_message)

    def test_forced_provider_reports_only_itself(self) -> None:
        """provider=gupshup on a WATI-only tenant → skipped, no send."""
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "wati-key"
        self.tenant.save()
        log = send_notification(self.tenant, self.customer, "check_in", {}, provider="gupshup")
        self.assertEqual(log.status, NotificationLog.Status.SKIPPED)
        self.assertIn("Gupshup is not enabled", log.error_message)

    def test_no_phone_is_skipped(self) -> None:
        """The capability check: WhatsApp needs a phone."""
        self._configure_gupshup()
        self.customer.phone = ""
        self.customer.save(update_fields=["phone"])
        log = send_notification(self.tenant, self.customer, "check_in", {})
        self.assertEqual(log.status, NotificationLog.Status.SKIPPED)
        self.assertIn("phone", log.error_message.lower())


class SendVerificationMessageTests(TestCase):
    """The verification-link delivery policy (trainer/staff + customer)."""

    def setUp(self) -> None:
        """A tenant with no channels and a staff user with phone + email."""
        self.tenant = provision_tenant(name="Verify Gym", contact_email="verify@local.test")
        self.user = User.objects.create_user(
            email="trainer@gym.test",
            password="x",
            first_name="T",
            last_name="R",
            role=User.Role.TRAINER,
            tenant=self.tenant,
            phone="+919900080001",
        )

    def _configure_wati(self) -> None:
        """Enable a working-by-default WATI leg."""
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "wati-key"
        self.tenant.save(update_fields=["is_wati_enabled", "wati_api_key"])

    def test_wati_carries_and_email_is_never_attempted(self) -> None:
        """Only WhatsApp configured → WhatsApp delivers; SendGrid is untouched."""
        self._configure_wati()
        wati = mock.patch.object(
            router_module,
            "post_wati_session_text",
            return_value=("wamid.1", ""),
        )
        email = mock.patch("apps.core.services.email.send_verification_email", return_value=True)
        with wati as wati_mock, email as email_mock:
            log = send_verification_message(self.user)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "whatsapp")
        self.assertEqual(log.provider, "wati")
        wati_mock.assert_called_once()
        email_mock.assert_not_called()
        self.assertIn("verify-email/", log.content)

    def test_wati_down_gupshup_carries(self) -> None:
        """WATI failing → Gupshup delivers the verification link."""
        self._configure_wati()
        for field, value in GUPSHUP.items():
            setattr(self.tenant, field, value)
        self.tenant.save()
        with (
            mock.patch.object(router_module, "post_wati_session_text", return_value=("", "wati down")),
            mock.patch("apps.core.services.email.send_verification_email", return_value=True) as email_mock,
        ):
            log = send_verification_message(self.user, poster=_ok_poster())
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.provider, "gupshup")
        email_mock.assert_not_called()

    def test_no_channels_email_is_last_resort(self) -> None:
        """No messaging channel → the email leg delivers (SendGrid provider)."""
        with mock.patch("apps.core.services.email.send_verification_email", return_value=True) as email_mock:
            log = send_verification_message(self.user)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "email")
        self.assertEqual(log.provider, "sendgrid")
        email_mock.assert_called_once()

    def test_email_transport_failure_is_audited_failed(self) -> None:
        """An unusable email transport (SendGrid unconfigured) is audited as
        FAILED with the error — never a silent ``SENT`` (issue #66 audit
        rule; this is the shape CI hit with a keyless dev environment)."""
        with mock.patch("apps.core.services.email.send_verification_email", return_value=False):
            log = send_verification_message(self.user)
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertEqual(log.channel, "email")
        self.assertEqual(log.provider, "sendgrid")
        self.assertEqual(log.error_message, "Email delivery failed")

    def test_wati_failure_falls_through_to_email_leg(self) -> None:
        """A failed WhatsApp leg with no other messaging channel → the email
        leg still runs (last resort) and the audit row names the provider
        that actually delivered."""
        self._configure_wati()
        with (
            mock.patch.object(router_module, "post_wati_session_text", return_value=("", "wati down")),
            mock.patch("apps.core.services.email.send_verification_email", return_value=True),
        ):
            log = send_verification_message(self.user)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "email")
        self.assertEqual(log.provider, "sendgrid")

    def test_synthetic_email_with_no_whatsapp_is_skipped(self) -> None:
        """A phone-keyed OTP identity (synthetic email) with no messaging
        channel is unreachable — skipped + audited, no send attempted."""
        self.user.email = "+919900080001.abc@fitnation.local"
        self.user.save(update_fields=["email"])
        with mock.patch("apps.core.services.email.send_verification_email") as email_mock:
            log = send_verification_message(self.user)
        self.assertEqual(log.status, NotificationLog.Status.SKIPPED)
        email_mock.assert_not_called()

    def test_no_phone_goes_straight_to_email(self) -> None:
        """A user without a phone skips the WhatsApp legs entirely."""
        self._configure_wati()
        self.user.phone = ""
        self.user.save(update_fields=["phone"])
        with (
            mock.patch.object(router_module, "post_wati_session_text") as wati_mock,
            mock.patch("apps.core.services.email.send_verification_email", return_value=True) as email_mock,
        ):
            log = send_verification_message(self.user)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "email")
        self.assertEqual(log.provider, "sendgrid")
        wati_mock.assert_not_called()
        email_mock.assert_called_once()

    def test_user_without_tenant_is_email_only_and_not_audited(self) -> None:
        """Platform-level accounts have no channel config; email runs alone
        and no NotificationLog row is written (the table requires a tenant)."""
        self.user.tenant = None
        with mock.patch("apps.core.services.email.send_verification_email", return_value=True):
            log = send_verification_message(self.user)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.provider, "sendgrid")
        self.assertIsNone(log.pk)
        self.assertFalse(NotificationLog.objects.filter(notification_type="email_verification").exists())


class ResendVerificationEndpointTests(APITestCase):
    """POST /users/auth/resend-verification/ rides the channel policy."""

    def setUp(self) -> None:
        """Tenant + unverified staff user with phone + real email."""
        self.tenant = provision_tenant(name="Resend Gym", contact_email="resend@local.test")
        self.user = User.objects.create_user(
            email="manager@gym.test",
            password="x",
            first_name="M",
            last_name="G",
            role=User.Role.MANAGER,
            tenant=self.tenant,
            phone="+919900090001",
        )

    def test_whatsapp_configured_carries_the_link(self) -> None:
        """With WATI on, the resend goes over WhatsApp — audited as such."""
        self.tenant.is_wati_enabled = True
        self.tenant.wati_api_key = "wati-key"
        self.tenant.save(update_fields=["is_wati_enabled", "wati_api_key"])
        with (
            mock.patch.object(router_module, "post_wati_session_text", return_value=("wamid.2", "")) as wati_mock,
            mock.patch("apps.core.services.email.send_verification_email") as email_mock,
        ):
            response = self.client.post("/api/v1/users/auth/resend-verification/", {"email": "manager@gym.test"})
        self.assertEqual(response.status_code, 200, response.data)
        wati_mock.assert_called_once()
        email_mock.assert_not_called()
        log = NotificationLog.objects.for_tenant(self.tenant).get(notification_type="email_verification")
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "whatsapp")
        self.assertEqual(log.provider, "wati")
