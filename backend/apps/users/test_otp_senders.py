"""OTP delivery chain tests (FBOS-011 §4): per-tenant sender resolution,
WATI/MSG91 contracts, prod-safety blocks, caps and audit logging."""

from unittest.mock import MagicMock

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from apps.notifications.models import NotificationLog
from apps.tenants.services import provision_tenant
from apps.users.otp import (
    ConsoleOtpSender,
    Msg91OtpSender,
    OtpDeliveryError,
    OtpError,
    StubOtpSender,
    WatiOtpSender,
    get_otp_sender,
    issue_otp,
    normalize_msisdn,
    resolve_otp_senders,
)

SMS_SETTINGS = {
    "SMS_PROVIDER": "msg91",
    "MSG91_AUTH_KEY": "test-auth-key",
    "MSG91_SENDER_ID": "FITNAT",
    "MSG91_TEMPLATE_ID": "dlt-otp-template",
}


class SenderResolutionTests(TestCase):
    """resolve_otp_senders per tenant + settings, and the prod-safety blocks."""

    def setUp(self) -> None:
        """A WATI-enabled tenant and a plain tenant."""
        self.wati_tenant = provision_tenant(
            name="Wati Gym",
            contact_email="wati@local.test",
            is_wati_enabled=True,
            wati_api_key="wati-key-123",
            wati_endpoint="https://api.wati.io/api/v1/sendSessionMessage",
        )
        self.plain_tenant = provision_tenant(name="Plain Gym", contact_email="plain@local.test")

    def test_debug_auto_resolves_console(self) -> None:
        """DEBUG + auto (default) → console sender (dev behavior kept)."""
        with override_settings(DEBUG=True, OTP_SENDER="auto"):
            chain = resolve_otp_senders(self.plain_tenant)
        self.assertEqual([s.name for s in chain], ["console"])

    def test_prod_auto_wati_then_sms(self) -> None:
        """Production auto: tenant WATI first, platform SMS second."""
        with override_settings(DEBUG=False, OTP_SENDER="auto", **SMS_SETTINGS):
            chain = resolve_otp_senders(self.wati_tenant)
            self.assertEqual([s.name for s in chain], ["wati", "sms"])
            # No WATI config → SMS only (no skipped noise)
            self.assertEqual([s.name for s in resolve_otp_senders(self.plain_tenant)], ["sms"])

    def test_prod_without_any_channel_is_empty_and_loud(self) -> None:
        """No channels anywhere → empty chain → issue_otp raises (503 path)."""
        with override_settings(DEBUG=False, OTP_SENDER="auto", SMS_PROVIDER="none", MSG91_AUTH_KEY=""):
            self.assertEqual(resolve_otp_senders(self.plain_tenant), [])

    def test_stub_hard_blocked_in_prod(self) -> None:
        """stub + DEBUG=False → ImproperlyConfigured (the prod blocker)."""
        with override_settings(DEBUG=False, OTP_SENDER="stub"):
            with self.assertRaises(ImproperlyConfigured):
                resolve_otp_senders(self.plain_tenant)
            with self.assertRaises(ImproperlyConfigured):
                get_otp_sender()

    def test_stub_allowed_in_debug(self) -> None:
        """stub + DEBUG=True → the code-echoing stub (tests only)."""
        with override_settings(DEBUG=True, OTP_SENDER="stub"):
            self.assertIsInstance(get_otp_sender(), StubOtpSender)

    def test_console_prod_guard_resolves_real_chain(self) -> None:
        """The console prod-guard resolves the production chain instead."""
        with self.assertLogs("apps.users.otp", level="WARNING") as logs:
            with override_settings(DEBUG=False, OTP_SENDER="console", **SMS_SETTINGS):
                chain = resolve_otp_senders(self.plain_tenant)
        self.assertEqual([s.name for s in chain], ["sms"])
        self.assertTrue(any("ignored" in line for line in logs.output))

    def test_forced_wati_and_sms_legs(self) -> None:
        """OTP_SENDER=wati/sms force exactly one leg (empty → loud 503)."""
        with override_settings(DEBUG=False, OTP_SENDER="wati", **SMS_SETTINGS):
            self.assertEqual([s.name for s in resolve_otp_senders(self.wati_tenant)], ["wati"])
            self.assertEqual(resolve_otp_senders(self.plain_tenant), [])
        with override_settings(DEBUG=False, OTP_SENDER="sms", SMS_PROVIDER="none", MSG91_AUTH_KEY=""):
            self.assertEqual(resolve_otp_senders(self.wati_tenant), [])


