"""Access rule engine (#19) + event ingestion (#21) tests."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import localdate
from rest_framework.test import APITestCase

from apps.access.adapters.base import AdapterError
from apps.access.models import (
    AccessDecisionLog,
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
)
from apps.access.services import decide_and_log, ingest_event
from apps.attendance.models import AttendanceRecord
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token


class RuleEngineTestBase(TestCase):
    """Shared fixtures: tenant, branch, owner, customer, device."""

    def setUp(self) -> None:
        """Create tenant, branch, owner, customer user, customer, device."""
        self.tenant = provision_tenant(name="Rule Gym", contact_email="owner@rule.test")
        self.branch = Branch.objects.create(
            tenant=self.tenant, name="Main Branch", branch_type="gym"
        )
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@rule.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Rule Owner",
        )
        self.user = User.objects.create_user(
            email="cust@rule.test",
            password="testpass",
            first_name="John",
            last_name="Doe",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=self.user,
            name="John Doe",
            phone="+919999000001",
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="hikvision",
            model="DS-K1T331M",
            serial_number="SN-RULE-1",
            name="Front Door",
        )

    def _credential(self, device_user_id: str = "D001") -> BiometricCredential:
        """Enroll a fingerprint credential for the customer on the device."""
        return BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id=device_user_id,
        )

    def _add_membership(self, *, days: int) -> Membership:
        """Create a membership ending ``days`` from today (negative = past)."""
        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name=f"Monthly-{type(self).__name__}",
            plan_type="monthly",
            price=Decimal("1000.00"),
            duration_days=30,
        )
        end = localdate() + timedelta(days=days)
        return Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=plan,
            start_date=end - timedelta(days=30),
            end_date=end,
        )


class DecideAndLogTest(RuleEngineTestBase):
    """Test the rule engine evaluation + decision audit log (issue #19)."""

    def test_no_membership_denies_and_logs(self) -> None:
        """No membership → deny, and the decision is persisted."""
        state = decide_and_log(customer=self.customer, device=self.device)
        assert state["allowed"] is False
        assert state["source"] == "no_membership"
        assert (
            AccessDecisionLog.objects.filter(
                customer=self.customer,
                device=self.device,
                allowed=False,
                source="no_membership",
            ).count()
            == 1
        )

    def test_active_membership_allows(self) -> None:
        """Active plan → allow with plan_active source."""
        self._add_membership(days=30)
        state = decide_and_log(customer=self.customer, device=self.device)
        assert state["allowed"] is True
        assert state["source"] == "plan_active"

    def test_plan_expired_denies(self) -> None:
        """Expired plan → deny with plan_expired source."""
        self._add_membership(days=-5)
        state = decide_and_log(customer=self.customer, device=self.device)
        assert state["allowed"] is False
        assert state["source"] == "plan_expired"

    def test_override_allow_beats_expired_plan(self) -> None:
        """An owner ALLOW override grants entry despite an expired plan."""
        self._add_membership(days=-5)
        override = AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            allow_access=True,
            reason="grace_period",
            created_by=self.owner,
        )
        state = decide_and_log(customer=self.customer, device=self.device)
        assert state["allowed"] is True
        assert state["source"] == "override"
        assert state["override_id"] == override.pk

    def test_override_deny_beats_active_plan(self) -> None:
        """An owner DENY override blocks entry despite an active plan."""
        self._add_membership(days=30)
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            allow_access=False,
            reason="violation",
            created_by=self.owner,
        )
        state = decide_and_log(customer=self.customer, device=self.device)
        assert state["allowed"] is False
        assert state["source"] == "override"

    def test_expired_override_falls_through_to_plan(self) -> None:
        """An expired override is ignored — plan rules apply again."""
        self._add_membership(days=30)
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            allow_access=True,
            reason="grace_period",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        state = decide_and_log(customer=self.customer, device=self.device)
        assert state["allowed"] is True
        assert state["source"] == "plan_active"


