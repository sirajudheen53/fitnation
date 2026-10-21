"""Tests for the onboarding app (onboarding-design §8).

Covers the composite response contract, the idempotency-key replay, the
double-submit guard, tenant isolation, and the app-invite ride-along.
"""

from unittest import mock

from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.memberships.models import Membership, MembershipPlan
from apps.onboarding.models import OnboardingSession
from apps.tenants.services import provision_tenant
from apps.users.models import AuthToken, User


class OnboardingMemberEndpointTests(APITestCase):
    """``POST /api/v1/onboarding/member/`` (onboarding-design §3.1)."""

    def setUp(self) -> None:
        """A tenant with a branch, a plan, and a manager token."""
        self.tenant = provision_tenant(
            name="Onboard Gym",
            contact_email="onboard@local.test",
            features={"app_access": True},
        )
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            name="Main Branch",
            address_line1="1 Main St",
            city="Kochi",
            state="Kerala",
            postal_code="682001",
        )
        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Monthly",
            price=2500,
            duration_days=30,
        )
        self.manager = User.objects.create_user(
            email="onboard.manager@local.test",
            password="F1tNati0n!",
            first_name="On",
            last_name="Board",
            role=User.Role.MANAGER,
            tenant=self.tenant,
        )
        token = AuthToken.objects.create(user=self.manager, tenant=self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def payload(self, **overrides) -> dict:
        """Build a valid cash-path wizard payload."""
        body = {
            "customer": {
                "phone": "9876543210",
                "name": "Asha Nair",
                "branch": self.branch.pk,
            },
            "membership": {"plan": self.plan.pk},
            "payment": {"method": "cash"},
            "send_welcome": False,
            "send_app_invite": False,
        }
        body.update(overrides)
        return body

    def post_member(self, body=None, **extra):
        """POST the wizard with the given body."""
        return self.client.post(
            "/api/v1/onboarding/member/",
            body if body is not None else self.payload(),
            format="json",
            **extra,
        )

    def test_cash_path_returns_composite_result(self) -> None:
        """The cash path returns the composite result body (not null).

        Regression guard: the service used to build the result and drop it
        on the floor, so the endpoint answered ``201`` with a ``null`` body
        and the wizard screen had nothing to render.
        """
        response = self.post_member()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNotNone(response.data)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["customer"]["name"], "Asha Nair")
        self.assertIsNotNone(response.data["membership"]["id"])
        self.assertEqual(response.data["membership"]["plan_name"], "Monthly")
        self.assertIsNotNone(response.data["payment"]["id"])
        self.assertEqual(response.data["payment"]["method"], "cash")
        self.assertIn("app_invite", response.data)
        self.assertIn("entitlement_preview", response.data)

    def test_cash_path_creates_membership_and_session(self) -> None:
        """One POST creates the customer, the membership, and the session."""
        response = self.post_member()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Membership.objects.for_tenant(self.tenant).count(), 1)
        session = OnboardingSession.objects.for_tenant(self.tenant).get()
        self.assertEqual(session.status, OnboardingSession.Status.COMPLETED)
        # The session stores the same composite result it replayed.
        self.assertEqual(session.result["onboarding_id"], response.data["onboarding_id"])

    def test_idempotency_key_replays_stored_result(self) -> None:
        """A repeat POST with the same key replays the stored result.

        Regression guard: the replay path called ``session_result_payload``
        without importing it, so the second POST raised ``NameError``
        (500) instead of replaying.
        """
        first = self.post_member(HTTP_IDEMPOTENCY_KEY="key-abc-123")
        self.assertEqual(first.status_code, 201, first.data)

        second = self.post_member(HTTP_IDEMPOTENCY_KEY="key-abc-123")
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(second.data, first.data)
        # No second membership was sold.
        self.assertEqual(Membership.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(OnboardingSession.objects.for_tenant(self.tenant).count(), 1)

    def test_duplicate_submit_same_day_replays(self) -> None:
        """A same-day resubmit without a key replays the first result.

        The double-click guard: no second membership for the same member and
        plan on the same day.
        """
        first = self.post_member()
        self.assertEqual(first.status_code, 201, first.data)

        second = self.post_member()
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(second.data["onboarding_id"], first.data["onboarding_id"])
        self.assertEqual(Membership.objects.for_tenant(self.tenant).count(), 1)

    def test_tenant_isolation_on_plan(self) -> None:
        """Another gym's plan id is rejected (400) — no cross-tenant sale."""
        other = provision_tenant(name="Other Gym", contact_email="other.onboard@local.test")
        other_plan = MembershipPlan.objects.create(tenant=other, name="Other", price=100, duration_days=30)
        response = self.post_member(self.payload(membership={"plan": other_plan.pk}))
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Membership.objects.count(), 0)

    def test_customer_role_forbidden(self) -> None:
        """A customer cannot onboard members (permissions required)."""
        member = User.objects.create_user(
            email="nosy.customer@local.test",
            password="F1tNati0n!",
            first_name="N",
            last_name="C",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
            phone="+919900070001",
        )
        token = AuthToken.objects.create(user=member, tenant=self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.post_member()
        self.assertEqual(response.status_code, 403)

    def test_app_invite_block_present(self) -> None:
        """The app-invite ride-along is reported in the response block."""
        with mock.patch("apps.onboarding.services.send_app_invite") as invite:
            invite.return_value = mock.MagicMock(
                status="sent",
                channel="whatsapp",
                reason=None,
                sent_at=None,
                resend_allowed_after=None,
            )
            response = self.post_member(self.payload(send_app_invite=True))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["app_invite"]["status"], "sent")
        self.assertEqual(response.data["app_invite"]["channel"], "whatsapp")
        invite.assert_called_once()

    def test_app_invite_disabled_is_skipped(self) -> None:
        """The wizard opt-out short-circuits the invite."""
        with mock.patch("apps.onboarding.services.send_app_invite") as invite:
            response = self.post_member(self.payload(send_app_invite=False))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["app_invite"]["status"], "skipped")
        self.assertEqual(response.data["app_invite"]["reason"], "disabled")
        invite.assert_not_called()
