"""ADMS push-protocol endpoint tests (ZKTeco/eSSL /iclock/*, phase 1).

The wire contract is firmware-driven and strict: plain-text responses
always, SN-whitelist auth, exact handshake lines, raw row storage.
"""

from __future__ import annotations

from django.test import Client, TestCase

from apps.access.models import (
    AdmsRequestLog,
    BiometricCredential,
    BiometricDevice,
    DeviceCommandQueue,
    PunchLogRaw,
)
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.tenants.services import provision_tenant
from apps.users.models import User

SN = "ADMS-TEST-001"


class AdmsEndpointTestBase(TestCase):
    """Shared fixtures: tenant, branch, customer, credential, ADMS device."""

    def setUp(self) -> None:
        """Create tenant, branch, customer, credential, and the device."""
        self.tenant = provision_tenant(name="ADMS Gym", contact_email="owner@adms.test")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        user = User.objects.create_user(
            email="cust@adms.test",
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
            serial_number=SN,
            name="Entrance",
            connection_type="webhook",
        )
        self.credential = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="1001",
        )

    def _queue_command(
        self,
        *,
        command: str = "DATA UPDATE USER",
        payload: dict | None = None,
    ) -> DeviceCommandQueue:
        """Queue one outbound command for the device."""
        return DeviceCommandQueue.objects.create(
            tenant=self.tenant,
            device=self.device,
            command=command,
            payload=payload if payload is not None else {"pin": "1001", "name": "John Doe"},
        )


class CdataHandshakeTest(AdmsEndpointTestBase):
    """GET /iclock/cdata — options handshake."""

    def test_handshake_exact_lines(self) -> None:
        """A registered SN receives the exact handshake block, newline-terminated."""
        response = self.client.get(f"/iclock/cdata?SN={SN}&options=all")
        assert response.status_code == 200
        expected = (
            f"GET OPTION FROM: {SN}\n"
            "ATTLOGStamp=None\n"
            "RealTime=1\n"
            "TransInterval=1\n"
            "Delay=10\n"
            "TimeZone=5.5\n"
        )
        assert response.content.decode() == expected
        assert response["Content-Type"].startswith("text/plain")

    def test_handshake_accepts_lowercase_sn(self) -> None:
        """SN casing varies by firmware — ``sn`` works identically."""
        response = self.client.get(f"/iclock/cdata?sn={SN}&options=all")
        assert response.status_code == 200
        assert response.content.decode().startswith(f"GET OPTION FROM: {SN}\n")

    def test_unregistered_sn_rejected_plain_text(self) -> None:
        """An unknown serial gets a non-200, never JSON."""
        response = self.client.get("/iclock/cdata?SN=NOT-REGISTERED&options=all")
        assert response.status_code != 200
        assert response["Content-Type"].startswith("text/plain")
        assert b'"' not in response.content

    def test_inactive_device_rejected(self) -> None:
        """A disabled device's serial is no longer whitelisted."""
        BiometricDevice.objects.filter(pk=self.device.pk).update(is_active=False)
        response = self.client.get(f"/iclock/cdata?SN={SN}&options=all")
        assert response.status_code != 200


