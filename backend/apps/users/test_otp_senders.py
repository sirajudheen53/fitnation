"""OTP delivery chain tests (FBOS-011 §4): per-tenant sender resolution,
WATI/Gupshup/MSG91 contracts, prod-safety blocks, caps, audit logging, and
the machine-readable failure diagnostics (issues #59, #66)."""

import json
from unittest.mock import MagicMock

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

import requests

from apps.notifications.models import NotificationLog
from apps.notifications.services.channels import (
    GUPSHUP_MSG_URL,
    approved_template_names_from_env,
    gupshup_template_status,
    parse_gupshup_template_status,
)
from apps.tenants.services import provision_tenant
from apps.users.otp import (
    ConsoleOtpSender,
    GupshupOtpSender,
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

GUPSHUP_CONFIG = {
    "is_gupshup_enabled": True,
    "gupshup_api_key": "gup-key",
    "gupshup_source": "911234567890",
    "gupshup_app_name": "hash-fit-app",
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

    def test_empty_chain_error_carries_channel_diagnostics(self) -> None:
        """The empty-chain raise names all three legs as not_configured (#59, #66)."""
        with (
            override_settings(DEBUG=False, OTP_SENDER="auto", SMS_PROVIDER="none", MSG91_AUTH_KEY=""),
            self.assertRaises(OtpDeliveryError) as caught,
        ):
            issue_otp("+919900000007", self.plain_tenant, sender=resolve_otp_senders(self.plain_tenant))
        self.assertEqual(caught.exception.reason, "not_configured")
        self.assertEqual(
            caught.exception.channels,
            [
                {"channel": "wati", "reason": "not_configured"},
                {"channel": "gupshup", "reason": "not_configured"},
                {"channel": "sms", "reason": "not_configured"},
            ],
        )

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
        with (
            self.assertLogs("apps.users.otp", level="WARNING") as logs,
            override_settings(DEBUG=False, OTP_SENDER="console", **SMS_SETTINGS),
        ):
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
        with self.assertRaises(OtpDeliveryError) as caught:
            sender.send_otp("+919900000002", "123456", tenant=self.tenant)
        self.assertEqual(caught.exception.reason, "transport_error")

    def test_http_failure_reason_carries_status_code(self) -> None:
        """A provider HTTP error → reason ``http_<status>`` (no secret/body)."""
        response = requests.Response()
        response.status_code = 401
        poster = MagicMock()
        poster.return_value = MagicMock(
            status_code=401, raise_for_status=MagicMock(side_effect=requests.HTTPError("401", response=response))
        )
        sender = WatiOtpSender(self.tenant, poster=poster)
        with self.assertRaises(OtpDeliveryError) as caught:
            sender.send_otp("+919900000002", "123456", tenant=self.tenant)
        self.assertEqual(caught.exception.reason, "http_401")

    def test_daily_cap_error_reason(self) -> None:
        """The budget guard fails with reason ``daily_cap_reached``."""
        cap = override_settings(TENANT_WATI_OTP_DAILY_CAP=0)
        cap.enable()
        self.addCleanup(cap.disable)
        sender = WatiOtpSender(self.tenant, poster=self._poster())
        with self.assertRaises(OtpDeliveryError) as caught:
            sender.send_otp("+919900000002", "123456", tenant=self.tenant)
        self.assertEqual(caught.exception.reason, "daily_cap_reached")

    def test_unconfigured_tenant_raises(self) -> None:
        """No WATI key → not even attempted."""
        plain = provision_tenant(name="No Wati", contact_email="nowati@local.test")
        sender = WatiOtpSender(plain, poster=self._poster())
        with self.assertRaises(OtpDeliveryError) as caught:
            sender.send_otp("+919900000002", "123456", tenant=plain)
        self.assertEqual(caught.exception.reason, "not_configured")

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
        result = issue_otp("+919900000003", self.tenant, sender=chain)
        self.assertEqual(result.expires_in, 600)
        self.assertEqual(result.channel, "sms")
        poster.assert_not_called()  # WATI skipped
        sms_poster.assert_called_once()  # SMS carried delivery


class GupshupTemplateStatusTests(TestCase):
    """The approval-status lookup backing the #74 delivery gate.

    Gupshup's /msg API 202-acks ANY submit (#73), so the only synchronous
    proof a template send can really deliver is the template-management API
    listing the name with status APPROVED (#74). Transport (#85): the list
    endpoint wants a PORTAL account key (the app key is rejected 401), so the
    gate order is portal-key live check → GUPSHUP_APPROVED_TEMPLATES env →
    fail closed.
    """

    DEFAULT_URL = "https://api.gupshup.io/sm/api/v1/template/list/hash-fit-app"

    def setUp(self) -> None:
        """A tenant with the full Gupshup configuration."""
        self.tenant = provision_tenant(name="Tpl Gym", contact_email="tpl@local.test", **GUPSHUP_CONFIG)

    @staticmethod
    def _response(payload) -> MagicMock:
        """A fake 2xx GET response carrying ``payload`` as JSON."""
        response = MagicMock(status_code=200)
        response.json.return_value = payload
        return response

    def test_parse_documented_shape(self) -> None:
        """The documented ``{"templates": [...]}`` shape parses by name."""
        payload = {
            "status": "success",
            "templates": [{"name": "welcome", "status": "APPROVED"}, {"name": "fitnation_otp", "status": "APPROVED"}],
        }
        self.assertEqual(parse_gupshup_template_status(payload, "fitnation_otp"), "APPROVED")

    def test_parse_bare_list_shape(self) -> None:
        """A bare template list parses identically."""
        self.assertEqual(
            parse_gupshup_template_status([{"name": "fitnation_otp", "status": "APPROVED"}], "fitnation_otp"),
            "APPROVED",
        )

    def test_parse_normalizes_status(self) -> None:
        """Status words are case/space normalized."""
        self.assertEqual(
            parse_gupshup_template_status([{"name": "fitnation_otp", "status": " approved "}], "fitnation_otp"),
            "APPROVED",
        )

    def test_parse_elementname_entry_shape(self) -> None:
        """Gupshup's other documented entry shape (elementName/templateName
        keys, wa/app/{id}/template flavour) parses too (#85)."""
        payload = {"templates": [{"elementName": "fitnation_otp", "status": "APPROVED"}]}
        self.assertEqual(parse_gupshup_template_status(payload, "fitnation_otp"), "APPROVED")
        bare = [{"elementName": "fitnation_otp", "templateStatus": "approved"}]
        self.assertEqual(parse_gupshup_template_status(bare, "fitnation_otp"), "APPROVED")

    def test_parse_missing_template_is_empty(self) -> None:
        """A name not in the list → "" (gate treats it as unapproved)."""
        self.assertEqual(
            parse_gupshup_template_status({"templates": [{"name": "welcome", "status": "APPROVED"}]}, "fitnation_otp"),
            "",
        )
        self.assertEqual(parse_gupshup_template_status({"templates": []}, "fitnation_otp"), "")

    def test_parse_pending_reports_pending(self) -> None:
        """A PENDING revision reports PENDING — not approved, not silent."""
        self.assertEqual(
            parse_gupshup_template_status([{"name": "fitnation_otp", "status": "PENDING"}], "fitnation_otp"),
            "PENDING",
        )

    def test_parse_any_approved_revision_wins(self) -> None:
        """Per-language revisions of one name: the approved one is the verdict."""
        payload = {
            "templates": [
                {"name": "fitnation_otp", "status": "REJECTED"},
                {"name": "fitnation_otp", "status": "APPROVED"},
            ]
        }
        self.assertEqual(parse_gupshup_template_status(payload, "fitnation_otp"), "APPROVED")

    def test_parse_unusable_payloads_are_empty(self) -> None:
        """None / junk shapes parse to "" — never raise."""
        self.assertEqual(parse_gupshup_template_status(None, "fitnation_otp"), "")
        self.assertEqual(parse_gupshup_template_status({"templates": "oops"}, "fitnation_otp"), "")
        self.assertEqual(parse_gupshup_template_status([{"status": "APPROVED"}], "fitnation_otp"), "")

    def test_portal_key_live_check_approves_and_fills_appname(self) -> None:
        """Portal-key gate: GET carries the portal key and the app name is
        substituted into the URL; a live APPROVED verdict wins."""
        captured = {}

        def getter(url, **kwargs):
            captured.update(kwargs, url=url)
            return self._response({"templates": [{"name": "fitnation_otp", "status": "APPROVED"}]})

        with override_settings(GUPSHUP_PORTAL_API_KEY="portal-key", GUPSHUP_APPROVED_TEMPLATES=""):
            status = gupshup_template_status(self.tenant, "fitnation_otp", getter=getter)
        self.assertEqual(status, "APPROVED")
        self.assertEqual(captured["url"], self.DEFAULT_URL)
        self.assertEqual(captured["headers"], {"apikey": "portal-key"})

    def test_portal_key_live_check_reports_negative_verdicts(self) -> None:
        """A usable live response is authoritative even when negative — the
        env allow-list must never override a working live check."""
        calls = []

        def getter(url, **kwargs):
            calls.append(url)
            return self._response({"templates": [{"name": "fitnation_otp", "status": "PENDING"}]})

        with override_settings(GUPSHUP_PORTAL_API_KEY="portal-key", GUPSHUP_APPROVED_TEMPLATES="fitnation_otp"):
            status = gupshup_template_status(self.tenant, "fitnation_otp", getter=getter)
        self.assertEqual(status, "PENDING")
        self.assertEqual(len(calls), 1)

    def test_portal_401_falls_through_to_approved_names_env(self) -> None:
        """The endpoint still refusing the call → the env allow-list decides."""
        calls = []

        def getter(url, **kwargs):
            calls.append(url)
            raise requests.ConnectionError("unreachable")

        with override_settings(GUPSHUP_PORTAL_API_KEY="portal-key", GUPSHUP_APPROVED_TEMPLATES="fitnation_otp"):
            self.assertEqual(gupshup_template_status(self.tenant, "fitnation_otp", getter=getter), "APPROVED")
            self.assertEqual(len(calls), 1)

    def test_portal_401_without_env_name_fails_closed(self) -> None:
        """Gate order ends in fail closed: unusable live check + unlisted
        name → "" (#74 semantics preserved)."""

        def getter(url, **kwargs):
            response = MagicMock(status_code=401)
            response.raise_for_status.side_effect = requests.HTTPError("401")
            response.json.return_value = {"message": "Portal User Not Found With APIKey"}
            return response

        with override_settings(GUPSHUP_PORTAL_API_KEY="portal-key", GUPSHUP_APPROVED_TEMPLATES="welcome"):
            self.assertEqual(gupshup_template_status(self.tenant, "fitnation_otp", getter=getter), "")

    def test_portal_junk_2xx_payload_falls_through_to_env(self) -> None:
        """A 2xx body without a usable template list is "no verdict" — the
        env allow-list is consulted, then the gate fails closed."""

        def getter(url, **kwargs):
            return self._response({"status": "error", "message": "boom"})

        with override_settings(GUPSHUP_PORTAL_API_KEY="portal-key", GUPSHUP_APPROVED_TEMPLATES="fitnation_otp"):
            self.assertEqual(gupshup_template_status(self.tenant, "fitnation_otp", getter=getter), "APPROVED")
        with override_settings(GUPSHUP_PORTAL_API_KEY="portal-key", GUPSHUP_APPROVED_TEMPLATES=""):
            self.assertEqual(gupshup_template_status(self.tenant, "fitnation_otp", getter=getter), "")

    def test_no_portal_key_never_calls_the_endpoint(self) -> None:
        """Without a portal key the list API cannot answer — the gate consults
        only the env allow-list and must not burn a GET."""
        getter = MagicMock()

        with override_settings(GUPSHUP_PORTAL_API_KEY="", GUPSHUP_APPROVED_TEMPLATES="fitnation_otp"):
            self.assertEqual(gupshup_template_status(self.tenant, "fitnation_otp", getter=getter), "APPROVED")
        with override_settings(GUPSHUP_PORTAL_API_KEY="", GUPSHUP_APPROVED_TEMPLATES="welcome"):
            self.assertEqual(gupshup_template_status(self.tenant, "fitnation_otp", getter=getter), "")
        getter.assert_not_called()

    def test_approved_names_env_is_whitespace_and_case_tolerant(self) -> None:
        """Ops-friendly parsing: spaces, empty segments, mixed case."""
        with override_settings(GUPSHUP_APPROVED_TEMPLATES=" welcome , , FitNation_OTP "):
            self.assertEqual(approved_template_names_from_env(), {"WELCOME", "FITNATION_OTP"})
        with override_settings(GUPSHUP_APPROVED_TEMPLATES=""):
            self.assertEqual(approved_template_names_from_env(), set())

    def test_url_setting_overrides_the_default_template(self) -> None:
        """A custom GUPSHUP_TEMPLATE_LIST_URL wins; {appname} is substituted."""
        captured = {}

        def getter(url, **kwargs):
            captured.update(kwargs, url=url)
            return self._response({"templates": [{"name": "fitnation_otp", "status": "APPROVED"}]})

        with override_settings(
            GUPSHUP_PORTAL_API_KEY="portal-key",
            GUPSHUP_TEMPLATE_LIST_URL="https://gupshup.example/sm/api/v1/template/list/{appname}",
        ):
            status = gupshup_template_status(self.tenant, "fitnation_otp", getter=getter)
        self.assertEqual(status, "APPROVED")
        self.assertEqual(captured["url"], "https://gupshup.example/sm/api/v1/template/list/hash-fit-app")
        self.assertEqual(captured["headers"], {"apikey": "portal-key"})


class GupshupOtpSenderTests(TestCase):
    """The Gupshup WhatsApp OTP contract (issue #66) — second BSP, same
    template variable map, /wa/api/v1/msg transport — plus the #74
    approved-template delivery gate on its 202-acks-anything submit API."""

    def setUp(self) -> None:
        """A tenant with the full Gupshup configuration."""
        # Rolled-back test rows replay their pk, and the locmem cache —
        # unlike the DB — persists across the run: clear the approval cache
        # so verdicts from another test tenant can't leak in.
        cache.clear()
        self.tenant = provision_tenant(name="Gup Gym", contact_email="gup@local.test", **GUPSHUP_CONFIG)

    def _poster(self, payload=None, status_code=200):
        """A fake requests.post returning a 2xx response (optional JSON body)."""
        poster = MagicMock()
        response = MagicMock(status_code=status_code, raise_for_status=MagicMock())
        if payload is not None:
            response.json.return_value = payload
        poster.return_value = response
        return poster

    @staticmethod
    def _approved_getter(return_status):
        """A template getter returning a fixed approval status."""
        return lambda tenant, name: return_status

    def test_send_posts_template_with_apikey_header(self) -> None:
        """Body carries [code] ONLY (Authentication shape, #85 — no gym name,
        no ttl); the apikey header is the tenant key."""
        poster = self._poster({"status": "submitted", "messageId": "m-1"})
        sender = GupshupOtpSender(self.tenant, poster=poster, template_getter=self._approved_getter("APPROVED"))
        sender.send_otp("+919900000020", "123456", tenant=self.tenant)
        args, kwargs = poster.call_args
        self.assertEqual(args[0], GUPSHUP_MSG_URL)
        self.assertEqual(
            json.loads(kwargs["data"]["message"]),
            {"type": "template", "name": "fitnation_otp", "params": ["123456"]},
        )
        self.assertEqual(kwargs["data"]["destination"], "919900000020")
        self.assertEqual(kwargs["data"]["source"], "911234567890")
        self.assertEqual(kwargs["headers"], {"apikey": "gup-key"})

    def test_unapproved_template_gates_the_send(self) -> None:
        """A PENDING/missing template never POSTs — 202 ≠ delivery (#74)."""
        for verdict in ("PENDING", "REJECTED", ""):
            poster = self._poster({"status": "submitted", "messageId": "m-1"})
            sender = GupshupOtpSender(self.tenant, poster=poster, template_getter=self._approved_getter(verdict))
            with self.assertRaises(OtpDeliveryError) as caught:
                sender.send_otp("+919900000020", "123456", tenant=self.tenant)
            self.assertEqual(caught.exception.reason, "template_not_approved")
            poster.assert_not_called()

    def test_unverifiable_template_status_gates_the_send(self) -> None:
        """When approval cannot be proven synchronously, SMS carries instead."""
        poster = self._poster({"status": "submitted"})
        sender = GupshupOtpSender(self.tenant, poster=poster, template_getter=MagicMock(return_value=""))
        with self.assertRaises(OtpDeliveryError) as caught:
            sender.send_otp("+919900000020", "123456", tenant=self.tenant)
        self.assertEqual(caught.exception.reason, "template_not_approved")
        poster.assert_not_called()

    def test_approved_verdict_is_cached(self) -> None:
        """A verified APPROVED template caches — subsequent sends skip the GET."""
        calls = []

        def getter(tenant, name):
            calls.append(name)
            return "APPROVED"

        sender = GupshupOtpSender(self.tenant, poster=self._poster({"status": "submitted"}), template_getter=getter)
        sender.send_otp("+919900000020", "123456", tenant=self.tenant)
        sender.send_otp("+919900000021", "123456", tenant=self.tenant)
        self.assertEqual(calls, ["fitnation_otp"])

    def test_2xx_error_body_raises_provider_error(self) -> None:
        """HTTP 2xx with a Gupshup error body is a failure, not delivery."""
        poster = self._poster({"status": "error", "message": "destination not opted in"})
        sender = GupshupOtpSender(self.tenant, poster=poster, template_getter=self._approved_getter("APPROVED"))
        with self.assertRaises(OtpDeliveryError) as caught:
            sender.send_otp("+919900000020", "123456", tenant=self.tenant)
        self.assertEqual(caught.exception.reason, "provider_error")
        self.assertIn("destination not opted in", str(caught.exception))

    def test_half_configured_tenant_is_not_ready(self) -> None:
        """Enabled + key but no source/app name → not configured (chain skips)."""
        half = provision_tenant(
            name="Half Gup",
            contact_email="half@local.test",
            is_gupshup_enabled=True,
            gupshup_api_key="gup-key",
        )
        self.assertFalse(GupshupOtpSender.is_configured_for(half))
        with self.assertRaises(OtpDeliveryError) as caught:
            GupshupOtpSender(half, poster=self._poster(), template_getter=self._approved_getter("APPROVED")).send_otp(
                "+919900000020", "123456"
            )
        self.assertEqual(caught.exception.reason, "not_configured")

    def test_transport_failure_raises_delivery_error(self) -> None:
        """Any HTTP failure → OtpDeliveryError (chain falls through)."""
        poster = MagicMock()
        poster.side_effect = RuntimeError("boom")
        sender = GupshupOtpSender(self.tenant, poster=poster, template_getter=self._approved_getter("APPROVED"))
        with self.assertRaises(OtpDeliveryError) as caught:
            sender.send_otp("+919900000020", "123456", tenant=self.tenant)
        self.assertEqual(caught.exception.reason, "transport_error")

    def test_daily_cap_error_reason(self) -> None:
        """The budget guard fails with reason ``daily_cap_reached``."""
        cap = override_settings(TENANT_WATI_OTP_DAILY_CAP=0)
        cap.enable()
        self.addCleanup(cap.disable)
        sender = GupshupOtpSender(self.tenant, poster=self._poster(), template_getter=self._approved_getter("APPROVED"))
        with self.assertRaises(OtpDeliveryError) as caught:
            sender.send_otp("+919900000020", "123456", tenant=self.tenant)
        self.assertEqual(caught.exception.reason, "daily_cap_reached")


class GupshupChainResolutionTests(TestCase):
    """resolve_otp_senders with the Gupshup leg in the chain (issue #66)."""

    def setUp(self) -> None:
        """Rolled-back rows replay pks; clear the approval verdict cache."""
        cache.clear()

    def _both_channels_tenant(self):
        """A tenant with WATI and Gupshup both configured."""
        return provision_tenant(
            name="Both Gyms",
            contact_email="both3@local.test",
            is_wati_enabled=True,
            wati_api_key="wati-key",
            **GUPSHUP_CONFIG,
        )

    def test_prod_auto_chain_is_wati_gupshup_sms(self) -> None:
        """Both WhatsApp BSPs configured → WATI first, Gupshup second, SMS last."""
        tenant = self._both_channels_tenant()
        with override_settings(DEBUG=False, OTP_SENDER="auto", **SMS_SETTINGS):
            self.assertEqual([s.name for s in resolve_otp_senders(tenant)], ["wati", "gupshup", "sms"])

    def test_gupshup_only_tenant_resolves_gupshup_then_sms(self) -> None:
        """No WATI → the chain starts at Gupshup."""
        tenant = provision_tenant(name="Gup Only", contact_email="guponly@local.test", **GUPSHUP_CONFIG)
        with override_settings(DEBUG=False, OTP_SENDER="auto", **SMS_SETTINGS):
            self.assertEqual([s.name for s in resolve_otp_senders(tenant)], ["gupshup", "sms"])

    def test_forced_gupshup_leg(self) -> None:
        """OTP_SENDER=gupshup forces exactly that leg."""
        tenant = self._both_channels_tenant()
        with override_settings(DEBUG=False, OTP_SENDER="gupshup"):
            self.assertEqual([s.name for s in resolve_otp_senders(tenant)], ["gupshup"])

    def test_wati_failure_falls_through_to_gupshup(self) -> None:
        """A live chain: WATI transport down → Gupshup delivers + both audited."""
        tenant = self._both_channels_tenant()
        wati_poster = MagicMock(side_effect=RuntimeError("wati down"))
        gup_poster = MagicMock()
        gup_poster.return_value = MagicMock(status_code=202, raise_for_status=MagicMock())
        cooldown = override_settings(OTP_RESEND_COOLDOWN_SECONDS=0)
        cooldown.enable()
        self.addCleanup(cooldown.disable)
        result = issue_otp(
            "+919900000021",
            tenant,
            sender=[
                WatiOtpSender(tenant, poster=wati_poster),
                GupshupOtpSender(tenant, poster=gup_poster, template_getter=lambda t, n: "APPROVED"),
            ],
        )
        self.assertEqual(result.expires_in, 600)
        self.assertEqual(result.channel, "whatsapp")
        rows = NotificationLog.objects.for_tenant(tenant).filter(notification_type="otp")
        self.assertEqual(rows.count(), 2)
        failed = rows.filter(status=NotificationLog.Status.FAILED).get()
        self.assertEqual(failed.provider, "wati")
        self.assertEqual(failed.channel, "whatsapp")
        self.assertIn("wati down", failed.error_message)
        sent = rows.filter(status=NotificationLog.Status.SENT).get()
        self.assertEqual(sent.provider, "gupshup")

    def test_gupshup_unapproved_template_propagates_to_sms(self) -> None:
        """THE #74 fix: Gupshup's 202 for an unapproved template must NOT be
        the end of the chain — the SMS leg carries the OTP instead."""
        tenant = provision_tenant(name="Gup Only", contact_email="gup74@local.test", **GUPSHUP_CONFIG)
        gup_poster = MagicMock()  # would "succeed" — proves it's never trusted
        gup_poster.return_value = MagicMock(status_code=202, raise_for_status=MagicMock())
        sms_poster = MagicMock()
        sms_poster.return_value = MagicMock(
            status_code=200, json=MagicMock(return_value={"type": "success"}), raise_for_status=MagicMock()
        )
        cooldown = override_settings(OTP_RESEND_COOLDOWN_SECONDS=0, DEBUG=False, **SMS_SETTINGS)
        cooldown.enable()
        self.addCleanup(cooldown.disable)
        chain = [
            GupshupOtpSender(tenant, poster=gup_poster, template_getter=lambda t, n: "PENDING"),
            Msg91OtpSender(poster=sms_poster),
        ]
        result = issue_otp("+919900000022", tenant, sender=chain)
        gup_poster.assert_not_called()
        sms_poster.assert_called_once()
        self.assertEqual(result.channel, "sms")
        self.assertEqual(result.expires_in, 600)
        rows = NotificationLog.objects.for_tenant(tenant).filter(notification_type="otp")
        self.assertEqual(rows.count(), 2)
        blocked = rows.filter(status=NotificationLog.Status.FAILED).get()
        self.assertEqual(blocked.provider, "gupshup")
        self.assertEqual(blocked.channel, "whatsapp")
        delivered = rows.filter(status=NotificationLog.Status.SENT).get()
        self.assertEqual(delivered.provider, "msg91")
        self.assertEqual(delivered.channel, "sms")


class Msg91OtpSenderTests(TestCase):
    """The MSG91 flow API contract (§4.2)."""

    def test_send_posts_flow_payload(self) -> None:
        """authkey header + template_id + recipients variable map."""
        poster = MagicMock()
        poster.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"type": "success"}),
            raise_for_status=MagicMock(),
        )
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

    def test_http_2xx_error_body_raises_provider_error(self) -> None:
        """MSG91 rejects (e.g. balance/DLT) can ride HTTP 2xx — not delivery."""
        poster = MagicMock()
        poster.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"type": "error", "title": "Insufficient Balance"}),
            raise_for_status=MagicMock(),
        )
        with override_settings(**SMS_SETTINGS):
            sender = Msg91OtpSender(poster=poster)
            with self.assertRaises(OtpDeliveryError) as caught:
                sender.send_otp("+919900000004", "654321", tenant=None)
        self.assertEqual(caught.exception.reason, "provider_error")
        self.assertIn("Insufficient Balance", str(caught.exception))

    def test_unconfigured_raises(self) -> None:
        """Missing credentials → delivery error, not a silent drop."""
        with override_settings(SMS_PROVIDER="msg91", MSG91_AUTH_KEY="", MSG91_TEMPLATE_ID=""):
            sender = Msg91OtpSender(poster=MagicMock())
            with self.assertRaises(OtpDeliveryError) as caught:
                sender.send_otp("+919900000004", "654321")
        self.assertEqual(caught.exception.reason, "not_configured")

    def test_http_failure_reason_carries_status_code(self) -> None:
        """A carrier HTTP error → reason ``http_<status>``."""
        response = requests.Response()
        response.status_code = 503
        poster = MagicMock()
        poster.return_value = MagicMock(
            status_code=503, raise_for_status=MagicMock(side_effect=requests.HTTPError("503", response=response))
        )
        with override_settings(**SMS_SETTINGS):
            sender = Msg91OtpSender(poster=poster)
            with self.assertRaises(OtpDeliveryError) as caught:
                sender.send_otp("+919900000004", "654321")
        self.assertEqual(caught.exception.reason, "http_503")


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
        with self.assertLogs("apps.users.otp", level="CRITICAL") as logs, self.assertRaises(OtpDeliveryError):
            issue_otp("+919900000005", self.tenant, sender=[first, second])
        self.assertTrue(any("all channels" in line for line in logs.output))

    def test_exhaustion_error_lists_channel_reasons(self) -> None:
        """The final raise aggregates one {channel, reason} per failed leg (#59)."""
        first = MagicMock()
        first.name = "wati"
        first.send_otp.side_effect = OtpDeliveryError("down1", reason="http_500")
        second = MagicMock()
        second.name = "sms"
        second.send_otp.side_effect = OtpDeliveryError("down2", reason="transport_error")
        with self.assertRaises(OtpDeliveryError) as caught:
            issue_otp("+919900000005", self.tenant, sender=[first, second])
        self.assertEqual(caught.exception.reason, "all_channels_failed")
        self.assertEqual(
            caught.exception.channels,
            [
                {"channel": "wati", "reason": "http_500"},
                {"channel": "sms", "reason": "transport_error"},
            ],
        )

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
        """A sent row records the semantic channel + provider; no code leaks."""
        wati = MagicMock()
        wati.name = "wati"
        issue_otp("+919900000006", self.tenant, sender=wati)
        log = NotificationLog.objects.for_tenant(self.tenant).get(notification_type="otp")
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "whatsapp")
        self.assertEqual(log.provider, "wati")
        self.assertNotIn("123456", log.content)

    def test_gupshup_row_names_whatsapp_channel_and_provider(self) -> None:
        """A Gupshup-carried OTP audits channel=whatsapp, provider=gupshup."""
        gupshup = MagicMock()
        gupshup.name = "gupshup"
        issue_otp("+919900000006", self.tenant, sender=gupshup)
        log = NotificationLog.objects.for_tenant(self.tenant).get(notification_type="otp")
        self.assertEqual(log.channel, "whatsapp")
        self.assertEqual(log.provider, "gupshup")

    def test_failure_row_records_error(self) -> None:
        """A failed chain writes the failed row with the transport error."""
        sender = MagicMock()
        sender.name = "sms"
        sender.send_otp.side_effect = OtpDeliveryError("carrier down")
        with self.assertRaises(OtpDeliveryError):
            issue_otp("+919900000006", self.tenant, sender=sender)
        log = NotificationLog.objects.for_tenant(self.tenant).get(notification_type="otp")
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertEqual(log.channel, "sms")
        self.assertEqual(log.provider, "msg91")
        self.assertIn("carrier down", log.error_message)

    def test_all_failed_writes_one_row_per_leg(self) -> None:
        """Every failed leg gets its own FAILED audit row (not just the last)."""
        first = MagicMock()
        first.name = "wati"
        first.send_otp.side_effect = OtpDeliveryError("down1")
        second = MagicMock()
        second.name = "gupshup"
        second.send_otp.side_effect = OtpDeliveryError("down2")
        with self.assertRaises(OtpDeliveryError):
            issue_otp("+919900000006", self.tenant, sender=[first, second])
        rows = NotificationLog.objects.for_tenant(self.tenant).filter(notification_type="otp")
        self.assertEqual(rows.count(), 2)
        wati_row = rows.filter(provider="wati").get()
        self.assertEqual(wati_row.status, NotificationLog.Status.FAILED)
        self.assertEqual(wati_row.channel, "whatsapp")
        self.assertIn("down1", wati_row.error_message)
        gup_row = rows.filter(provider="gupshup").get()
        self.assertEqual(gup_row.status, NotificationLog.Status.FAILED)
        self.assertIn("down2", gup_row.error_message)

    def test_success_after_failure_audits_both_legs(self) -> None:
        """A degraded delivery shows failed WhatsApp + sent SMS rows (#74)."""
        wati = MagicMock()
        wati.name = "wati"
        wati.send_otp.side_effect = OtpDeliveryError("wati down")
        sms = MagicMock()
        sms.name = "sms"
        result = issue_otp("+919900000006", self.tenant, sender=[wati, sms])
        self.assertEqual(result.channel, "sms")
        rows = NotificationLog.objects.for_tenant(self.tenant).filter(notification_type="otp")
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows.filter(status=NotificationLog.Status.FAILED).get().provider, "wati")
        self.assertEqual(rows.filter(status=NotificationLog.Status.SENT).get().provider, "msg91")

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
