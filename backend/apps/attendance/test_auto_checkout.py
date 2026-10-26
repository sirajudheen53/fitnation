"""Issue #83 — biometric auto-checkout tests (check-in + 2h).

The device never pushes a check-out, so an unpaired check-in is closed
at check-in + 2h: stamped by the sweep (punch ingest / manual check-in /
backfill command), derived on read by the serializer, and always
overridable by a real punch or an admin edit.
"""

from __future__ import annotations

import io
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.access.models import BiometricCredential, BiometricDevice, PunchLogRaw
from apps.attendance.models import AttendanceRecord
from apps.attendance.serializers import AttendanceRecordSerializer
from apps.attendance.services import apply_auto_checkouts, log_check_in, pair_punch
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_user, issue_token

SN = "ADMS-AUTO-001"


class AutoCheckoutTestBase(TestCase):
    """Shared fixtures: tenant, branch, customer, ADMS device."""

    def setUp(self) -> None:
        """Create tenant, branch, customer, and the biometric device."""
        self.tenant = provision_tenant(name="Auto Gym", contact_email="owner@auto.test")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        user = User.objects.create_user(
            email="member@auto.test",
            password="testpass",
            first_name="Jane",
            last_name="Doe",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name="Jane Doe",
            phone="+919999000042",
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number=SN,
            name="Main Entrance",
            connection_type="webhook",
        )
        self.credential = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="42",
        )

    def _open_record(self, *, customer=None, tenant=None, age=timedelta(hours=3), **kwargs) -> AttendanceRecord:
        """Create an open record `age` old (check-in = now - age)."""
        check_in = timezone.now() - age
        return AttendanceRecord.objects.create(
            tenant=tenant or self.tenant,
            customer=customer or self.customer,
            branch=self.branch,
            check_in_time=check_in,
            method=AttendanceRecord.Method.BIOMETRIC,
            **kwargs,
        )

    def _auto_closed_record(self, **kwargs) -> AttendanceRecord:
        """Create a record the sweep already stamped (open, 3h old, then swept)."""
        record = self._open_record(**kwargs)
        apply_auto_checkouts(tenant=record.tenant)
        record.refresh_from_db()
        return record


class ApplyAutoCheckoutsTest(AutoCheckoutTestBase):
    """apply_auto_checkouts — eligibility, idempotency, tenant scope."""

    def test_stamps_open_record_past_two_hours(self) -> None:
        """An open check-in 3h old is closed at exactly check-in + 2h."""
        record = self._open_record()
        stamped = apply_auto_checkouts(tenant=self.tenant)
        record.refresh_from_db()
        assert stamped == 1
        assert record.check_out_time == record.check_in_time + timedelta(hours=2)
        assert record.check_out_is_auto is True
        assert record.status == AttendanceRecord.Status.LEFT

    def test_record_under_two_hours_untouched(self) -> None:
        """An open check-in 1h old stays open."""
        self._open_record(age=timedelta(hours=1))
        assert apply_auto_checkouts(tenant=self.tenant) == 0
        record = AttendanceRecord.objects.get()
        assert record.check_out_time is None
        assert record.check_out_is_auto is False

    def test_boundary_exactly_two_hours_is_stamped(self) -> None:
        """A record whose check-in is exactly 2h ago is eligible."""
        self._open_record(age=timedelta(hours=2))
        assert apply_auto_checkouts(tenant=self.tenant) == 1

    def test_real_check_out_never_touched(self) -> None:
        """A record closed by a real punch is excluded from the sweep."""
        record = self._open_record(age=timedelta(hours=3))
        real_out = record.check_in_time + timedelta(minutes=45)
        record.check_out_time = real_out
        record.save(update_fields=["check_out_time", "updated_at"])
        assert apply_auto_checkouts(tenant=self.tenant) == 0
        record.refresh_from_db()
        assert record.check_out_time == real_out
        assert record.check_out_is_auto is False

    def test_rerun_is_idempotent(self) -> None:
        """A second sweep changes nothing — stamped rows stop matching."""
        record = self._open_record()
        assert apply_auto_checkouts(tenant=self.tenant) == 1
        record.refresh_from_db()
        first_out = record.check_out_time
        assert apply_auto_checkouts(tenant=self.tenant) == 0
        record.refresh_from_db()
        assert record.check_out_time == first_out
        assert AttendanceRecord.objects.filter(check_out_is_auto=True).count() == 1

    def test_tenant_isolation(self) -> None:
        """The sweep only closes the requested tenant's records."""
        other_tenant = provision_tenant(name="Rival Auto Gym", contact_email="owner@rival.test")
        other_customer = Customer.objects.create(
            tenant=other_tenant,
            branch=self.branch,
            name="Rival Member",
            phone="+919999000099",
        )
        rival = self._open_record(customer=other_customer, tenant=other_tenant)
        mine = self._open_record()
        assert apply_auto_checkouts(tenant=self.tenant) == 1
        rival.refresh_from_db()
        assert rival.check_out_time is None  # other tenant's open record untouched
        mine.refresh_from_db()
        assert mine.check_out_is_auto is True
        assert apply_auto_checkouts(tenant=other_tenant) == 1
        rival.refresh_from_db()
        assert rival.check_out_time == rival.check_in_time + timedelta(hours=2)

    def test_dry_run_counts_without_writing(self) -> None:
        """dry_run reports eligible rows and writes nothing."""
        self._open_record()
        assert apply_auto_checkouts(tenant=self.tenant, dry_run=True) == 1
        assert AttendanceRecord.objects.get().check_out_time is None

    def test_explicit_now_is_honored(self) -> None:
        """A caller-supplied `now` decides eligibility and stamps."""
        record = self._open_record(age=timedelta(hours=3))
        before_punch = record.check_in_time + timedelta(minutes=30)
        assert apply_auto_checkouts(tenant=self.tenant, now=before_punch) == 0
        assert apply_auto_checkouts(tenant=self.tenant, now=record.check_in_time + timedelta(hours=5)) == 1
        record.refresh_from_db()
        assert record.check_out_time == record.check_in_time + timedelta(hours=2)


