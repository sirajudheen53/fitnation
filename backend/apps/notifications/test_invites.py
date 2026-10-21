"""App invite tests (FBOS-011 §5): channel chain, dedupe/resend, endpoint
contract shapes, tenant isolation, and the CustomerSerializer surface."""

from datetime import timedelta
from unittest import mock
from unittest.mock import MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

import requests

from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.notifications.models import NotificationLog
from apps.notifications.services import invite_service as invite_module
from apps.notifications.services.invite_service import (
    build_app_invite_links,
    invite_result_payload,
    send_app_invite,
)
from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, User

SMS_INVITE_SETTINGS = {
    "MSG91_AUTH_KEY": "test-auth-key",
    "MSG91_INVITE_TEMPLATE_ID": "dlt-invite-template",
}


def _ok_poster():
    """A fake HTTP post that always succeeds."""
    from unittest.mock import MagicMock

    poster = MagicMock()
    poster.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    return poster


def _failing_poster():
    """A fake HTTP post that always fails."""
    from unittest.mock import MagicMock

    poster = MagicMock()
    poster.side_effect = RuntimeError("transport down")
    return poster


def _wati_down_poster():
    """A fake HTTP post where only the WATI host is down; MSG91 still delivers.

    The two channels are separate hosts in production (``api.wati.io`` vs
    ``control.msg91.com``), so a WhatsApp outage must not take the SMS
    fallback down with it — the fallback is what carries the invite when
    WATI is unavailable.
    """

    def _post(url, **kwargs):
        if "api.wati.io" in url:
            raise requests.exceptions.ConnectionError("transport down")
        return MagicMock(status_code=200, raise_for_status=MagicMock())

    poster = MagicMock()
    poster.side_effect = _post
    return poster


def _posted_urls(poster) -> list[str]:
    """The URLs a fake poster was called with, in call order."""
    return [call.args[0] for call in poster.call_args_list]