class IngestEventTest(RuleEngineTestBase):
    """Test event ingestion with attendance auto-creation (issue #21)."""

    def test_entry_creates_log_and_attendance(self) -> None:
        """An entry event from an enrolled credential checks the customer in."""
        self._credential()
        result = ingest_event(
            device=self.device,
            device_user_id="D001",
            event_type="entry",
            event_timestamp=timezone.now(),
        )
        assert result["duplicate"] is False
        assert result["log"].customer_id == self.customer.pk
        assert result["attendance_created"] is True
        assert AttendanceRecord.objects.for_tenant(self.tenant).filter(
            customer=self.customer
        ).exists()

    def test_duplicate_event_is_idempotent(self) -> None:
        """The same event twice yields one log row and one attendance row."""
        self._credential()
        now = timezone.now()
        first = ingest_event(
            device=self.device,
            device_user_id="D001",
            event_type="entry",
            event_timestamp=now,
        )
        second = ingest_event(
            device=self.device,
            device_user_id="D001",
            event_type="entry",
            event_timestamp=now,
        )
        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert AccessLog.objects.filter(device=self.device).count() == 1
        assert AttendanceRecord.objects.for_tenant(self.tenant).count() == 1

    def test_unknown_credential_logs_without_customer(self) -> None:
        """Events from unenrolled credentials are logged but unresolved."""
        result = ingest_event(
            device=self.device,
            device_user_id="GHOST",
            event_type="entry",
            event_timestamp=timezone.now(),
        )
        assert result["log"].customer is None
        assert result["attendance_created"] is False

    def test_exit_does_not_create_attendance(self) -> None:
        """Exit events never create attendance check-ins."""
        self._credential()
        result = ingest_event(
            device=self.device,
            device_user_id="D001",
            event_type="exit",
            event_timestamp=timezone.now(),
        )
        assert result["attendance_created"] is False
        assert AttendanceRecord.objects.for_tenant(self.tenant).count() == 0

    def test_second_entry_same_day_skips_attendance(self) -> None:
        """A re-entry after an open check-in logs the event, skips attendance."""
        self._credential()
        ingest_event(
            device=self.device,
            device_user_id="D001",
            event_type="entry",
            event_timestamp=timezone.now(),
        )
        later = timezone.now() + timedelta(minutes=5)
        result = ingest_event(
            device=self.device,
            device_user_id="D001",
            event_type="entry",
            event_timestamp=later,
        )
        # New access log recorded (different timestamp), but no second
        # attendance record — the open check-in is reused.
        assert result["duplicate"] is False
        assert result["attendance_created"] is False
        assert AccessLog.objects.filter(device=self.device).count() == 2
        assert AttendanceRecord.objects.for_tenant(self.tenant).count() == 1

    def test_invalid_event_type_raises(self) -> None:
        """Unsupported event types are rejected."""
        with self.assertRaises(AdapterError):
            ingest_event(
                device=self.device,
                device_user_id="D001",
                event_type="teleport",
                event_timestamp=timezone.now(),
            )

    def test_ingest_updates_last_seen(self) -> None:
        """Ingesting an event stamps the device's last_seen_at."""
        assert self.device.last_seen_at is None
        self._credential()
        ingest_event(
            device=self.device,
            device_user_id="D001",
            event_type="entry",
            event_timestamp=timezone.now(),
        )
        self.device.refresh_from_db()
        assert self.device.last_seen_at is not None


class AccessCheckAPITest(RuleEngineTestBase, APITestCase):
    """Integration tests for GET /api/v1/access/check/ (issue #19)."""

    def setUp(self) -> None:
        """Add token auth on top of the shared fixtures."""
        super().setUp()
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_check_requires_params(self) -> None:
        """Missing query params → 400."""
        response = self.client.get("/api/v1/access/check/")
        assert response.status_code == 400

    def test_check_unknown_ids_404(self) -> None:
        """Unknown customer or device → 404."""
        response = self.client.get(
            "/api/v1/access/check/?customer_id=99999&device_id=99999"
        )
        assert response.status_code == 404

    def test_check_logs_decision(self) -> None:
        """A check call returns the state and persists a decision row."""
        self._add_membership(days=30)
        response = self.client.get(
            f"/api/v1/access/check/?customer_id={self.customer.pk}"
            f"&device_id={self.device.pk}"
        )
        assert response.status_code == 200
        assert response.data["allowed"] is True
        assert (
            AccessDecisionLog.objects.filter(customer=self.customer).count() == 1
        )


class AccessEventsAPITest(RuleEngineTestBase, APITestCase):
    """Integration tests for POST /api/v1/access/events/ (issue #21)."""

    def setUp(self) -> None:
        """Add token auth + an enrolled credential on top of the fixtures."""
        super().setUp()
        self._credential()
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _payload(self, **overrides: object) -> dict:
        """Build an event-ingest payload with optional overrides."""
        payload = {
            "device_id": self.device.pk,
            "device_user_id": "D001",
            "event_type": "entry",
            "event_timestamp": timezone.now().isoformat(),
        }
        payload.update(overrides)
        return payload

    def test_events_endpoint_happy_path(self) -> None:
        """A valid entry event returns 201 and creates attendance."""
        response = self.client.post(
            "/api/v1/access/events/", self._payload(), format="json"
        )
        assert response.status_code == 201
        assert response.data["duplicate"] is False
        assert response.data["attendance_created"] is True
        assert response.data["customer_id"] == self.customer.pk

    def test_events_endpoint_duplicate_returns_200(self) -> None:
        """Re-posting the identical event returns 200 + duplicate flag."""
        payload = self._payload()  # captured once — identical timestamps
        self.client.post("/api/v1/access/events/", payload, format="json")
        response = self.client.post(
            "/api/v1/access/events/", payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["duplicate"] is True

    def test_events_endpoint_missing_fields_400(self) -> None:
        """Incomplete payloads → 400."""
        response = self.client.post(
            "/api/v1/access/events/",
            {"device_id": self.device.pk},
            format="json",
        )
        assert response.status_code == 400

    def test_events_endpoint_bad_event_type_400(self) -> None:
        """Unsupported event types → 400."""
        response = self.client.post(
            "/api/v1/access/events/",
            self._payload(event_type="teleport"),
            format="json",
        )
        assert response.status_code == 400

    def test_events_endpoint_unknown_device_404(self) -> None:
        """Unknown device → 404."""
        response = self.client.post(
            "/api/v1/access/events/",
            self._payload(device_id=999999),
            format="json",
        )
        assert response.status_code == 404
