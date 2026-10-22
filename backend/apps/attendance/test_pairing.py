"""Phase-2 punch → attendance pairing state machine tests.

Per (customer, branch, local date): first punch checks in, a punch ≥60s
later checks out, sooner is a double-read, and later punches keep
sliding check_out to the last of the day.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.attendance.models import AttendanceRecord
from apps.attendance.services import pair_punch
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.services import provision_tenant
from apps.users.models import User


class PairingTestBase(TestCase):
    """Shared fixtures: tenant, branch, second branch, customer."""

    def setUp(self) -> None:
        """Create tenant, branches, customer user, and customer."""
        self.tenant = provision_tenant(name="Pair Gym", contact_email="owner@pair.test")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        self.other_branch = Branch.objects.create(tenant=self.tenant, name="East Branch", branch_type="gym")
        user = User.objects.create_user(
            email="member@pair.test",
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
        # Morning punch, fully inside "today" in the project timezone.
        self.morning = timezone.make_aware(timezone.datetime(2026, 10, 20, 8, 0, 0))


class PairPunchStateMachineTest(PairingTestBase):
    """pair_punch — first / open / closed / double-read transitions."""

    def test_first_punch_opens_record(self) -> None:
        """A lone punch creates an open biometric record for the day."""
        result = pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=self.morning)
        assert result["outcome"] == "checked_in"
        record = result["record"]
        assert record.pk is not None
        assert record.check_in_time == self.morning
        assert record.check_out_time is None
        assert record.method == AttendanceRecord.Method.BIOMETRIC
        assert record.date == timezone.localdate(self.morning)

    def test_punch_after_sixty_seconds_checks_out(self) -> None:
        """A punch ≥60s after check_in closes the open record."""
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=self.morning)
        evening = self.morning + timedelta(hours=10)
        result = pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=evening)
        assert result["outcome"] == "checked_out"
        assert result["record"].check_out_time == evening

    def test_punch_under_sixty_seconds_is_double_read(self) -> None:
        """A punch <60s after check_in is ignored — duplicate scan."""
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=self.morning)
        result = pair_punch(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            punch_ts=self.morning + timedelta(seconds=10),
        )
        assert result["outcome"] == "double_read_ignored"
        assert result["record"].check_out_time is None
        assert AttendanceRecord.objects.filter(customer=self.customer).count() == 1

    def test_exactly_sixty_seconds_checks_out(self) -> None:
        """The boundary is inclusive: 60s exactly closes the record."""
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=self.morning)
        result = pair_punch(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            punch_ts=self.morning + timedelta(seconds=60),
        )
        assert result["outcome"] == "checked_out"

    def test_later_punch_moves_check_out_keep_last_of_day(self) -> None:
        """A punch on a closed record slides check_out to the newest."""
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=self.morning)
        noon = self.morning + timedelta(hours=4)
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=noon)
        evening = self.morning + timedelta(hours=10)
        result = pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=evening)
        assert result["outcome"] == "check_out_updated"
        assert result["record"].check_out_time == evening
        assert result["record"].check_in_time == self.morning  # first of day, untouched
        assert AttendanceRecord.objects.filter(customer=self.customer).count() == 1

    def test_stale_punch_on_closed_record_ignored(self) -> None:
        """A punch older than the stored check_out never moves it back."""
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=self.morning)
        noon = self.morning + timedelta(hours=4)
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=noon)
        result = pair_punch(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            punch_ts=self.morning + timedelta(hours=2),
        )
        assert result["outcome"] == "stale_punch_ignored"
        assert result["record"].check_out_time == noon

    def test_next_day_gets_a_fresh_record(self) -> None:
        """The next calendar day pairs into its own record."""
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=self.morning)
        next_morning = self.morning + timedelta(days=1)
        result = pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=next_morning)
        assert result["outcome"] == "checked_in"
        assert AttendanceRecord.objects.filter(customer=self.customer).count() == 2

    def test_other_branch_gets_its_own_record(self) -> None:
        """Pairing is per (customer, branch): another branch opens its own."""
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=self.morning)
        result = pair_punch(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.other_branch,
            punch_ts=self.morning + timedelta(minutes=5),
        )
        assert result["outcome"] == "checked_in"
        assert result["record"].branch_id == self.other_branch.pk
        assert AttendanceRecord.objects.filter(customer=self.customer).count() == 2

    def test_pairing_scoped_to_tenant(self) -> None:
        """Another tenant's records never pair into this tenant's punches."""
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=self.morning)
        other_tenant = provision_tenant(name="Rival Pair Gym", contact_email="owner@rival.test")
        result = pair_punch(
            tenant=other_tenant,
            customer=self.customer,
            branch=self.branch,
            punch_ts=self.morning + timedelta(hours=2),
        )
        # The open record belongs to a different tenant → not found → new row.
        assert result["outcome"] == "checked_in"
        assert result["record"].tenant == other_tenant