class InviteServiceTests(TestCase):
    """send_app_invite outcome matrix (§5.1/§5.3)."""

    def setUp(self) -> None:
        """Flag-on tenant with WATI + a member on an app-including plan."""
        self.tenant = provision_tenant(
            name="Hash Fit",
            contact_email="hash@local.test",
            features={"app_access": True},
            is_wati_enabled=True,
            wati_api_key="wati-key",
            wati_endpoint="https://api.wati.io/api/v1/sendSessionMessage",
        )
        self.plan = MembershipPlan.objects.create(tenant=self.tenant, name="Monthly", price=2500, duration_days=30)
        self.staff = User.objects.create_user(
            email="desk@hash.local",
            password="x",
            first_name="Desk",
            last_name="Staff",
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )
        member_user = User.objects.create_user(
            email="member@fitnation.local",
            password="x",
            first_name="Asha",
            last_name="Nair",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+919900060001",
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=member_user,
            name="Asha Nair",
            phone="+919900060001",
        )
        Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
        )

    def test_wati_sent_is_whatsapp_channel(self) -> None:
        """WATI configured → sent over WhatsApp with the 4 template vars."""
        poster = _ok_poster()
        result = send_app_invite(self.tenant, self.customer, invited_by=self.staff, poster=poster)
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.channel, "whatsapp")
        args, kwargs = poster.call_args
        self.assertIn("sendTemplateMessage/fitnation_app_invite", args[0])
        link = build_app_invite_links(self.tenant)["web"]
        self.assertEqual(kwargs["json"]["templateParams"], ["Asha Nair", "Hash Fit", "Monthly", link])
        log = result.log
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.channel, "whatsapp")
        self.assertEqual(log.actor_id, self.staff.pk)
        # The product's user-facing name is "FitNation" (FBOS-011 §5.2 copy) —
        # the audit copy must carry it plus the tenant-anchored deep link.
        self.assertIn("FitNation", log.content)
        self.assertIn(link, log.content)

    def test_wati_down_falls_to_sms(self) -> None:
        """WATI transport failing → MSG91 SMS carries the invite."""
        poster = _wati_down_poster()
        with override_settings(**SMS_INVITE_SETTINGS):
            result = send_app_invite(self.tenant, self.customer, poster=poster)
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.channel, "sms")
        # The WATI leg was tried and failed; the SMS leg then delivered.
        urls = _posted_urls(poster)
        self.assertTrue(any("api.wati.io" in url for url in urls), urls)
        self.assertTrue(any("control.msg91.com" in url for url in urls), urls)
        self.assertEqual(result.log.status, NotificationLog.Status.SENT)
        self.assertEqual(result.log.channel, "sms")

    def test_no_channels_configured_is_skipped(self) -> None:
        """WATI off + no SMS → skipped with reason wati_not_configured."""
        self.tenant.is_wati_enabled = False
        self.tenant.save(update_fields=["is_wati_enabled"])
        with override_settings(MSG91_AUTH_KEY="", MSG91_INVITE_TEMPLATE_ID=""):
            result = send_app_invite(self.tenant, self.customer, poster=_ok_poster())
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.reason, "wati_not_configured")
        self.assertEqual(result.log.status, NotificationLog.Status.SKIPPED)

    def test_all_channels_fail_is_failed(self) -> None:
        """WATI fails + SMS unset → failed (recorded, never raised)."""
        self.tenant.is_wati_enabled = True
        result = send_app_invite(self.tenant, self.customer, poster=_failing_poster())
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.log.status, NotificationLog.Status.FAILED)

    def test_flag_off_is_not_applicable(self) -> None:
        """Rollout flag off → not_applicable / flag_off, no send attempted."""
        self.tenant.features = {}
        self.tenant.save(update_fields=["features"])
        poster = _ok_poster()
        result = send_app_invite(self.tenant, self.customer, poster=poster)
        self.assertEqual(result.status, "not_applicable")
        self.assertEqual(result.reason, "flag_off")
        poster.assert_not_called()

    def test_plan_excluding_app_is_not_applicable(self) -> None:
        """A gym-only plan → not_applicable / plan_excludes_app."""
        gym_plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Gym Only",
            price=500,
            duration_days=30,
            includes_app_access=False,
        )
        self.customer.memberships.update(plan=gym_plan)
        result = send_app_invite(self.tenant, self.customer, poster=_ok_poster())
        self.assertEqual(result.status, "not_applicable")
        self.assertEqual(result.reason, "plan_excludes_app")

    def test_dedupe_within_window_returns_already_sent(self) -> None:
        """A sent invite inside 24h short-circuits with resend_allowed_after."""
        first = send_app_invite(self.tenant, self.customer, poster=_ok_poster())
        self.assertEqual(first.status, "sent")
        second = send_app_invite(self.tenant, self.customer, poster=_ok_poster())
        self.assertEqual(second.status, "already_sent")
        self.assertEqual(second.sent_at, first.log.created_at)
        self.assertIsNotNone(second.resend_allowed_after)
        self.assertEqual(NotificationLog.objects.filter(notification_type="app_invite").count(), 1)

    def test_force_resend_bypasses_dedupe(self) -> None:
        """resend: true (force) sends again — front-desk override."""
        send_app_invite(self.tenant, self.customer, poster=_ok_poster())
        forced = send_app_invite(self.tenant, self.customer, force=True, poster=_ok_poster())
        self.assertEqual(forced.status, "sent")
        self.assertEqual(NotificationLog.objects.filter(notification_type="app_invite").count(), 2)

    def test_daily_cap_returns_failed_with_reason(self) -> None:
        """Exhausting the tenant's daily invite budget → failed/daily_limit."""
        cap = override_settings(APP_INVITE_DAILY_LIMIT=1)
        cap.enable()
        self.addCleanup(cap.disable)
        self.tenant.is_wati_enabled = False
        self.tenant.save(update_fields=["is_wati_enabled"])
        with override_settings(**SMS_INVITE_SETTINGS):
            first = send_app_invite(self.tenant, self.customer, poster=_ok_poster())
            second = send_app_invite(self.tenant, self.customer, force=True, poster=_ok_poster())
        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "failed")
        self.assertEqual(second.reason, "daily_limit_reached")

    def test_tenant_isolation_on_dedupe_query(self) -> None:
        """Another gym's invite for a same-id customer never dedupes."""
        other = provision_tenant(
            name="Other Gym",
            contact_email="other2@local.test",
            features={"app_access": True},
            is_wati_enabled=True,
            wati_api_key="other-wati-key",
        )
        other_user = User.objects.create_user(
            email="othermember@fitnation.local",
            password="x",
            first_name="O",
            last_name="M",
            role=User.Role.CUSTOMER,
            tenant=other,
            phone="+919900060002",
        )
        other_customer = Customer.objects.create(tenant=other, user=other_user, name="OM", phone="+919900060002")
        # Gym A's own sent invite for its own member.
        NotificationLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type=NotificationLog.NotificationType.APP_INVITE,
            status=NotificationLog.Status.SENT,
        )
        # A sent invite row filed under gym A but pointing at gym B's member
        # (a misfiled log). Dedupe is scoped to the customer's own gym, so
        # this foreign-tenant row must not suppress gym B's send — a dedupe
        # query filtered on the customer alone would wrongly short-circuit
        # to already_sent here.
        NotificationLog.objects.create(
            tenant=self.tenant,
            customer=other_customer,
            notification_type=NotificationLog.NotificationType.APP_INVITE,
            status=NotificationLog.Status.SENT,
        )
        result = send_app_invite(other, other_customer, poster=_ok_poster())
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.channel, "whatsapp")
        # The other gym's invite is its own row — gym A's logs are untouched
        # and no cross-tenant log was created.
        self.assertEqual(result.log.tenant_id, other.pk)
        self.assertEqual(result.log.customer_id, other_customer.pk)
        self.assertEqual(NotificationLog.objects.for_tenant(self.tenant).count(), 2)
        self.assertEqual(NotificationLog.objects.for_tenant(other).count(), 1)


