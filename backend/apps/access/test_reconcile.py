"""Phase-2 tests: reconcile_biometric_access management command.

The command is a drift-only safety net: it must enqueue exactly the
missing device state, stay idempotent across re-runs, and never
double-queue against the realtime propagation (shared dedupe).
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django.utils.timezone import localdate

from apps.access.models import BiometricCredential, BiometricDevice, DeviceCommandQueue
from apps.access.propagation import DELETE_COMMAND, UPDATE_COMMAND, propagate_customer_biometric_state
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.tenants.services import provision_tenant
from apps.users.models import User


class ReconcileTestBase(TestCase):
    """Shared fixtures: tenant, branch, member, device, credential."""

    def setUp(self) -> None:
        """Create tenant, branch, member, device, credential, plan."""
        self.tenant = provision_tenant(name="Recon Gym", contact_email="owner@recon.test")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        user = User.objects.create_user(
            email="member@recon.test",
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
            serial_number="RECON-DEV-1",
            name="Main Entrance",
            connection_type="webhook",
        )
        self.credential = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="3",
        )
        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Silver Monthly",
            price=Decimal("500.00"),
            duration_days=30,
        )

    def _membership(self, *, ends_in_days: int = 25) -> Membership:
        """Create a membership (negative = already ended)."""
        today = localdate()
        return Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=ends_in_days),
        )

    def _reconcile(self) -> str:
        """Run the command and return its stdout."""
        out = StringIO()
        call_command("reconcile_biometric_access", stdout=out)
        return out.getvalue()


class ReconcileDriftTest(ReconcileTestBase):
    """The command enqueues exactly the missing desired state."""

    def test_active_member_gets_update_enqueued(self) -> None:
        """A live member whose state was never pushed gets an UPDATE."""
        self._membership()
        output = self._reconcile()
        row = DeviceCommandQueue.objects.get()
        assert row.command == UPDATE_COMMAND
        assert row.payload["pin"] == "3"
        assert "updates_enqueued=1" in output
        assert f"[tenant {self.tenant.pk}" in output

    def test_expired_past_cool_off_gets_delete_enqueued(self) -> None:
        """A member expired beyond the cool-off gets a DELETE."""
        self._membership(ends_in_days=-10)
        self._reconcile()
        row = DeviceCommandQueue.objects.get()
        assert row.command == DELETE_COMMAND
        assert row.payload["pin"] == "3"

    def test_no_membership_gets_delete_enqueued(self) -> None:
        """A credentialed customer without any membership gets a DELETE."""
        self._reconcile()
        assert DeviceCommandQueue.objects.get().command == DELETE_COMMAND

    def test_rerun_enqueues_nothing(self) -> None:
        """A second run finds no drift and enqueues nothing."""
        self._membership()
        self._reconcile()
        before = DeviceCommandQueue.objects.count()
        output = self._reconcile()
        assert DeviceCommandQueue.objects.count() == before
        assert "skipped_no_drift=1" in output

    def test_skips_state_delivered_within_24h(self) -> None:
        """Identical state delivered 2h ago counts as in-sync."""
        self._membership()
        self._reconcile()
        DeviceCommandQueue.objects.update(executed_at=timezone.now() - timedelta(hours=2))
        self._reconcile()
        assert DeviceCommandQueue.objects.count() == 1

    def test_refreshes_state_delivered_beyond_24h(self) -> None:
        """Identical state delivered 30h ago re-queues (periodic refresh)."""
        self._membership()
        self._reconcile()
        DeviceCommandQueue.objects.update(executed_at=timezone.now() - timedelta(hours=30))
        output = self._reconcile()
        assert DeviceCommandQueue.objects.count() == 2
        assert "updates_enqueued=1" in output


class ReconcileRealtimeCoexistenceTest(ReconcileTestBase):
    """The command and the realtime propagation share one dedupe."""

    def test_idempotent_against_realtime_propagation(self) -> None:
        """Realtime already queued the state → reconcile adds nothing."""
        self._membership()
        realtime_results = propagate_customer_biometric_state(customer=self.customer)
        assert realtime_results[0]["enqueued"] is True
        self._reconcile()
        assert DeviceCommandQueue.objects.count() == 1

    def test_reconcile_then_realtime_adds_nothing(self) -> None:
        """The reverse order is equally drift-free."""
        self._membership()
        self._reconcile()
        realtime_results = propagate_customer_biometric_state(customer=self.customer)
        assert realtime_results[0]["enqueued"] is False
        assert DeviceCommandQueue.objects.count() == 1

    def test_catches_drift_after_realtime_state_change(self) -> None:
        """Membership expired quietly → reconcile queues the missing DELETE."""
        membership = self._membership(ends_in_days=25)
        propagate_customer_biometric_state(customer=self.customer)
        membership.end_date = localdate() - timedelta(days=10)
        membership.save()
        self._reconcile()
        assert DeviceCommandQueue.objects.filter(command=DELETE_COMMAND).count() == 1


class ReconcileScopeTest(ReconcileTestBase):
    """Tenant scoping and credential gating."""

    def test_tenant_filter_limits_scope(self) -> None:
        """--tenant reconciles only that tenant."""
        self._membership()
        other_tenant = provision_tenant(name="Rival Recon", contact_email="owner@rival.test")
        other_branch = Branch.objects.create(tenant=other_tenant, name="Rival Branch", branch_type="gym")
        rival_user = User.objects.create_user(
            email="rival@recon.test",
            password="testpass",
            first_name="Rival",
            last_name="Member",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        rival = Customer.objects.create(
            tenant=other_tenant,
            branch=other_branch,
            user=rival_user,
            name="Rival Member",
            phone="+919999000009",
        )
        rival_device = BiometricDevice.objects.create(
            tenant=other_tenant,
            branch=other_branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number="RECON-RIVAL-1",
            name="Rival Entrance",
        )
        BiometricCredential.objects.create(
            tenant=other_tenant,
            customer=rival,
            device=rival_device,
            credential_type="fingerprint",
            device_user_id="3",
        )
        out = StringIO()
        call_command("reconcile_biometric_access", tenant=self.tenant.pk, stdout=out)
        output = out.getvalue()
        assert "Rival Recon" not in output
        assert DeviceCommandQueue.objects.count() == 1
        assert DeviceCommandQueue.objects.get().tenant_id == self.tenant.pk

    def test_customers_without_active_credentials_skipped(self) -> None:
        """Deactivated credentials exclude the customer from the walk."""
        self._membership()
        self.credential.is_active = False
        self.credential.save(update_fields=["is_active", "updated_at"])
        output = self._reconcile()
        assert DeviceCommandQueue.objects.count() == 0
        assert "customers=0" in output
