"""History-pull + punch-raw API tests (Siju BioDebug POC).

Covers the stored-transaction re-upload (``DATA QUERY ATTLOG`` over the
ADMS command queue), the raw punch viewer endpoint, and the ingest
idempotency contract: a re-dumped device log never double-folds the
parsed attendance side.
"""

from __future__ import annotations

from datetime import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.access.models import (
    BiometricCredential,
    BiometricDevice,
    DeviceCommandQueue,
    PunchLogRaw,
)
from apps.access.services import HISTORY_PULL_COMMAND, ingest_attlog_rows
from apps.attendance.models import AttendanceRecord
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token


class HistoryPullAPIBase(APITestCase):
    """Shared fixtures: tenant, owner token, member, credential, eSSL ADMS device."""

    def setUp(self) -> None:
        """Create tenant, owner token, customer, credential, and the device."""
        self.tenant = provision_tenant(name="History Gym", contact_email="owner@history.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@history.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="History Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        user = User.objects.create_user(
            email="member@history.test",
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
        # Mirrors prod device 2: eSSL firmware over the ADMS push protocol.
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="essl",
            model="eFace990",
            serial_number="HIST-DEV-1",
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
        self.pull_url = f"/api/v1/access/devices/{self.device.pk}/pull-history/"
        self.raw_url = f"/api/v1/access/devices/{self.device.pk}/punch-raw/"
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _customer_token_client(self) -> None:
        """Switch the API client to a customer-role token (no device perms)."""
        user = User.objects.create_user(
            email="cust@history.test",
            password="testpass",
            first_name="Cus",
            last_name="Tomer",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        token = issue_token(user, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _other_tenant_device(self) -> BiometricDevice:
        """A device belonging to a different tenant."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="owner@other.test")
        other_branch = Branch.objects.create(tenant=other_tenant, name="Other Branch", branch_type="gym")
        return BiometricDevice.objects.create(
            tenant=other_tenant,
            branch=other_branch,
            vendor="essl",
            model="eFace990",
            serial_number="OTHER-DEV-1",
            name="Other Entrance",
            connection_type="webhook",
        )


class PullHistoryQueueTest(HistoryPullAPIBase):
    """POST pull-history — queues DATA QUERY ATTLOG for the device."""

    def test_pull_history_queues_command(self) -> None:
        """The endpoint queues the data-query command and reports the contract payload."""
        response = self.client.post(f"{self.pull_url}?to=2026-10-11", format="json")
        assert response.status_code == 200
        row = DeviceCommandQueue.objects.get()
        assert response.data == {
            "queued": True,
            "mechanism": "data_query_attlog",
            "detail": response.data["detail"],
            "device_id": self.device.pk,
            "last_seen_at": None,
        }
        assert response.data["detail"]
        assert row.command == HISTORY_PULL_COMMAND
        assert row.device_id == self.device.pk
        assert row.tenant_id == self.tenant.pk
        assert row.payload["mechanism"] == "data_query_attlog"
        # Explicit window: the wire text carries the requested bounds.
        assert row.payload["text"] == ("DATA QUERY ATTLOG StartTime=2000-01-01 00:00:00\tEndTime=2026-10-11 00:00:00")
        assert row.executed_at is None

    def test_pull_history_default_window_covers_full_history(self) -> None:
        """Without from/to the window starts at the 2000 epoch (full stored log)."""
        response = self.client.post(self.pull_url, format="json")
        assert response.status_code == 200
        text = DeviceCommandQueue.objects.get().payload["text"]
        assert text.startswith("DATA QUERY ATTLOG StartTime=2000-01-01 00:00:00\tEndTime=")

    def test_pull_history_delivered_verbatim_on_getrequest(self) -> None:
        """The device's next poll receives the exact command line, C:-prefixed."""
        self.client.post(f"{self.pull_url}?from=2026-10-01&to=2026-10-11", format="json")
        row = DeviceCommandQueue.objects.get()
        response = self.client.get("/iclock/getrequest?SN=HIST-DEV-1")
        assert response.status_code == 200
        assert response.content.decode() == (
            f"C:{row.pk}:DATA QUERY ATTLOG StartTime=2026-10-01 00:00:00\tEndTime=2026-10-11 00:00:00"
        )
        row.refresh_from_db()
        assert row.executed_at is not None

    def test_pull_history_pending_dedupe(self) -> None:
        """A second pull while one is undelivered does not queue a duplicate."""
        self.client.post(self.pull_url, format="json")
        response = self.client.post(self.pull_url, format="json")
        assert response.status_code == 200
        assert response.data["queued"] is True
        assert "already queued" in response.data["detail"]
        assert DeviceCommandQueue.objects.count() == 1

    def test_pull_history_repull_after_delivery_queues_fresh_row(self) -> None:
        """Re-pulling after delivery is allowed — a fresh command is queued."""
        self.client.post(self.pull_url, format="json")
        self.client.get("/iclock/getrequest?SN=HIST-DEV-1")
        response = self.client.post(self.pull_url, format="json")
        assert response.status_code == 200
        assert "already queued" not in response.data["detail"]
        assert DeviceCommandQueue.objects.count() == 2

    def test_pull_history_non_adms_vendor_rejected(self) -> None:
        """Vendors that do not speak the ADMS push protocol get a 400."""
        BiometricDevice.objects.filter(pk=self.device.pk).update(vendor="hikvision")
        response = self.client.post(self.pull_url, format="json")
        assert response.status_code == 400
        assert "ADMS push-mode" in response.data["detail"]
        assert DeviceCommandQueue.objects.count() == 0

    def test_pull_history_non_webhook_connection_rejected(self) -> None:
        """ADMS vendors on pull/cloud connections get a 400 too."""
        BiometricDevice.objects.filter(pk=self.device.pk).update(connection_type="agent")
        response = self.client.post(self.pull_url, format="json")
        assert response.status_code == 400
        assert "ADMS push-mode" in response.data["detail"]
        assert DeviceCommandQueue.objects.count() == 0

    def test_pull_history_invalid_window_param(self) -> None:
        """Unparseable from/to bounds are a 400, nothing queued."""
        response = self.client.post(f"{self.pull_url}?from=not-a-date", format="json")
        assert response.status_code == 400
        assert DeviceCommandQueue.objects.count() == 0

    def test_pull_history_other_tenant_device_404(self) -> None:
        """Devices outside the request tenant are invisible."""
        other = self._other_tenant_device()
        response = self.client.post(f"/api/v1/access/devices/{other.pk}/pull-history/", format="json")
        assert response.status_code == 404

    def test_pull_history_requires_edit_permission(self) -> None:
        """A customer-role token cannot trigger a device re-dump."""
        self._customer_token_client()
        response = self.client.post(self.pull_url, format="json")
        assert response.status_code == 403
        assert DeviceCommandQueue.objects.count() == 0


class PunchRawListTest(HistoryPullAPIBase):
    """GET punch-raw — newest-first raw punch viewer for the device."""

    def _seed_rows(self) -> None:
        """Push one OPERLOG and two ATTLOG rows through the device endpoint."""
        self.client.post(
            "/iclock/cdata?SN=HIST-DEV-1&table=OPERLOG",
            data="OPERLOG\r\n\t7\t1\t2026-10-20 08:15:00\t1\t0\t0",
            content_type="text/plain",
        )
        self.client.post(
            "/iclock/cdata?SN=HIST-DEV-1&table=ATTLOG",
            data="\t7\t2026-10-20 08:15:00\t1\t0\t1\t0",
            content_type="text/plain",
        )
        self.client.post(
            "/iclock/cdata?SN=HIST-DEV-1&table=ATTLOG",
            data="\t7\t2026-10-20 18:05:30\t0\t0\t1\t0",
            content_type="text/plain",
        )

    def test_lists_rows_newest_first_with_attlog_parse(self) -> None:
        """Rows come back newest-first; ATTLOG lines carry pin + punch time."""
        self._seed_rows()
        response = self.client.get(self.raw_url)
        assert response.status_code == 200
        # The OPERLOG body stores two lines (marker + data), ATTLOG one each.
        assert response.data["count"] == 4
        rows = response.data["results"]
        assert [row["table_name"] for row in rows] == ["ATTLOG", "ATTLOG", "OPERLOG", "OPERLOG"]
        newest = rows[0]
        assert newest["raw_line"] == "\t7\t2026-10-20 18:05:30\t0\t0\t1\t0"
        assert newest["pin"] == "7"
        # Device wall time (IST) survives the round-trip.
        expected_punch_at = timezone.make_aware(datetime(2026, 10, 20, 18, 5, 30))  # noqa: DTZ001
        assert newest["punch_at"] == expected_punch_at
        assert newest["received_at"] is not None
        assert newest["id"] is not None
        # Non-ATTLOG rows carry no parsed punch fields.
        assert rows[2]["pin"] is None
        assert rows[2]["punch_at"] is None

    def test_limit_bounds_page(self) -> None:
        """?limit=2 returns only the two newest rows."""
        self._seed_rows()
        response = self.client.get(f"{self.raw_url}?limit=2")
        assert response.status_code == 200
        assert response.data["count"] == 2
        assert response.data["results"][0]["raw_line"] == "\t7\t2026-10-20 18:05:30\t0\t0\t1\t0"

    def test_limit_capped_at_500(self) -> None:
        """A limit above the cap is clamped to 500 rows."""
        PunchLogRaw.objects.bulk_create(
            [
                PunchLogRaw(tenant=self.tenant, device=self.device, table_name="ATTLOG", raw_line=f"\t7\trow {i}")
                for i in range(501)
            ]
        )
        response = self.client.get(f"{self.raw_url}?limit=501")
        assert response.status_code == 200
        assert response.data["count"] == 500

    def test_limit_invalid_rejected(self) -> None:
        """A non-integer limit is a 400."""
        response = self.client.get(f"{self.raw_url}?limit=abc")
        assert response.status_code == 400

    def test_other_tenant_device_404(self) -> None:
        """Raw punches of another tenant's device are invisible."""
        other = self._other_tenant_device()
        response = self.client.get(f"/api/v1/access/devices/{other.pk}/punch-raw/")
        assert response.status_code == 404

    def test_requires_log_view_permission(self) -> None:
        """A customer-role token cannot browse raw punches."""
        self._seed_rows()
        self._customer_token_client()
        response = self.client.get(self.raw_url)
        assert response.status_code == 403


class ReDumpIdempotencyTest(TestCase):
    """Re-dumps (history pulls) must not duplicate the parsed attendance side."""

    def setUp(self) -> None:
        """Create tenant, branch, member, credential, and the ADMS device."""
        self.tenant = provision_tenant(name="Redump Gym", contact_email="owner@redump.test")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        user = User.objects.create_user(
            email="member@redump.test",
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
            vendor="essl",
            model="eFace990",
            serial_number="REDUMP-DEV-1",
            name="Main Entrance",
            connection_type="webhook",
        )

    def _credential(self, device_user_id: str) -> BiometricCredential:
        """Enroll a credential for the customer on the device."""
        return BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id=device_user_id,
        )

    def _post_attlog(self, body: str) -> None:
        """Push an ATTLOG body to the device endpoint."""
        response = self.client.post(
            "/iclock/cdata?SN=REDUMP-DEV-1&table=ATTLOG",
            data=body,
            content_type="text/plain",
        )
        assert response.status_code == 200

    def _records(self) -> list:
        """The tenant's attendance records, oldest first."""
        return list(AttendanceRecord.objects.for_tenant(self.tenant).order_by("check_in_time"))

    def test_reingesting_same_rows_is_a_noop(self) -> None:
        """A replay of already-ingested raw rows pairs nothing new."""
        self._credential("7")
        rows = [
            PunchLogRaw(
                tenant=self.tenant,
                device=self.device,
                table_name="ATTLOG",
                raw_line="\t7\t2026-10-20 08:15:00\t1\t0\t1\t0",
            ),
            PunchLogRaw(
                tenant=self.tenant,
                device=self.device,
                table_name="ATTLOG",
                raw_line="\t7\t2026-10-20 18:05:30\t0\t0\t1\t0",
            ),
        ]
        PunchLogRaw.objects.bulk_create(rows)
        result = ingest_attlog_rows(device=self.device, rows=rows)
        assert result["paired"] == 2
        again = ingest_attlog_rows(device=self.device, rows=rows)
        assert again["paired"] == 0
        assert again["skipped"] == 2

    def test_device_redump_does_not_duplicate_attendance(self) -> None:
        """The same punch body arriving twice stores raw twice, pairs once."""
        self._credential("7")
        body = "\t7\t2026-10-20 08:15:00\t1\t0\t1\t0"
        self._post_attlog(body)
        self._post_attlog(body)
        assert PunchLogRaw.objects.count() == 2  # verbatim raw store keeps both
        assert sum(1 for row in PunchLogRaw.objects.all() if row.ingested_at is not None) == 2
        records = self._records()
        assert len(records) == 1
        assert timezone.localtime(records[0].check_in_time).strftime("%Y-%m-%d %H:%M:%S") == "2026-10-20 08:15:00"
        assert records[0].check_out_time is None

    def test_full_day_redump_keeps_check_out(self) -> None:
        """Re-sending a whole day's punches leaves the folded record intact."""
        self._credential("7")
        day = "\t7\t2026-10-20 08:15:00\t1\t0\t1\t0\r\n\t7\t2026-10-20 18:05:30\t0\t0\t1\t0"
        self._post_attlog(day)
        self._post_attlog(day)
        records = self._records()
        assert len(records) == 1
        assert records[0].check_out_time is not None
        assert timezone.localtime(records[0].check_out_time).strftime("%Y-%m-%d %H:%M:%S") == "2026-10-20 18:05:30"

    def test_orphan_punch_pairs_after_later_enrollment_redump(self) -> None:
        """A punch enrolled later pairs exactly once on the re-dump."""
        body = "\t999\t2026-10-20 08:15:00\t1\t0\t1\t0"
        self._post_attlog(body)  # no credential 999 yet → orphan
        orphan_row = PunchLogRaw.objects.get()
        assert orphan_row.is_orphan is True
        assert orphan_row.ingested_at is not None  # processed, not pending

        self._credential("999")
        self._post_attlog(body)  # the re-dump arrives as a NEW raw row
        rows = list(PunchLogRaw.objects.order_by("pk"))
        assert len(rows) == 2
        assert rows[1].is_orphan is False
        records = self._records()
        assert len(records) == 1
        assert timezone.localtime(records[0].check_in_time).strftime("%Y-%m-%d %H:%M:%S") == "2026-10-20 08:15:00"

        # A third dump still changes nothing.
        self._post_attlog(body)
        assert PunchLogRaw.objects.count() == 3
        records = self._records()
        assert len(records) == 1
        assert records[0].check_out_time is None