class LinkBuilderTests(TestCase):
    """The gym-anchored link set (§5.4)."""

    def setUp(self) -> None:
        """One tenant."""
        self.tenant = provision_tenant(name="Link Gym", contact_email="link@local.test")

    def test_link_shapes(self) -> None:
        """App Link + custom scheme + Play referrer all carry the uuid."""
        links = build_app_invite_links(self.tenant)
        self.assertEqual(links["web"], f"https://app.yougetfitwithus.com/g/{self.tenant.uuid}")
        self.assertEqual(links["scheme"], f"fitnation://g/{self.tenant.uuid}")
        self.assertIn(f"referrer=gym%3D{self.tenant.uuid}", links["play"])
        self.assertIn("com.getfitwithus.app", links["play"])

    def test_web_base_override(self) -> None:
        """APP_INVITE_WEB_BASE is honored (staging domains)."""
        with override_settings(APP_INVITE_WEB_BASE="https://staging.example.com"):
            links = build_app_invite_links(self.tenant)
        self.assertTrue(links["web"].startswith("https://staging.example.com/g/"))

    def test_play_link_package_matches_the_mobile_application_id(self) -> None:
        """The Play link must target the package the app is actually published under.

        The invite's Play referrer link is dead if the backend's package
        constant drifts from the mobile ``applicationId`` — the store page
        404s and the install-referrer anchor (FBOS-011 §5.4, prong 2) never
        reaches the app. Read the Gradle file so the two cannot drift apart
        again without a failing test.
        """
        from pathlib import Path

        gradle = Path(__file__).resolve().parents[3] / "mobile" / "android" / "app" / "build.gradle.kts"
        if not gradle.exists():
            self.skipTest("mobile/android/app/build.gradle.kts is not in this checkout")
        application_id = gradle.read_text().split('applicationId = "')[1].split('"')[0]

        links = build_app_invite_links(self.tenant)
        self.assertIn(f"id={application_id}", links["play"])
        self.assertNotIn("com.fitnation.app", links["play"])

    def test_payload_shape(self) -> None:
        """invite_result_payload renders the documented API block."""
        from apps.notifications.services.invite_service import AppInviteResult  # noqa: PLC0415

        when = timezone.now()
        payload = invite_result_payload(
            AppInviteResult(status="sent", channel="whatsapp", sent_at=when),
        )
        self.assertEqual(
            sorted(payload.keys()),
            ["channel", "reason", "resend_allowed_after", "sent_at", "status"],
        )
        self.assertEqual(payload["sent_at"], when.isoformat())


