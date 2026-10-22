"""Phase-2 tests: membership → ADMS user-metadata propagation (the gate).

Covers the desired-state machine (UPDATE while active-or-in-cool-off,
DELETE past cool-off / cancelled), the 24h dedupe window, and the
membership viewset touchpoints (create / update / renewal / cancel).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import localdate
from rest_framework.test import APITestCase

from apps.access.models import BiometricCredential, BiometricDevice, DeviceCommandQueue
from apps.access.propagation import (
    DELETE_COMMAND,
    UPDATE_COMMAND,
    propagate_customer_biometric_state,
    userinfo_delete_text,
    userinfo_update_text,
)
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token


class PropagationTestBase(TestCase):
    """Shared fixtures: tenant, branch, member with a device credential."""

    def setUp(self) -> None:
        """Create tenant, branch, member, device, and credential."""
        self.tenant = provision_tenant(name="Gate Gym", contact_email="owner@gate.test")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        user = User.objects.create_user(
            email="member@gate.test",
            password="testpass",
            first_name="John",
            last_name="Doe",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name="John Doe",
            phone="+919999000001",
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number="GATE-DEV-1",
            name="Main Entrance",
            connection_type="webhook",
        )
        self.credential = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="12",
        )

    def _second_device(self) -> BiometricDevice:
        """A second device with the same customer enrolled (canonical id)."""
        device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number="GATE-DEV-2",
            name="Side Door",
            connection_type="webhook",
        )
        BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=device,
            credential_type="face",
            device_user_id="12",
        )
        return device

    def _membership(self, *, ends_in_days: int = 25, status: str | None = None) -> Membership:
        """Create a membership (negative = already ended)."""
        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Silver Monthly",
            price=Decimal("500.00"),
            duration_days=30,
        )
        today = localdate()
        membership = Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=plan,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=ends_in_days),
        )
        if status is not None:
            membership.status = status
            membership.save(update_fields=["status"])
        return membership


class DesiredStatePropagationTest(PropagationTestBase):
    """propagate_customer_biometric_state — the desired-state machine."""

    def test_active_membership_enqueues_update_with_cool_off_valid(self) -> None:
        """Live member → UPDATE with Valid = end_date + 3 days."""
        membership = self._membership(ends_in_days=25)
        results = propagate_customer_biometric_state(customer=self.customer)
        assert len(results) == 1
        assert results[0]["action"] == "update"
        assert results[0]["enqueued"] is True

        row = DeviceCommandQueue.objects.get(pk=results[0]["queue_id"])
        assert row.command == UPDATE_COMMAND
        assert row.device_id == self.device.pk
        assert row.payload["pin"] == "12"
        assert row.payload["name"] == "John Doe"
        assert row.payload["privilege"] == 0
        assert row.payload["valid_date"] == (membership.end_date + timedelta(days=3)).isoformat()

    def test_expired_inside_cool_off_still_gets_update(self) -> None:
        """Expired 2 days ago (cool-off 3) → member keeps device access."""
        self._membership(ends_in_days=-2)
        results = propagate_customer_biometric_state(customer=self.customer)
        assert results[0]["action"] == "update"
        assert DeviceCommandQueue.objects.filter(command=UPDATE_COMMAND).count() == 1

    def test_expired_past_cool_off_gets_delete(self) -> None:
        """Expired 4 days ago (cool-off 3) → device user deleted."""
        self._membership(ends_in_days=-4)
        results = propagate_customer_biometric_state(customer=self.customer)
        assert results[0]["action"] == "delete"
        row = DeviceCommandQueue.objects.get(pk=results[0]["queue_id"])
        assert row.command == DELETE_COMMAND
        assert row.payload["pin"] == "12"
        assert row.payload["text"] == "DATA DELETE USERINFO PIN=12"

    def test_cancelled_membership_gets_delete(self) -> None:
        """Cancellation revokes immediately — no cool-off."""
        self._membership(status="cancelled")
        results = propagate_customer_biometric_state(customer=self.customer)
        assert results[0]["action"] == "delete"
        assert DeviceCommandQueue.objects.filter(command=DELETE_COMMAND).count() == 1

    def test_no_membership_gets_delete(self) -> None:
        """Never-membered credential holders are deleted from devices."""
        results = propagate_customer_biometric_state(customer=self.customer)
        assert results[0]["action"] == "delete"

    def test_propagates_onto_every_enrolled_device(self) -> None:
        """One canonical id, every device the customer enrolls on."""
        second = self._second_device()
        self._membership()
        results = propagate_customer_biometric_state(customer=self.customer)
        assert sorted(r["device_id"] for r in results) == sorted([self.device.pk, second.pk])
        assert all(r["device_user_id"] == "12" for r in results)
        assert DeviceCommandQueue.objects.filter(command=UPDATE_COMMAND).count() == 2

    def test_inactive_credentials_are_skipped(self) -> None:
        """Deactivated credentials produce no commands."""
        self._membership()
        self.credential.is_active = False
        self.credential.save(update_fields=["is_active", "updated_at"])
        assert propagate_customer_biometric_state(customer=self.customer) == []
        assert DeviceCommandQueue.objects.count() == 0

    def test_customer_without_credentials_is_noop(self) -> None:
        """No enrollments → empty result, no queue rows."""
        user = User.objects.create_user(
            email="plain@gate.test",
            password="testpass",
            first_name="Plain",
            last_name="Member",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        plain = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name="Plain Member",
            phone="+919999000003",
        )
        assert propagate_customer_biometric_state(customer=plain) == []
        assert DeviceCommandQueue.objects.count() == 0

    def test_wire_text_format(self) -> None:
        """The UPDATE wire line carries every ADMS field, tab-separated."""
        self._membership(ends_in_days=25)
        propagate_customer_biometric_state(customer=self.customer)
        row = DeviceCommandQueue.objects.get()
        valid = row.payload["valid_date"]
        assert row.payload["text"] == (
            f"DATA UPDATE USERINFO\tPIN=12\tName=John Doe\tPrivilege=0\tPasswd=\tCard=\tValid={valid}"
        )


class PropagationDedupeTest(PropagationTestBase):
    """Drift-guard: identical pending / 24h-fresh executed rows skip."""

    def test_identical_pending_skips_enqueue(self) -> None:
        """A second identical propagation creates no duplicate row."""
        self._membership()
        first = propagate_customer_biometric_state(customer=self.customer)
        second = propagate_customer_biometric_state(customer=self.customer)
        assert first[0]["enqueued"] is True
        assert second[0]["enqueued"] is False
        assert second[0]["queue_id"] is None
        assert DeviceCommandQueue.objects.count() == 1

    def test_state_change_bypasses_dedupe(self) -> None:
        """A pending UPDATE does not block a DELETE (different string)."""
        self._membership()
        propagate_customer_biometric_state(customer=self.customer)
        self.customer.memberships.update(status="cancelled")
        results = propagate_customer_biometric_state(customer=self.customer)
        assert results[0]["action"] == "delete"
        assert results[0]["enqueued"] is True
        assert DeviceCommandQueue.objects.count() == 2

    def test_renewal_updates_valid_date(self) -> None:
        """Renewal extends end_date → fresh UPDATE with the new Valid."""
        membership = self._membership(ends_in_days=25)
        propagate_customer_biometric_state(customer=self.customer)
        membership.end_date = membership.end_date + timedelta(days=30)
        membership.save()
        results = propagate_customer_biometric_state(customer=self.customer)
        assert results[0]["enqueued"] is True
        updates = DeviceCommandQueue.objects.filter(command=UPDATE_COMMAND).order_by("pk")
        assert updates.count() == 2
        assert updates.last().payload["valid_date"] != updates.first().payload["valid_date"]

    def test_identical_executed_within_24h_skips(self) -> None:
        """Delivered an hour ago → the same desired state skips."""
        self._membership()
        propagate_customer_biometric_state(customer=self.customer)
        DeviceCommandQueue.objects.update(executed_at=timezone.now() - timedelta(hours=1))
        results = propagate_customer_biometric_state(customer=self.customer)
        assert results[0]["enqueued"] is False
        assert DeviceCommandQueue.objects.count() == 1

    def test_executed_beyond_24h_reenqueues(self) -> None:
        """Delivered 25h ago → the same desired state re-queues (refresh)."""
        self._membership()
        propagate_customer_biometric_state(customer=self.customer)
        DeviceCommandQueue.objects.update(executed_at=timezone.now() - timedelta(hours=25))
        results = propagate_customer_biometric_state(customer=self.customer)
        assert results[0]["enqueued"] is True
        assert DeviceCommandQueue.objects.count() == 2

    def test_dedupe_scoped_per_device(self) -> None:
        """A pending row on device A never blocks device B."""
        self._second_device()
        self._membership()
        propagate_customer_biometric_state(customer=self.customer)
        DeviceCommandQueue.objects.filter(device=self.device).delete()
        results = propagate_customer_biometric_state(customer=self.customer)
        # Only the second device's row was missing; it alone is enqueued.
        by_device = {r["device_id"]: r for r in results}
        assert by_device[self.device.pk]["enqueued"] is True
        assert DeviceCommandQueue.objects.count() == 2


class WireTextHelperTest(PropagationTestBase):
    """The ADMS command-line builders (shared with the adapter in B-C)."""

    def test_update_text_exact_format(self) -> None:
        """Tab-separated ADMS fields with empty Passwd/Card."""
        assert userinfo_update_text(pin="12", name="Ana", privilege=0, valid_date=None) == (
            "DATA UPDATE USERINFO\tPIN=12\tName=Ana\tPrivilege=0\tPasswd=\tCard=\tValid="
        )

    def test_delete_text_exact_format(self) -> None:
        assert userinfo_delete_text(pin="12") == "DATA DELETE USERINFO PIN=12"


class MembershipTouchpointPropagationTest(APITestCase):
    """create / renewal / cancel through the API reach the device queue."""

    def setUp(self) -> None:
        """Create tenant, owner token, member, device, credential, plan."""
        self.tenant = provision_tenant(name="Touch Gym", contact_email="owner@touch.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@touch.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Touch Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Bronze Monthly",
            price=Decimal("750.00"),
            duration_days=30,
        )
        user = User.objects.create_user(
            email="member@touch.test",
            password="testpass",
            first_name="Carl",
            last_name="Customer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name="Carl Customer",
            phone="+919999000004",
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number="TOUCH-DEV-1",
            name="Entrance",
            connection_type="webhook",
        )
        self.credential = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="9",
        )

    def _create_membership_via_api(self) -> dict:
        """POST /memberships/ and return the response payload."""
        today = localdate()
        response = self.client.post(
            "/api/v1/memberships/memberships/",
            {
                "customer": self.customer.pk,
                "plan": self.plan.pk,
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=30)).isoformat(),
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        return response.data

    def test_membership_create_enqueues_update(self) -> None:
        """Creating a membership pushes the user metadata to the device."""
        payload = self._create_membership_via_api()
        row = DeviceCommandQueue.objects.get(command=UPDATE_COMMAND)
        assert row.payload["pin"] == "9"
        assert row.payload["name"] == "Carl Customer"
        expected_valid = (date.fromisoformat(payload["end_date"]) + timedelta(days=3)).isoformat()
        assert row.payload["valid_date"] == expected_valid

    def test_membership_renewal_refreshes_valid_date(self) -> None:
        """Renewal extends membership → a second UPDATE with new Valid."""
        payload = self._create_membership_via_api()
        response = self.client.post(
            f"/api/v1/memberships/memberships/{payload['id']}/renewal/", {"days": 30}, format="json"
        )
        assert response.status_code == 200
        updates = DeviceCommandQueue.objects.filter(command=UPDATE_COMMAND).order_by("pk")
        assert updates.count() == 2
        assert updates.last().payload["valid_date"] > updates.first().payload["valid_date"]

    def test_membership_cancel_enqueues_delete(self) -> None:
        """Cancelling revokes the device user right away."""
        payload = self._create_membership_via_api()
        response = self.client.post(f"/api/v1/memberships/memberships/{payload['id']}/cancel/")
        assert response.status_code == 200
        assert DeviceCommandQueue.objects.filter(command=DELETE_COMMAND, payload__pin="9").exists()

    def test_membership_cancel_is_deduped_on_repeat(self) -> None:
        """A second cancel propagates no duplicate DELETE."""
        payload = self._create_membership_via_api()
        self.client.post(f"/api/v1/memberships/memberships/{payload['id']}/cancel/")
        self.client.post(f"/api/v1/memberships/memberships/{payload['id']}/cancel/")
        assert DeviceCommandQueue.objects.filter(command=DELETE_COMMAND).count() == 1
