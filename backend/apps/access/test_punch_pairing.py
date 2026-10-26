"""Phase-2 end-to-end punch pairing tests (POST /iclock/cdata → attendance).

The device-facing contract must hold while pairing runs: plain-text OK
always, raw rows always stored, orphans flagged and excluded, IST local
dates, and the tenant-wide same-id fallback pairing to the punching
device's branch.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.access.models import BiometricCredential, BiometricDevice, PunchLogRaw
from apps.attendance.models import AttendanceRecord
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.services import provision_tenant
from apps.users.models import User

SN = "ADMS-PAIR-001"


class PunchPairingTestBase(TestCase):
    """Shared fixtures: tenant, branch, member, credential, ADMS device."""

    def setUp(self) -> None:
        """Create tenant, branch, customer, credential, and the device."""
        self.tenant = provision_tenant(name="Punch Gym", contact_email="owner@punch.test")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        user = User.objects.create_user(
            email="member@punch.test",
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
            serial_number=SN,
            name="Main Entrance",
            connection_type="webhook",
        )
        self.credential = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="7",
        )

    def _post_attlog(self, body: str) -> object:
        """Push ATTLOG lines to the device endpoint."""
        return self.client.post(f"/iclock/cdata?SN={SN}&table=ATTLOG", data=body, content_type="text/plain")


class CdataPairingTest(PunchPairingTestBase):
    """ATTLOG pushes resolve and pair into AttendanceRecords."""

    def test_attlog_punch_creates_attendance_record(self) -> None:
        """A resolved punch opens the member's day record."""
        response = self._post_attlog("\t7\t2026-10-20 08:15:00\t1\t0\t1\t0")
        assert response.status_code == 200
        assert response.content == b"OK"
        record = AttendanceRecord.objects.get()
        assert record.customer == self.customer
        assert record.branch == self.branch
        assert record.method == AttendanceRecord.Method.BIOMETRIC
        # Issue #83: the punch is days old and never got a paired
        # check-out, so the batch sweep auto-closed it at check-in + 2h.
        assert record.check_out_time == record.check_in_time + timedelta(hours=2)
        assert record.check_out_is_auto is True
        assert record.date.isoformat() == "2026-10-20"
        # Device wall time is IST: aware stamp must keep that wall clock.
        assert timezone.localtime(record.check_in_time).isoformat().startswith("2026-10-20T08:15:00")

    def test_evening_punch_lands_on_same_local_date(self) -> None:
        """An 20:30 IST punch pairs on the 20th — not a UTC-shifted 21st."""
        self._post_attlog("\t7\t2026-10-20 08:15:00\t1\t0\t1\t0")
        self._post_attlog("\t7\t2026-10-20 20:30:00\t0\t0\t1\t0")
        record = AttendanceRecord.objects.get()
        assert record.date.isoformat() == "2026-10-20"
        assert timezone.localtime(record.check_out_time).hour == 20

    def test_in_out_double_read_sequence(self) -> None:
        """In → +10s re-read (ignored) → out → later out slides check_out."""
        self._post_attlog("\t7\t2026-10-20 08:15:00\t1\t0\t1\t0")
        self._post_attlog("\t7\t2026-10-20 08:15:10\t1\t0\t1\t0")  # double-read
        self._post_attlog("\t7\t2026-10-20 12:00:00\t0\t0\t1\t0")  # check-out
        self._post_attlog("\t7\t2026-10-20 18:30:00\t0\t0\t1\t0")  # keep last
        assert AttendanceRecord.objects.count() == 1
        record = AttendanceRecord.objects.get()
        assert record.check_in_time == timezone.make_aware(datetime(2026, 10, 20, 8, 15, 0))  # noqa: DTZ001
        assert timezone.localtime(record.check_out_time).isoformat().startswith("2026-10-20T18:30:00")

    def test_orphan_punch_flagged_and_not_paired(self) -> None:
        """An unknown device_user_id is stored raw, flagged, never paired."""
        response = self._post_attlog("\t7\t2026-10-20 08:15:00\t1\t0\t1\t0\r\n\t999\t2026-10-20 08:16:00\t1\t0\t1\t0")
        assert response.content == b"OK"
        assert AttendanceRecord.objects.count() == 1
        resolved_row = PunchLogRaw.objects.get(raw_line__contains="\t7\t")
        orphan_row = PunchLogRaw.objects.get(raw_line__contains="\t999\t")
        assert resolved_row.is_orphan is False
        assert orphan_row.is_orphan is True

    def test_deactivated_credential_punch_is_orphan(self) -> None:
        """Deactivating the credential stops pairing immediately."""
        self.credential.is_active = False
        self.credential.save(update_fields=["is_active", "updated_at"])
        self._post_attlog("\t7\t2026-10-20 08:15:00\t1\t0\t1\t0")
        assert AttendanceRecord.objects.count() == 0
        assert PunchLogRaw.objects.get().is_orphan is True

    def test_pairing_failure_never_breaks_ok(self) -> None:
        """A blow-up inside pairing still answers OK; raw rows persist."""
        with mock.patch("apps.attendance.services.pair_punch", side_effect=RuntimeError("boom")):
            response = self._post_attlog("\t7\t2026-10-20 08:15:00\t1\t0\t1\t0")
        assert response.status_code == 200
        assert response.content == b"OK"
        assert PunchLogRaw.objects.count() == 1
        assert AttendanceRecord.objects.count() == 0

    def test_non_attlog_tables_are_not_paired(self) -> None:
        """OPERLOG/UNKNOWN rows store raw and never touch attendance."""
        response = self.client.post(
            f"/iclock/cdata?SN={SN}&table=OPERLOG",
            data="OPERLOG\r\n\t7\t1\t2026-10-20 08:15:00\t1\t0\t0",
            content_type="text/plain",
        )
        assert response.content == b"OK"
        assert AttendanceRecord.objects.count() == 0