class PairPunchAutoOverrideTest(AutoCheckoutTestBase):
    """pair_punch — a real punch always beats the auto-derived value."""

    def test_late_real_punch_replaces_earlier_auto_value(self) -> None:
        """A delayed true check-out (after the +2h stamp) wins."""
        record = self._auto_closed_record()
        real_out = record.check_in_time + timedelta(hours=5)
        result = pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=real_out)
        assert result["outcome"] == "auto_check_out_overridden"
        assert result["record"].check_out_time == real_out
        assert result["record"].check_out_is_auto is False

    def test_delayed_real_punch_before_auto_value_wins(self) -> None:
        """A punch between check-in and the +2h guess replaces the guess."""
        record = self._auto_closed_record()
        real_out = record.check_in_time + timedelta(minutes=90)
        result = pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=real_out)
        assert result["outcome"] == "auto_check_out_overridden"
        assert result["record"].check_out_time == real_out
        assert result["record"].check_out_is_auto is False

    def test_double_read_after_auto_close_ignored(self) -> None:
        """A punch <60s after check-in is still a double-read, not a correction."""
        record = self._auto_closed_record()
        result = pair_punch(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            punch_ts=record.check_in_time + timedelta(seconds=10),
        )
        assert result["outcome"] == "double_read_ignored"
        result["record"].refresh_from_db()
        assert result["record"].check_out_time == record.check_in_time + timedelta(hours=2)
        assert result["record"].check_out_is_auto is True

    def test_real_closed_record_keeps_stale_punch_guard(self) -> None:
        """Records closed by a punch keep the existing out-of-order guard."""
        record = self._open_record(age=timedelta(hours=3))
        noon = record.check_in_time + timedelta(hours=4)
        pair_punch(tenant=self.tenant, customer=self.customer, branch=self.branch, punch_ts=noon)
        result = pair_punch(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            punch_ts=record.check_in_time + timedelta(hours=2),
        )
        assert result["outcome"] == "stale_punch_ignored"
        record.refresh_from_db()
        assert record.check_out_time == noon

    def test_auto_override_scoped_to_tenant(self) -> None:
        """Another tenant's punch cannot override this tenant's auto value."""
        other_tenant = provision_tenant(name="Rival Override Gym", contact_email="owner@rival2.test")
        record = self._auto_closed_record()
        result = pair_punch(
            tenant=other_tenant,
            customer=self.customer,
            branch=self.branch,
            punch_ts=record.check_in_time + timedelta(minutes=90),
        )
        # The auto-closed record belongs to a different tenant → invisible.
        assert result["outcome"] == "checked_in"
        record.refresh_from_db()
        assert record.check_out_is_auto is True
        assert AttendanceRecord.objects.count() == 2