class CdataPushTest(AdmsEndpointTestBase):
    """POST /iclock/cdata — attendance/table push."""

    def _post(self, body: str, query: str = f"SN={SN}&table=ATTLOG"):
        return self.client.post(f"/iclock/cdata?{query}", data=body, content_type="text/plain")

    def test_attlog_post_stores_raw_rows_and_replies_ok(self) -> None:
        """Every tab-separated row is stored raw, verbatim; reply is OK."""
        body = "\r\n".join(
            [
                "\t1\t2026-10-20 08:15:00\t1\t0\t1\t0",
                "\t1\t2026-10-20 18:05:30\t0\t0\t1\t0",
            ]
        )
        response = self._post(body)
        assert response.status_code == 200
        assert response.content == b"OK"
        assert response["Content-Type"].startswith("text/plain")
        rows = list(PunchLogRaw.objects.filter(device=self.device).order_by("pk"))
        assert len(rows) == 2
        assert all(row.table_name == "ATTLOG" for row in rows)
        assert rows[0].raw_line == "\t1\t2026-10-20 08:15:00\t1\t0\t1\t0"
        assert rows[1].raw_line == "\t1\t2026-10-20 18:05:30\t0\t0\t1\t0"
        assert rows[0].received_at is not None

    def test_table_detected_from_leading_marker(self) -> None:
        """Without a table param, a leading OPERLOG marker names the table."""
        response = self._post(
            "OPERLOG\r\n\t1\t1\t2026-10-20 08:15:00\t1\t0\t0",
            query=f"SN={SN}",
        )
        assert response.status_code == 200
        tables = set(PunchLogRaw.objects.filter(device=self.device).values_list("table_name", flat=True))
        assert tables == {"OPERLOG"}

    def test_unknown_table_falls_back_to_unknown(self) -> None:
        """Rows without any table hint are still stored, marked UNKNOWN."""
        response = self._post("\t1\t2026-10-20 08:15:00\t1\t0\t1\t0", query=f"SN={SN}")
        assert response.status_code == 200
        assert PunchLogRaw.objects.filter(device=self.device, table_name="UNKNOWN").count() == 1

    def test_empty_lines_are_skipped(self) -> None:
        """Blank lines carry no data — only real rows are stored."""
        response = self._post("\r\n\r\n\t1\t2026-10-20 08:15:00\t1\t0\t1\t0\r\n")
        assert response.status_code == 200
        assert PunchLogRaw.objects.filter(device=self.device).count() == 1

    def test_post_stamps_last_seen(self) -> None:
        """Any authenticated contact refreshes device liveness."""
        assert self.device.last_seen_at is None
        self._post("\t1\t2026-10-20 08:15:00\t1\t0\t1\t0")
        self.device.refresh_from_db()
        assert self.device.last_seen_at is not None

    def test_push_from_unregistered_sn_rejected(self) -> None:
        """Unregistered serials store nothing and get a plain-text rejection."""
        response = self._post("\t1\t2026-10-20 08:15:00\t1\t0\t1\t0", query="SN=NOT-REGISTERED&table=ATTLOG")
        assert response.status_code != 200
        assert response["Content-Type"].startswith("text/plain")
        assert PunchLogRaw.objects.count() == 0


class GetRequestTest(AdmsEndpointTestBase):
    """GET /iclock/getrequest — command delivery."""

    def test_no_queued_commands_replies_ok(self) -> None:
        """With nothing queued the device is told OK."""
        response = self.client.get(f"/iclock/getrequest?SN={SN}")
        assert response.status_code == 200
        assert response.content == b"OK"
        assert response["Content-Type"].startswith("text/plain")

    def test_delivers_upsert_command_exact_text(self) -> None:
        """User upsert renders the guide wire format with literal tabs."""
        row = self._queue_command()
        response = self.client.get(f"/iclock/getrequest?SN={SN}")
        assert response.status_code == 200
        expected = f"C:{row.pk}:DATA UPDATE USERINFO PIN=1001\tName=John Doe\tPri=0\tGrp=1"
        assert response.content.decode() == expected
        row.refresh_from_db()
        assert row.executed_at is not None

    def test_delivers_oldest_first(self) -> None:
        """Commands deliver in queue order, one per poll."""
        first = self._queue_command(payload={"pin": "1001", "name": "John Doe"})
        second = self._queue_command(payload={"pin": "1002", "name": "Jane Roe"})
        response = self.client.get(f"/iclock/getrequest?SN={SN}")
        assert response.content.decode() == f"C:{first.pk}:DATA UPDATE USERINFO PIN=1001\tName=John Doe\tPri=0\tGrp=1"
        second.refresh_from_db()
        assert second.executed_at is None
        response = self.client.get(f"/iclock/getrequest?SN={SN}")
        assert response.content.decode() == f"C:{second.pk}:DATA UPDATE USERINFO PIN=1002\tName=Jane Roe\tPri=0\tGrp=1"

    def test_delete_command_format(self) -> None:
        """User delete renders the DELETE wire format."""
        row = self._queue_command(command="DATA DELETE USER", payload={"pin": "1001"})
        response = self.client.get(f"/iclock/getrequest?SN={SN}")
        assert response.content.decode() == f"C:{row.pk}:DATA DELETE USERINFO PIN=1001"
        row.refresh_from_db()
        assert row.executed_at is not None

    def test_pin_and_name_fall_back_to_credential(self) -> None:
        """A credential reference in the payload resolves pin + customer name."""
        row = self._queue_command(payload={"credential_id": self.credential.pk})
        response = self.client.get(f"/iclock/getrequest?SN={SN}")
        assert response.content.decode() == f"C:{row.pk}:DATA UPDATE USERINFO PIN=1001\tName=John Doe\tPri=0\tGrp=1"

    def test_unregistered_sn_rejected(self) -> None:
        """Unregistered serials get a non-200 plain-text rejection."""
        response = self.client.get("/iclock/getrequest?SN=NOT-REGISTERED")
        assert response.status_code != 200
        assert response["Content-Type"].startswith("text/plain")


