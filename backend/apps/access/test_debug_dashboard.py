"""Biometrics debug dashboard tests (staff-only server-rendered view).

The dashboard is a read-only diagnostic over the live ADMS stack, so
the contract under test is: strict staff gating, correct section
rendering, SN filtering, escaping/truncation of raw device input, and
admin visibility for the three underlying models.
"""

from __future__ import annotations

from django.test import TestCase

from apps.access.models import AdmsRequestLog, BiometricDevice, PunchLogRaw
from apps.branches.models import Branch
from apps.tenants.services import provision_tenant
from apps.users.models import User

SN = "ADMS-DEBUG-001"
SN_OTHER = "ADMS-DEBUG-002"


class BiometricsDebugDashboardTestBase(TestCase):
    """Shared fixtures: tenant, branch, device, raw rows, staff user."""

    def setUp(self) -> None:
        """Create tenant, branch, device, sample traffic, and users."""
        self.tenant = provision_tenant(name="Debug Gym", contact_email="owner@debug.test")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="essl",
            model="eFace990",
            serial_number=SN,
            name="Entrance",
            connection_type="webhook",
        )
        self.punch = PunchLogRaw.objects.create(
            tenant=self.tenant,
            device=self.device,
            table_name="ATTLOG",
            raw_line="\t1\t2026-10-20 08:15:00\t1\t0\t1\t0",
        )
        self.registered_log = AdmsRequestLog.objects.create(
            device=self.device,
            tenant=self.tenant,
            path="/iclock/cdata",
            query_string=f"SN={SN}&table=ATTLOG",
            raw_body="\t1\t2026-10-20 08:15:00\t1\t0\t1\t0",
            sn=SN,
            remote_addr="192.168.1.50",
        )
        # A hit from a serial that is not whitelisted — the 403 case.
        self.unknown_log = AdmsRequestLog.objects.create(
            device=None,
            tenant=None,
            path="/iclock/cdata",
            query_string="SN=NOT-REGISTERED&options=all",
            raw_body="",
            sn="NOT-REGISTERED",
            remote_addr="192.168.1.99",
        )
        self.staff = User.objects.create_user(
            email="staff@debug.test",
            password="testpass",
            first_name="Staff",
            last_name="Ops",
            is_staff=True,
            tenant=self.tenant,
        )
        self.regular = User.objects.create_user(
            email="cust@debug.test",
            password="testpass",
            first_name="John",
            last_name="Doe",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def _second_device_traffic(self) -> BiometricDevice:
        """Create a second device with its own punch + request rows."""
        device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="zkteco",
            model="uFace800",
            serial_number=SN_OTHER,
            name="Exit",
            connection_type="webhook",
        )
        PunchLogRaw.objects.create(
            tenant=self.tenant,
            device=device,
            table_name="ATTLOG",
            raw_line="\t2\t2026-10-20 09:00:00\t1\t0\t1\t0",
        )
        AdmsRequestLog.objects.create(
            device=device,
            tenant=self.tenant,
            path="/iclock/getrequest",
            query_string=f"SN={SN_OTHER}",
            sn=SN_OTHER,
            remote_addr="192.168.1.51",
        )
        return device


class BiometricsDebugAuthTest(BiometricsDebugDashboardTestBase):
    """The dashboard is staff-only via Django-admin auth."""

    def test_anonymous_user_redirected_to_admin_login(self) -> None:
        """Anonymous visitors are redirected to the admin login page."""
        response = self.client.get("/debug/biometrics/")
        assert response.status_code == 302
        assert "/admin/login" in response["Location"]

    def test_authenticated_non_staff_user_redirected(self) -> None:
        """A signed-in customer (non-staff) never sees the dashboard."""
        self.client.force_login(self.regular)
        response = self.client.get("/debug/biometrics/")
        assert response.status_code == 302
        assert "/admin/login" in response["Location"]

    def test_staff_user_gets_200(self) -> None:
        """A staff member opens the dashboard successfully."""
        self.client.force_login(self.staff)
        response = self.client.get("/debug/biometrics/")
        assert response.status_code == 200