class WatiOtpSenderTests(TestCase):
    """The WATI template contract + endpoint normalization (§4.2)."""

    def setUp(self) -> None:
        """A WATI-configured tenant storing the legacy session-message URL."""
        self.tenant = provision_tenant(
            name="Wati Gym",
            contact_email="wati2@local.test",
            is_wati_enabled=True,
            wati_api_key="wati-key-123",
            wati_endpoint="https://api.wati.io/api/v1/sendSessionMessage",
        )

    def _poster(self):
        """A fake requests.post returning a 2xx response."""
        poster = MagicMock()
        poster.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        return poster

    def test_endpoint_normalization_from_session_url(self) -> None:
        """The stored session URL becomes the template endpoint."""
        url = WatiOtpSender.template_endpoint(
            "https://api.wati.io/api/v1/sendSessionMessage",
            "9199000000002",
            "fitnation_otp",
        )
        self.assertEqual(
            url,
            "https://api.wati.io/api/v1/sendTemplateMessage/fitnation_otp?whatsappNumber=9199000000002",
        )

    def test_endpoint_accepts_bare_base_too(self) -> None:
        """A tenant pasting the bare account base works identically."""
        url = WatiOtpSender.template_endpoint("https://api.wati.io", "9199000000002", "fitnation_otp")
        self.assertTrue(url.startswith("https://api.wati.io/api/v1/sendTemplateMessage/fitnation_otp"))

    def test_send_posts_template_params_with_auth_header(self) -> None:
        """Body carries [code, gym_name, ttl]; auth header is the tenant key."""
        poster = self._poster()
        sender = WatiOtpSender(self.tenant, poster=poster)
        sender.send_otp("+919900000002", "123456", tenant=self.tenant)
        args, kwargs = poster.call_args
        self.assertIn("sendTemplateMessage/fitnation_otp", args[0])
        self.assertIn("whatsappNumber=919900000002", args[0])
        self.assertEqual(kwargs["json"]["templateParams"], ["123456", "Wati Gym", "10"])
        self.assertEqual(kwargs["headers"]["Authorization"], "wati-key-123")

    def test_transport_failure_raises_delivery_error(self) -> None:
        """Any HTTP failure → OtpDeliveryError (chain falls through)."""
        poster = MagicMock()
        poster.side_effect = RuntimeError("boom")
        sender = WatiOtpSender(self.tenant, poster=poster)
        with self.assertRaises(OtpDeliveryError):
            sender.send_otp("+919900000002", "123456", tenant=self.tenant)

    def test_unconfigured_tenant_raises(self) -> None:
        """No WATI key → not even attempted."""
        plain = provision_tenant(name="No Wati", contact_email="nowati@local.test")
        sender = WatiOtpSender(plain, poster=self._poster())
        with self.assertRaises(OtpDeliveryError):
            sender.send_otp("+919900000002", "123456", tenant=plain)

    def test_tenant_daily_cap_skips_to_next_channel(self) -> None:
        """Exhausting the tenant's WATI OTP budget → skip straight to SMS."""
        cap = override_settings(TENANT_WATI_OTP_DAILY_CAP=0, DEBUG=False, **SMS_SETTINGS)
        cap.enable()
        self.addCleanup(cap.disable)
        poster = self._poster()
        sms_poster = self._poster()
        chain = [
            WatiOtpSender(self.tenant, poster=poster),
            Msg91OtpSender(poster=sms_poster),
        ]
        ttl = issue_otp("+919900000003", self.tenant, sender=chain)
        self.assertEqual(ttl, 600)
        poster.assert_not_called()  # WATI skipped
        sms_poster.assert_called_once()  # SMS carried delivery


class Msg91OtpSenderTests(TestCase):
    """The MSG91 flow API contract (§4.2)."""

    def test_send_posts_flow_payload(self) -> None:
        """authkey header + template_id + recipients variable map."""
        poster = MagicMock()
        poster.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        with override_settings(**SMS_SETTINGS):
            sender = Msg91OtpSender(poster=poster)
            sender.send_otp("+919900000004", "654321", tenant=None)
        args, kwargs = poster.call_args
        self.assertEqual(args[0], "https://control.msg91.com/api/v5/flow/")
        body = kwargs["json"]
        self.assertEqual(body["template_id"], "dlt-otp-template")
        self.assertEqual(body["short_url"], "0")
        self.assertEqual(
            body["recipients"],
            [{"mobiles": "919900000004", "OTP": "654321", "GYM": "FitNation"}],
        )
        self.assertEqual(kwargs["headers"], {"authkey": "test-auth-key"})

    def test_unconfigured_raises(self) -> None:
        """Missing credentials → delivery error, not a silent drop."""
        with override_settings(SMS_PROVIDER="msg91", MSG91_AUTH_KEY="", MSG91_TEMPLATE_ID=""):
            sender = Msg91OtpSender(poster=MagicMock())
            with self.assertRaises(OtpDeliveryError):
                sender.send_otp("+919900000004", "654321")