class SerializerDerivationTest(AutoCheckoutTestBase):
    """The UI-facing serializer derives the +2h check-out without writing."""

    def test_open_record_past_two_hours_renders_auto_checkout(self) -> None:
        """A 3h-old open record renders check-out = check-in + 2h, flagged."""
        record = self._open_record()
        data = AttendanceRecordSerializer(record).data
        expected = record.check_in_time + timedelta(hours=2)
        assert data["check_out_time"] is not None
        assert timezone.datetime.fromisoformat(data["check_out_time"]) == expected
        assert data["check_out_is_auto"] is True
        record.refresh_from_db()
        assert record.check_out_time is None  # read never writes

    def test_open_record_under_two_hours_stays_open(self) -> None:
        """A 1h-old open record renders no check-out and no flag."""
        record = self._open_record(age=timedelta(hours=1))
        data = AttendanceRecordSerializer(record).data
        assert data["check_out_time"] is None
        assert data["check_out_is_auto"] is False

    def test_stored_auto_stamp_renders_flagged(self) -> None:
        """A sweep-stamped record keeps the flag after the stamp."""
        record = self._auto_closed_record()
        data = AttendanceRecordSerializer(record).data
        assert data["check_out_is_auto"] is True
        assert timezone.datetime.fromisoformat(data["check_out_time"]) == record.check_in_time + timedelta(hours=2)

    def test_real_check_out_renders_its_own_value(self) -> None:
        """A punch-closed record renders the punch and no flag."""
        record = self._open_record()
        real_out = record.check_in_time + timedelta(minutes=45)
        record.check_out_time = real_out
        record.save(update_fields=["check_out_time", "updated_at"])
        data = AttendanceRecordSerializer(record).data
        assert timezone.datetime.fromisoformat(data["check_out_time"]) == real_out
        assert data["check_out_is_auto"] is False

    def test_check_out_time_field_stays_writable(self) -> None:
        """Derivation must not turn the model field read-only (admin path)."""
        record = self._open_record(age=timedelta(hours=3))
        manual_out = timezone.now()
        serializer = AttendanceRecordSerializer(record, data={"check_out_time": manual_out.isoformat()}, partial=True)
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        record.refresh_from_db()
        assert record.check_out_time is not None
        assert record.check_out_is_auto is False