class AppInviteEndpointTests(APITestCase):
    """POST /api/v1/memberships/app-invite/ (§5.1b)."""

    def setUp(self) -> None:
        """Flag-on tenant, manager with edit permission, and a member."""
        self.tenant = provision_tenant(
            name="Hash Fit",
            contact_email="hash3@local.test",
            features={"app_access": True},
            is_wati_enabled=True,
            wati_api_key="wati-key",
        )
        self.manager = User.objects.create_user(
            email="mgr@hash.local",
            password="F1tNati0n!",
            first_name="M",
            last_name="G",
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )
        member_user = User.objects.create_user(
            email="m2@fitnation.local",
            password="x",
            first_name="M",
            last_name="Two",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+919900060003",
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            user=member_user,
            name="M Two",
            phone="+919900060003",
        )
        self.plan = MembershipPlan.objects.create(tenant=self.tenant, name="Monthly", price=1, duration_days=30)
        Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
        )
        token = AuthToken.objects.create(user=self.manager, tenant=self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        wati = override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
        wati.enable()
        self.addCleanup(wati.disable)

    def post_invite(self, customer_id=None, resend=None):
        """Call the endpoint with the given body."""
        body = {"customer_id": customer_id if customer_id is not None else self.customer.pk}
        if resend is not None:
            body["resend"] = resend
        return self.client.post("/api/v1/memberships/app-invite/", body, format="json")

    @override_settings(MSG91_AUTH_KEY="", MSG91_INVITE_TEMPLATE_ID="")
    def test_fresh_send_201_with_block(self) -> None:
        """Fresh send → 201 + the documented app_invite block."""
        with mock.patch.object(invite_module, "post_wati_template") as wati:
            wati.return_value = MagicMock(status_code=200)
            response = self.post_invite()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "sent")
        self.assertEqual(response.data["channel"], "whatsapp")
        self.assertIsNone(response.data["reason"])
        wati.assert_called_once()

    def test_idempotent_repeat_returns_already_sent_200(self) -> None:
        """A second call inside the window → 200 already_sent + cooldown."""
        with override_settings(**SMS_INVITE_SETTINGS):
            with mock.patch.object(invite_module, "post_msg91_flow") as sms:
                sms.return_value = MagicMock(status_code=200)
                first = self.post_invite()
            self.assertEqual(first.status_code, 201, first.data)
            self.assertEqual(first.data["status"], "sent")
            self.assertEqual(first.data["channel"], "sms")

            second = self.post_invite()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["status"], "already_sent")
        self.assertIsNotNone(second.data["resend_allowed_after"])

    def test_resend_true_forces_new_send(self) -> None:
        """resend: true → a new send (201 again)."""
        with override_settings(**SMS_INVITE_SETTINGS):
            with mock.patch.object(invite_module, "post_msg91_flow") as sms:
                sms.return_value = MagicMock(status_code=200)
                self.post_invite()
                forced = self.post_invite(resend=True)
        self.assertEqual(forced.status_code, 201)
        self.assertEqual(forced.data["status"], "sent")

    def test_daily_cap_maps_to_429(self) -> None:
        """The tenant daily cap surfaces as 429."""
        cap = override_settings(APP_INVITE_DAILY_LIMIT=0, **SMS_INVITE_SETTINGS)
        cap.enable()
        self.addCleanup(cap.disable)
        response = self.post_invite()
        self.assertEqual(response.status_code, 429)

    def test_unknown_customer_404_and_cross_tenant_404(self) -> None:
        """Customer ids outside the tenant are 404 (no existence leak)."""
        other = provision_tenant(name="Other", contact_email="other3@local.test", features={"app_access": True})
        other_user = User.objects.create_user(
            email="other3@fitnation.local",
            password="x",
            first_name="O",
            last_name="T",
            role=User.Role.CUSTOMER,
            tenant=other,
            phone="+919900060004",
        )
        foreign = Customer.objects.create(tenant=other, user=other_user, name="OT", phone="+919900060004")
        self.assertEqual(self.post_invite(customer_id=foreign.pk).status_code, 404)
        self.assertEqual(self.post_invite(customer_id=999999).status_code, 404)

    def test_customer_role_forbidden(self) -> None:
        """Customers cannot invite (customers.edit_customer required)."""
        token = AuthToken.objects.create(user=self.customer.user, tenant=self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.post_invite()
        self.assertEqual(response.status_code, 403)

    def test_bad_payload_400(self) -> None:
        """Missing customer_id is a clean 400."""
        response = self.client.post("/api/v1/memberships/app-invite/", {}, format="json")
        self.assertEqual(response.status_code, 400)


class CustomerInviteStatusTests(TestCase):
    """CustomerSerializer.app_invite_status (§5.1b)."""

    def setUp(self) -> None:
        """Tenant + a customer."""
        self.tenant = provision_tenant(name="Status Gym", contact_email="status@local.test")
        user = User.objects.create_user(
            email="status@fitnation.local",
            password="x",
            first_name="S",
            last_name="C",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+919900060005",
        )
        self.customer = Customer.objects.create(tenant=self.tenant, user=user, name="SC", phone="+919900060005")

    def test_none_when_never_invited(self) -> None:
        """No invite history → null."""
        from apps.customers.serializers import CustomerSerializer  # noqa: PLC0415

        self.assertIsNone(CustomerSerializer(self.customer).data["app_invite_status"])

    def test_latest_log_summarized(self) -> None:
        """The most recent invite log renders {status, channel, sent_at…}."""
        from apps.customers.serializers import CustomerSerializer  # noqa: PLC0415

        NotificationLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type=NotificationLog.NotificationType.APP_INVITE,
            status=NotificationLog.Status.FAILED,
            channel="whatsapp",
            error_message="wati down",
        )
        latest = NotificationLog.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type=NotificationLog.NotificationType.APP_INVITE,
            status=NotificationLog.Status.SENT,
            channel="sms",
        )
        data = CustomerSerializer(self.customer).data["app_invite_status"]
        self.assertEqual(data["status"], "sent")
        self.assertEqual(data["channel"], "sms")
        self.assertEqual(data["sent_at"], latest.created_at)