class IssueOtpChainTests(TestCase):
    """issue_otp walks the chain, logs attempts, and fails loudly (§4.1)."""

    def setUp(self) -> None:
        """A tenant with cooldown disabled for fast tests."""
        self.tenant = provision_tenant(name="Chain Gym", contact_email="chain@local.test")
        cooldown = override_settings(OTP_RESEND_COOLDOWN_SECONDS=0)
        cooldown.enable()
        self.addCleanup(cooldown.disable)

    def test_first_winning_sender_stops_the_chain(self) -> None:
        """Happy WATI → SMS never attempted."""
        wati = MagicMock()
        wati.name = "wati"
        sms = MagicMock()
        sms.name = "sms"
        issue_otp("+919900000005", self.tenant, sender=[wati, sms])
        wati.send_otp.assert_called_once()
        sms.send_otp.assert_not_called()

    def test_wati_down_falls_to_sms(self) -> None:
        """WATI raising → SMS carries the delivery."""
        wati = MagicMock()
        wati.name = "wati"
        wati.send_otp.side_effect = OtpDeliveryError("wati down")
        sms = MagicMock()
        sms.name = "sms"
        issue_otp("+919900000005", self.tenant, sender=[wati, sms])
        wati.send_otp.assert_called_once()
        sms.send_otp.assert_called_once()

    def test_all_channels_down_raises_and_logs_critical(self) -> None:
        """Every channel failing → OtpDeliveryError + CRITICAL log."""
        first = MagicMock()
        first.name = "wati"
        first.send_otp.side_effect = OtpDeliveryError("down1")
        second = MagicMock()
        second.name = "sms"
        second.send_otp.side_effect = OtpDeliveryError("down2")
        with self.assertLogs("apps.users.otp", level="CRITICAL") as logs:
            with self.assertRaises(OtpDeliveryError):
                issue_otp("+919900000005", self.tenant, sender=[first, second])
        self.assertTrue(any("all channels" in line for line in logs.output))

    def test_empty_chain_raises_loudly(self) -> None:
        """No configured channel → OtpDeliveryError (view → 503)."""
        with self.assertRaises(OtpDeliveryError):
            issue_otp("+919900000005", self.tenant, sender=[])

    def test_existing_caps_still_enforced(self) -> None:
        """The resend cooldown survives the chain refactor."""
        cooldown = override_settings(OTP_RESEND_COOLDOWN_SECONDS=60)
        cooldown.enable()
        self.addCleanup(cooldown.disable)
        ok = MagicMock()
        ok.name = "console"
        issue_otp("+919900000005", self.tenant, sender=ok)
        with self.assertRaises(OtpError):
            issue_otp("+919900000005", self.tenant, sender=ok)


class OtpAuditLogTests(TestCase):
    """Every real-channel attempt lands in NotificationLog — never the code."""

    def setUp(self) -> None:
        """Tenant + disabled cooldown."""
        self.tenant = provision_tenant(name="Audit Gym", contact_email="audit@local.test")
        cooldown = override_settings(OTP_RESEND_COOLDOWN_SECONDS=0)
        cooldown.enable()
        self.addCleanup(cooldown.disable)

    def test_success_row_has_channel_and_no_code(self) -> None:
        """A sent row records the channel; content never contains the code."""
        wati = MagicMock()
        wati.name = "wati"
        issue_otp("+919900000006", self.tenant, sender=wati)
        log = NotificationLog.objects.for_tenant(self.tenant).get(notification_type="otp")
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "wati")
        self.assertNotIn("123456", log.content)

    def test_failure_row_records_error(self) -> None:
        """A failed chain writes the failed row with the transport error."""
        sender = MagicMock()
        sender.name = "sms"
        sender.send_otp.side_effect = OtpDeliveryError("carrier down")
        with self.assertRaises(OtpDeliveryError):
            issue_otp("+919900000006", self.tenant, sender=sender)
        log = NotificationLog.objects.for_tenant(self.tenant).get(notification_type="otp")
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn("carrier down", log.error_message)

    def test_dev_senders_are_not_logged(self) -> None:
        """Console/stub attempts write no rows (dev noise control)."""
        console = ConsoleOtpSender()
        issue_otp("+919900000006", self.tenant, sender=console)
        self.assertEqual(NotificationLog.objects.filter(notification_type="otp").count(), 0)


class NormalizeMsisdnTests(TestCase):
    """Phone normalization for carrier payloads."""

    def test_bare_ten_digit_gets_country_code(self) -> None:
        """A bare 10-digit Indian number gains the 91 prefix."""
        self.assertEqual(normalize_msisdn("9876543210"), "919876543210")

    def test_plus_prefix_stripped(self) -> None:
        """+91 numbers normalize to bare digits."""
        self.assertEqual(normalize_msisdn("+919876543210"), "919876543210")

    def test_formatting_stripped(self) -> None:
        """Spaces/dashes are removed."""
        self.assertEqual(normalize_msisdn("+91 98765 43210"), "919876543210")