class BiometricsDebugRenderTest(BiometricsDebugDashboardTestBase):
    """The three sections render the live ADMS data."""

    def setUp(self) -> None:
        """Sign in as staff for every rendering test."""
        super().setUp()
        self.client.force_login(self.staff)

    def test_device_section_renders_registry_and_liveness(self) -> None:
        """Device rows show serial, active flag, and request-log count."""
        response = self.client.get("/debug/biometrics/")
        content = response.content.decode()
        assert SN in content
        devices = list(response.context["devices"])
        assert [device.serial_number for device in devices] == [SN]
        assert devices[0].today_request_count == 1

    def test_punch_section_renders_raw_rows_newest_first(self) -> None:
        """Raw punch rows appear with device serial and table name."""
        response = self.client.get("/debug/biometrics/")
        content = response.content.decode()
        assert "ATTLOG" in content
        assert "2026-10-20 08:15:00" in content
        punches = list(response.context["punches"])
        assert punches[0].pk == self.punch.pk

    def test_orphan_punches_flagged_red(self) -> None:
        """Orphan punches show an 'orphan' badge; resolved rows show none."""
        self.punch.is_orphan = True
        self.punch.save(update_fields=["is_orphan"])
        response = self.client.get("/debug/biometrics/")
        content = response.content.decode()
        assert "orphan" in content
        # Only the flagged row carries the badge — a clean punch shows the
        # muted dash instead (one badge per orphan in the punches section).
        self.punch.is_orphan = False
        self.punch.save(update_fields=["is_orphan"])
        response = self.client.get("/debug/biometrics/")
        punches_section = response.content.decode().split("Raw punch lines")[1].split("ADMS requests")[0]
        assert "orphan" not in punches_section

    def test_request_section_marks_registered_and_unknown(self) -> None:
        """Registered SNs are labelled; unknown SNs flagged as 403."""
        response = self.client.get("/debug/biometrics/")
        content = response.content.decode()
        assert "/iclock/cdata" in content
        assert "NOT-REGISTERED" in content
        assert "unknown" in content
        assert "registered" in content
        rows = list(response.context["requests"])
        assert len(rows) == 2
        assert rows[0].pk == self.unknown_log.pk  # newest first
        assert rows[1].pk == self.registered_log.pk

    def test_raw_device_input_is_html_escaped(self) -> None:
        """Device-controlled raw lines can never inject markup."""
        PunchLogRaw.objects.create(
            tenant=self.tenant,
            device=self.device,
            table_name="UNKNOWN",
            raw_line='<script>alert("pwned")</script>',
        )
        response = self.client.get("/debug/biometrics/")
        content = response.content.decode()
        assert '<script>alert("pwned")</script>' not in content
        assert "&lt;script&gt;" in content

    def test_raw_line_truncated_to_200_chars(self) -> None:
        """Oversized raw lines render truncated with an ellipsis."""
        tail = "X" * 60
        PunchLogRaw.objects.create(
            tenant=self.tenant,
            device=self.device,
            table_name="UNKNOWN",
            raw_line="A" * 250 + tail,
        )
        response = self.client.get("/debug/biometrics/")
        content = response.content.decode()
        assert tail not in content
        assert "…" in content

    def test_rows_capped_at_50(self) -> None:
        """Only the newest 50 rows are rendered per section."""
        for _ in range(55):
            PunchLogRaw.objects.create(
                tenant=self.tenant,
                device=self.device,
                table_name="ATTLOG",
                raw_line="row",
            )
        response = self.client.get("/debug/biometrics/")
        assert len(response.context["punches"]) == 50

    def test_meta_refresh_present(self) -> None:
        """The page auto-refreshes every 10 seconds via meta refresh."""
        response = self.client.get("/debug/biometrics/")
        assert 'http-equiv="refresh" content="10"' in response.content.decode()

    def test_sn_filter_narrows_all_sections(self) -> None:
        """?sn=<serial> filters devices, punches, and requests alike."""
        self._second_device_traffic()
        response = self.client.get(f"/debug/biometrics/?sn={SN_OTHER}")
        assert response.status_code == 200
        assert [device.serial_number for device in response.context["devices"]] == [SN_OTHER]
        punches = list(response.context["punches"])
        assert len(punches) == 1
        assert punches[0].device.serial_number == SN_OTHER
        requests = list(response.context["requests"])
        assert len(requests) == 1
        assert requests[0].sn == SN_OTHER
        content = response.content.decode()
        assert "2026-10-20 08:15:00" not in content  # first device's punch

    def test_unknown_sn_filter_yields_empty_sections(self) -> None:
        """A serial with no rows renders the empty-state messages."""
        response = self.client.get("/debug/biometrics/?sn=NO-SUCH-SN")
        assert response.status_code == 200
        assert list(response.context["punches"]) == []
        assert list(response.context["requests"]) == []


class BiometricsDebugAdminTest(BiometricsDebugDashboardTestBase):
    """The three models are visible in Django admin."""

    def setUp(self) -> None:
        """Sign in a staff superuser for admin access."""
        super().setUp()
        self.superuser = User.objects.create_user(
            email="admin@debug.test",
            password="testpass",
            first_name="Admin",
            last_name="Root",
            is_staff=True,
            is_superuser=True,
            tenant=self.tenant,
        )
        self.client.force_login(self.superuser)

    def test_device_changelist_renders(self) -> None:
        """BiometricDevice is registered with a working changelist."""
        response = self.client.get("/admin/access/biometricdevice/")
        assert response.status_code == 200
        assert SN.encode() in response.content

    def test_punchlograw_changelist_is_read_only(self) -> None:
        """PunchLogRaw changelist renders with no add button."""
        response = self.client.get("/admin/access/punchlograw/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "ATTLOG" in content
        assert "Add punch log raw" not in content

    def test_admsrequestlog_changelist_is_read_only(self) -> None:
        """AdmsRequestLog changelist renders with no add button."""
        response = self.client.get("/admin/access/admsrequestlog/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "/iclock/cdata" in content
        assert "Add adms request log" not in content
