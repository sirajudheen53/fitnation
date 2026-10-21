"""Recorded member-journey log for the app-access workflow (QA / Shield).

The :mod:`tests.test_app_access_e2e` suite asserts the journey step-by-step;
this file runs the *same* journey as one linear scenario and PRINTS each
state transition, so the QA report (``docs/qa/app-access-e2e-verification.md``)
can quote a concrete, reproducible log:

    python -m pytest -s tests/test_app_access_rehearsal_log.py > evidence.log

Same guarantees: fake WATI transport, DEBUG stub OTP sender, no real
WhatsApp/SMS/Play traffic. The assertions keep it honest; the prints keep it
readable.
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
from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, User

from tests.test_app_access_e2e import _ok_poster

JOURNEY_PHONE = "9876500001"


class AppAccessJourneyLogTests(APITestCase):
    """Walk the workflow once and print every gate transition (QA evidence)."""

    @classmethod
    def setUpTestData(cls) -> None:
        cache.clear()
        cls.poster = _ok_poster()
        cls.gym_a = provision_tenant(name="Hash Fit", contact_email="hash@journey.local", features={"app_access": True})
        cls.gym_a.is_wati_enabled = True
        cls.gym_a.wati_api_key = "journey-wati-key"
        cls.gym_a.wati_endpoint = "https://api.wati.io/api/v1/sendSessionMessage"
        cls.gym_a.save(update_fields=["is_wati_enabled", "wati_api_key", "wati_endpoint"])
        cls.gym_b = provision_tenant(name="Iron Temple", contact_email="iron@journey.local")
        cls.gym_b.features = {"app_access": True}
        cls.gym_b.save(update_fields=["features"])

        cls.plan = MembershipPlan.objects.create(tenant=cls.gym_a, name="Monthly", price=2500, duration_days=30)
        cls.plan_b = MembershipPlan.objects.create(tenant=cls.gym_b, name="Monthly", price=2000, duration_days=30)
        cls.branch = Branch.objects.create(
            tenant=cls.gym_a,
            name="Main Branch",
            address_line1="1 Main St",
            city="Kochi",
            state="Kerala",
            postal_code="682001",
        )
        cls.branch_b = Branch.objects.create(
            tenant=cls.gym_b,
            name="Temple Branch",
            address_line1="2 Temple Rd",
            city="Kochi",
            state="Kerala",
            postal_code="682002",
        )
        cls.desk = User.objects.create_user(
            email="desk@journey.local",
            password="F1tNati0n!",
            first_name="Front",
            last_name="Desk",
            role=User.Role.MANAGER,
            tenant=cls.gym_a,
        )
        cls.desk_b = User.objects.create_user(
            email="desk.b@journey.local",
            password="F1tNati0n!",
            first_name="Front",
            last_name="Desk",
            role=User.Role.MANAGER,
            tenant=cls.gym_b,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        cache.clear()

    # ── helpers ─────────────────────────────────────────────────────────────

    def log(self, step: str, message: str) -> None:
        """One journey line: ``[step] message``."""
        print(f"[{step}] {message}")

    def auth_as(self, user: User) -> None:
        issued = AuthToken.objects.create(user=user, tenant=user.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {issued.key}")

    def onboard(self, phone: str, desk: User, plan: MembershipPlan, branch: Branch) -> dict:
        """One front-desk wizard submit (client credentials cleared after)."""
        self.auth_as(desk)
        with (
            mock.patch("apps.notifications.services.channels.requests.post", self.poster),
            mock.patch("apps.notifications.services.wati_service.requests.post", self.poster),
        ):
            response = self.client.post(
                "/api/v1/onboarding/member/",
                {
                    "customer": {"phone": phone, "name": f"Member {phone[-4:]}", "branch": branch.pk},
                    "membership": {"plan": plan.pk},
                    "payment": {"method": "cash", "amount": plan.price},
                    "send_welcome": False,
                    "send_app_invite": True,
                },
                format="json",
            )
        self.client.credentials()
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def otp_verify(self, phone: str, gym: str | None = None) -> dict:
        """The member's device flow: request + verify, with the gym anchor."""
        body = {"phone": phone, **({"gym": gym} if gym else {})}
        issued = self.client.post("/api/v1/users/auth/otp/request/", body, format="json")
        self.assertEqual(issued.status_code, 200, issued.data)
        verify = self.client.post(
            "/api/v1/users/auth/otp/verify/",
            {**body, "otp": issued.data["otp"]},
            format="json",
        )
        self.assertEqual(verify.status_code, 200, verify.data)
        return verify.data

    def live_entitlement(self) -> dict:
        response = self.client.get("/api/v1/users/auth/entitlement/")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def set_end_date(self, days_ago: int, status: str) -> None:
        membership = Membership.objects.filter(tenant=self.gym_a, customer__phone=JOURNEY_PHONE).first()
        membership.end_date = timezone.localdate() - timedelta(days=days_ago)
        membership.status = status
        membership.save(update_fields=["end_date", "status"])

    # ── the journey ─────────────────────────────────────────────────────────

    @override_settings(DEBUG=True, OTP_SENDER="stub", OTP_RESEND_COOLDOWN_SECONDS=0)
    def test_journey_records_state_transitions(self) -> None:
        """One member, one gym, the whole lifecycle — printed to stdout."""
        print(f"[setup] gym A={self.gym_a.name} uuid={self.gym_a.uuid} | gym B={self.gym_b.name}")

        # 1. front desk onboards the member; the invite rides along.
        payload = self.onboard(JOURNEY_PHONE, self.desk, self.plan, self.branch)
        invite = payload["app_invite"]
        self.log("1 onboarding", f"201 completed; invite status={invite['status']} channel={invite['channel']}")
        self.assertEqual(invite["status"], "sent")
        self.assertEqual(invite["channel"], "whatsapp")

        # 2. resend inside the cooldown is idempotent.
        customer = Customer.objects.get(tenant=self.gym_a, phone=JOURNEY_PHONE)
        self.auth_as(self.desk)
        with mock.patch("apps.notifications.services.channels.requests.post", self.poster):
            repeat = self.client.post("/api/v1/memberships/app-invite/", {"customer_id": customer.pk}, format="json")
        self.log("2 invite-resend", f"non-forced resend → status={repeat.data['status']}")
        self.assertEqual(repeat.data["status"], "already_sent")
        self.client.credentials()

        # 3. the member logs in with the anchored link.
        verified = self.otp_verify(JOURNEY_PHONE, gym=str(self.gym_a.uuid))
        self.assertIn("app.access", verified["permissions"])
        self.assertEqual(verified["entitlement"]["status"], "active")
        entitlement = verified["entitlement"]
        self.log(
            "3 otp-verify",
            f"entitlement={entitlement['status']} app.access=YES token granted plan={entitlement['plan_name']}",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {verified['token']}")

        # 4. the gate flips: active → grace (−3d) → expired (−8d) → cancelled.
        state = self.live_entitlement()
        self.assertEqual(state["status"], "active")
        self.log("4a entitlement", f"today → status={state['status']} read_only={state['read_only']}")

        self.set_end_date(3, Membership.Status.EXPIRED)
        state = self.live_entitlement()
        write = self.client.post("/api/v1/feedback/feedback/", {"title": "x", "body": "y"}, format="json")
        code = write.data.get("code")
        self.log("4b entitlement", f"expiry −3d → {state['status']} read_only={state['read_only']} write→403 {code}")
        self.assertEqual(state["status"], "grace")
        self.assertTrue(state["read_only"])
        self.assertEqual(write.status_code, 403)
        self.assertEqual(write.data["code"], "app_access_read_only")

        self.set_end_date(8, Membership.Status.EXPIRED)
        state = self.live_entitlement()
        read = self.client.get("/api/v1/workouts/workout-plans/")
        self.log("4c entitlement", f"expiry −8d → status={state['status']} read→403 {read.data.get('code')}")
        self.assertEqual(state["status"], "expired")
        self.assertEqual(read.status_code, 403)
        self.assertEqual(read.data["code"], "app_access_required")

        self.set_end_date(0, Membership.Status.CANCELLED)
        state = self.live_entitlement()
        self.log("4d entitlement", f"cancelled → status={state['status']} (no grace)")
        self.assertEqual(state["status"], "none")

        # 5. a second member of the same gym is isolated.
        self.onboard("9876500002", self.desk, self.plan, self.branch)
        second = self.otp_verify("9876500002", gym=str(self.gym_a.uuid))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {second['token']}")
        listing = self.client.get("/api/v1/customers/customers/")
        phones = {row["phone"] for row in listing.data["results"]}
        self.log("5 isolation", f"member-2 sees phones={sorted(phones)} (only their own row)")
        self.assertEqual(phones, {"9876500002"})

        # 6. the same phone at another gym resolves via the anchor.
        self.onboard(JOURNEY_PHONE, self.desk_b, self.plan_b, self.branch_b)
        in_b = self.otp_verify(JOURNEY_PHONE, gym=str(self.gym_b.uuid))
        self.log(
            "6 multi-tenant",
            f"same phone + anchor B → gym={in_b['entitlement']['gym']['name']} (separate account, separate token)",
        )
        self.assertEqual(in_b["entitlement"]["gym"]["uuid"], str(self.gym_b.uuid))

        ambiguous = self.client.post("/api/v1/users/auth/otp/request/", {"phone": JOURNEY_PHONE}, format="json")
        self.assertEqual(ambiguous.data["action"], "select_gym")
        names = sorted(gym["name"] for gym in ambiguous.data["gyms"])
        self.log("6b disambiguation", f"no anchor → select_gym prompt with {names} (only tenant-uuid + name exposed)")
        self.assertEqual(names, ["Hash Fit", "Iron Temple"])