class DeviceCmdTest(AdmsEndpointTestBase):
    """POST /iclock/devicecmd — device acknowledges delivery."""

    def test_devicecmd_marks_row_done(self) -> None:
        """The acknowledged queue row is marked done; reply is OK."""
        row = self._queue_command()
        response = self.client.post(
            f"/iclock/devicecmd?SN={SN}",
            data=f"ID={row.pk}&Return=0",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 200
        assert response.content == b"OK"
        assert response["Content-Type"].startswith("text/plain")
        row.refresh_from_db()
        assert row.executed_at is not None

    def test_devicecmd_confirm_is_idempotent(self) -> None:
        """A confirm after delivery never re-stamps executed_at."""
        row = self._queue_command()
        self.client.get(f"/iclock/getrequest?SN={SN}")
        delivered_at = DeviceCommandQueue.objects.get(pk=row.pk).executed_at
        response = self.client.post(
            f"/iclock/devicecmd?SN={SN}",
            data=f"ID={row.pk}&Return=0",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.content == b"OK"
        row.refresh_from_db()
        assert row.executed_at == delivered_at

    def test_devicecmd_unknown_id_still_ok(self) -> None:
        """Stale/unknown command ids must not break the device loop."""
        response = self.client.post(
            f"/iclock/devicecmd?SN={SN}",
            data="ID=999999&Return=0",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_unregistered_sn_rejected(self) -> None:
        """Unregistered serials get a non-200 plain-text rejection."""
        response = self.client.post(
            "/iclock/devicecmd?SN=NOT-REGISTERED",
            data="ID=1&Return=0",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code != 200


class AdmsRequestLogTest(AdmsEndpointTestBase):
    """Every inbound ADMS request leaves one audit row."""

    def test_all_four_endpoints_logged(self) -> None:
        """Handshake, push, poll, and confirm each write a full log row."""
        row = self._queue_command()
        self.client.get(f"/iclock/cdata?SN={SN}&options=all")
        self.client.post(
            f"/iclock/cdata?SN={SN}&table=ATTLOG",
            data="\t1\t2026-10-20 08:15:00\t1\t0\t1\t0",
            content_type="text/plain",
        )
        self.client.get(f"/iclock/getrequest?SN={SN}")
        self.client.post(
            f"/iclock/devicecmd?SN={SN}",
            data=f"ID={row.pk}&Return=0",
            content_type="application/x-www-form-urlencoded",
        )
        logs = list(AdmsRequestLog.objects.order_by("created_at", "pk"))
        assert len(logs) == 4
        assert [log.path for log in logs] == [
            "/iclock/cdata",
            "/iclock/cdata",
            "/iclock/getrequest",
            "/iclock/devicecmd",
        ]
        assert all(log.sn == SN for log in logs)
        assert all(log.device_id == self.device.pk for log in logs)
        assert all(log.tenant_id == self.tenant.pk for log in logs)
        assert logs[0].query_string == f"SN={SN}&options=all"
        assert logs[1].raw_body == "\t1\t2026-10-20 08:15:00\t1\t0\t1\t0"
        assert logs[3].raw_body == f"ID={row.pk}&Return=0"
        assert all(log.remote_addr for log in logs)

    def test_unregistered_requests_logged_without_device(self) -> None:
        """Rejected serials are still audited, with null device/tenant."""
        self.client.get("/iclock/cdata?SN=NOT-REGISTERED&options=all")
        log = AdmsRequestLog.objects.get()
        assert log.sn == "NOT-REGISTERED"
        assert log.device is None
        assert log.tenant is None

    def test_device_posts_pass_without_csrf_token(self) -> None:
        """Devices cannot answer CSRF challenges — POSTs must go through."""
        strict_client = Client(enforce_csrf_checks=True)
        response = strict_client.post(
            f"/iclock/cdata?SN={SN}&table=ATTLOG",
            data="\t1\t2026-10-20 08:15:00\t1\t0\t1\t0",
            content_type="text/plain",
        )
        assert response.status_code == 200
        assert response.content == b"OK"