class PunchFallbackResolutionTest(PunchPairingTestBase):
    """Tenant-wide same-id fallback: punch on device B pairs to customer."""

    def test_punch_on_second_device_pairs_via_canonical_id(self) -> None:
        """The id lives on device A; a punch on device B still resolves."""
        other_branch = Branch.objects.create(tenant=self.tenant, name="East Branch", branch_type="gym")
        device_b = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=other_branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number="ADMS-PAIR-002",
            name="East Entrance",
            connection_type="webhook",
        )
        response = self.client.post(
            f"/iclock/cdata?SN={device_b.serial_number}&table=ATTLOG",
            data="\t7\t2026-10-20 09:00:00\t1\t0\t1\t0",
            content_type="text/plain",
        )
        assert response.content == b"OK"
        record = AttendanceRecord.objects.get()
        assert record.customer == self.customer
        # Branch = the punching device's branch, not the credential's.
        assert record.branch == other_branch

    def test_same_id_in_other_tenant_does_not_resolve(self) -> None:
        """The fallback is tenant-scoped: another tenant's id never matches."""
        other_tenant = provision_tenant(name="Rival Punch Gym", contact_email="owner@rival.test")
        other_branch = Branch.objects.create(tenant=other_tenant, name="Rival Branch", branch_type="gym")
        other_device = BiometricDevice.objects.create(
            tenant=other_tenant,
            branch=other_branch,
            vendor="zkteco",
            model="BioFace C1",
            serial_number="ADMS-PAIR-RIVAL",
            name="Rival Entrance",
        )
        rival_user = User.objects.create_user(
            email="rival@punch.test",
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
        BiometricCredential.objects.create(
            tenant=other_tenant,
            customer=rival,
            device=other_device,
            credential_type="fingerprint",
            device_user_id="7",
        )
        # A punch on the rival device resolves to the rival customer only.
        response = self.client.post(
            f"/iclock/cdata?SN={other_device.serial_number}&table=ATTLOG",
            data="\t7\t2026-10-20 09:00:00\t1\t0\t1\t0",
            content_type="text/plain",
        )
        assert response.content == b"OK"
        record = AttendanceRecord.objects.get()
        assert record.customer == rival
        assert record.tenant == other_tenant