class AutoCheckoutAPITests(APITestCase):
    """End-to-end: list derivation, admin correction, check-out action."""

    def setUp(self) -> None:
        """Create tenant, owner, branch, customer, and auth token."""
        self.tenant = provision_tenant(name="Auto API Gym", contact_email="owner@autoapi.test")
        self.owner = create_user(
            tenant=self.tenant,
            email="owner@autoapi.test",
            first_name="Owner",
            last_name="User",
            role=User.Role.GYM_OWNER,
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", address_line1="MG Road")
        user = User.objects.create_user(
            email="member@autoapi.test",
            password="testpass",
            first_name="Jane",
            last_name="Roe",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name="Jane Roe",
            phone="+919999000043",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _open_record(self, age: timedelta) -> AttendanceRecord:
        """Create an open biometric record `age` old."""
        return AttendanceRecord.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            check_in_time=timezone.now() - age,
            method=AttendanceRecord.Method.BIOMETRIC,
        )

    def test_list_shows_derived_auto_checkout(self) -> None:
        """GET attendance list renders the +2h value for a stale open row."""
        record = self._open_record(age=timedelta(hours=3))
        response = self.client.get("/api/v1/attendance/attendance/")
        assert response.status_code == 200
        row = response.data["results"][0]
        assert row["check_out_is_auto"] is True
        expected = record.check_in_time + timedelta(hours=2)
        assert timezone.datetime.fromisoformat(row["check_out_time"]) == expected
        record.refresh_from_db()
        assert record.check_out_time is None  # still a read-only derivation

    def test_admin_correction_persists_and_clears_flag(self) -> None:
        """PATCHing a real check-out on an auto-stamped record wins for good."""
        record = self._open_record(age=timedelta(hours=3))
        apply_auto_checkouts(tenant=self.tenant)
        record.refresh_from_db()
        assert record.check_out_is_auto is True

        correction = (record.check_in_time + timedelta(minutes=75)).isoformat()
        response = self.client.patch(
            f"/api/v1/attendance/attendance/{record.pk}/",
            {"check_out_time": correction},
            format="json",
        )
        assert response.status_code == 200
        record.refresh_from_db()
        assert record.check_out_is_auto is False
        assert timezone.datetime.fromisoformat(response.data["check_out_time"]) == (
            record.check_in_time + timedelta(minutes=75)
        )
        # A later sweep must not resurrect the auto value.
        assert apply_auto_checkouts(tenant=self.tenant) == 0
        record.refresh_from_db()
        assert record.check_out_is_auto is False

    def test_check_out_action_wins_over_derivation(self) -> None:
        """The check-out action stamps real now and clears the flag."""
        record = self._open_record(age=timedelta(hours=3))
        response = self.client.post(f"/api/v1/attendance/attendance/{record.pk}/check-out/")
        assert response.status_code == 200
        record.refresh_from_db()
        assert record.check_out_time is not None
        assert record.check_out_is_auto is False
        assert record.status == AttendanceRecord.Status.LEFT

    def test_manual_check_in_after_auto_close_frees_member(self) -> None:
        """A member auto-closed 3h ago can check in again the same day."""
        stale = self._open_record(age=timedelta(hours=3))
        response = self.client.post(
            "/api/v1/attendance/check-in/",
            {"person_id": self.customer.id, "person_type": "customer", "branch_id": self.branch.id},
            format="json",
        )
        assert response.status_code == 201  # not the duplicate guard 400
        stale.refresh_from_db()
        assert stale.check_out_time == stale.check_in_time + timedelta(hours=2)
        assert stale.check_out_is_auto is True

    def test_duplicate_check_in_within_two_hours_rejected(self) -> None:
        """The duplicate guard still applies while the visit is open."""
        self._open_record(age=timedelta(minutes=30))
        response = self.client.post(
            "/api/v1/attendance/check-in/",
            {"person_id": self.customer.id, "person_type": "customer"},
            format="json",
        )
        assert response.status_code == 400

    def test_list_derivation_is_tenant_scoped(self) -> None:
        """Another tenant's stale open record never leaks into the list."""
        other_tenant = provision_tenant(name="Rival API Gym", contact_email="owner@rival3.test")
        other_user = User.objects.create_user(
            email="rival@autoapi.test",
            password="testpass",
            first_name="Rival",
            last_name="Member",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        other_customer = Customer.objects.create(
            tenant=other_tenant,
            branch=self.branch,
            user=other_user,
            name="Rival Member",
            phone="+919999000044",
        )
        AttendanceRecord.objects.create(
            tenant=other_tenant,
            customer=other_customer,
            branch=self.branch,
            check_in_time=timezone.now() - timedelta(hours=3),
        )
        response = self.client.get("/api/v1/attendance/attendance/")
        assert response.status_code == 200
        assert response.data["count"] == 0


class PunchIngestSweepTest(AutoCheckoutTestBase):
    """The ADMS ingest batch sweeps stale open records (issue #83)."""

    def _attlog_row(self, pin: str, stamp: str) -> PunchLogRaw:
        """Build an unsaved raw ATTLOG row."""
        raw_line = f"\t{pin}\t{stamp}\t1\t0\t1\t0"
        return PunchLogRaw(tenant=self.tenant, device=self.device, table_name="ATTLOG", raw_line=raw_line)

    def test_ingest_batch_auto_closes_other_stale_record(self) -> None:
        """Pairing one punch also auto-closes an unrelated 3h-old check-in."""
        stale = self._open_record(age=timedelta(hours=3))
        from apps.access.services import ingest_attlog_rows

        result = ingest_attlog_rows(device=self.device, rows=[self._attlog_row("42", "2026-10-20 08:15:00")])
        assert result["paired"] == 1
        stale.refresh_from_db()
        assert stale.check_out_time == stale.check_in_time + timedelta(hours=2)
        assert stale.check_out_is_auto is True

    def test_recent_open_record_survives_ingest_batch(self) -> None:
        """The sweep leaves open records younger than 2h alone."""
        fresh = self._open_record(age=timedelta(minutes=30))
        from apps.access.services import ingest_attlog_rows

        ingest_attlog_rows(device=self.device, rows=[self._attlog_row("42", "2026-10-20 08:15:00")])
        fresh.refresh_from_db()
        assert fresh.check_out_time is None


class BackfillCommandTest(AutoCheckoutTestBase):
    """auto_checkout_backfill — idempotent, tenant-filtered, dry-run."""

    def test_backfill_stamps_across_tenants(self) -> None:
        """The command sweeps every tenant's eligible records."""
        other_tenant = provision_tenant(name="Backfill Rival", contact_email="owner@bf.test")
        other_customer = Customer.objects.create(
            tenant=other_tenant,
            branch=self.branch,
            name="BF Rival",
            phone="+919999000045",
        )
        mine = self._open_record()
        rival = self._open_record(customer=other_customer, tenant=other_tenant)
        call_command("auto_checkout_backfill", stdout=io.StringIO())
        mine.refresh_from_db()
        rival.refresh_from_db()
        assert mine.check_out_is_auto is True
        assert rival.check_out_is_auto is True
        assert mine.check_out_time == mine.check_in_time + timedelta(hours=2)
        assert rival.check_out_time == rival.check_in_time + timedelta(hours=2)

    def test_backfill_is_idempotent(self) -> None:
        """Re-running the command is a no-op."""
        record = self._open_record()
        out = io.StringIO()
        call_command("auto_checkout_backfill", stdout=out)
        assert "1 record(s)" in out.getvalue()
        record.refresh_from_db()
        first = record.check_out_time
        out = io.StringIO()
        call_command("auto_checkout_backfill", stdout=out)
        assert "0 record(s)" in out.getvalue()
        record.refresh_from_db()
        assert record.check_out_time == first

    def test_backfill_tenant_filter(self) -> None:
        """--tenant limits the sweep to that tenant."""
        other_tenant = provision_tenant(name="BF Filter Rival", contact_email="owner@bff.test")
        other_customer = Customer.objects.create(
            tenant=other_tenant,
            branch=self.branch,
            name="BFF Rival",
            phone="+919999000046",
        )
        rival = self._open_record(customer=other_customer, tenant=other_tenant)
        call_command("auto_checkout_backfill", tenant=self.tenant.pk, stdout=io.StringIO())
        rival.refresh_from_db()
        assert rival.check_out_time is None

    def test_backfill_dry_run_writes_nothing(self) -> None:
        """--dry-run reports eligible rows without stamping."""
        record = self._open_record()
        out = io.StringIO()
        call_command("auto_checkout_backfill", dry_run=True, stdout=out)
        assert "would stamp 1 record(s)" in out.getvalue()
        record.refresh_from_db()
        assert record.check_out_time is None

    def test_backfill_never_touches_real_check_out(self) -> None:
        """Rows closed by a real punch stay untouched."""
        record = self._open_record(age=timedelta(hours=3))
        real_out = record.check_in_time + timedelta(minutes=45)
        record.check_out_time = real_out
        record.save(update_fields=["check_out_time", "updated_at"])
        call_command("auto_checkout_backfill", stdout=io.StringIO())
        record.refresh_from_db()
        assert record.check_out_time == real_out
        assert record.check_out_is_auto is False


class LogCheckInSweepTest(AutoCheckoutTestBase):
    """The manual check-in flow sweeps before its duplicate guard."""

    def test_log_check_in_sweeps_stale_open_record_first(self) -> None:
        """log_check_in auto-closes a 3h-old open record and opens a new one."""
        stale = self._open_record(age=timedelta(hours=3))
        record = log_check_in(tenant=self.tenant, person_id=self.customer.id, person_type="customer")
        stale.refresh_from_db()
        assert stale.check_out_is_auto is True
        assert record.pk != stale.pk
        assert record.check_out_time is None

    def test_log_check_in_keeps_guard_within_two_hours(self) -> None:
        """An open visit under 2h old still blocks a duplicate check-in."""
        self._open_record(age=timedelta(minutes=30))
        with self.assertRaises(ValidationError):
            log_check_in(tenant=self.tenant, person_id=self.customer.id, person_type="customer")
