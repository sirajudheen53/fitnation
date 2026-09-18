"""Access app tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from django.utils.timezone import localdate
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

import requests

from apps.access.adapters.base import (
    AdapterError,
    AdapterNotRegisteredError,
    BiometricAdapter,
)
from apps.access.adapters.generic_http import GenericHTTPAdapter
from apps.access.adapters.registry import (
    get_adapter,
    get_adapter_class,
    register_adapter,
    registered_vendors,
)
from apps.access.models import (
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
    Vendor,
)
from apps.access.selectors import (
    get_customer_access_state,
    get_device_allow_list,
)
from apps.access.services import sync_customer_devices, sync_device
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.memberships.models import Membership, MembershipPlan
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.models import User
from apps.users.services import create_owner_user, issue_token


def _mock_response(status_code: int = 200, json_data: dict | list | None = None) -> mock.Mock:
    """Build a fake ``requests.Response`` for the mocked HTTP layer."""
    response = mock.Mock()
    response.status_code = status_code
    response.json.return_value = {} if json_data is None else json_data
    return response


class RecordingAdapter(BiometricAdapter):
    """In-memory fake adapter that records calls on the class."""

    calls: list = []
    error: Exception | None = None
    events: list = []

    @classmethod
    def reset(cls) -> None:
        """Clear recorded calls and canned results."""
        cls.calls = []
        cls.error = None
        cls.events = []

    def sync_allow_list(self, device, credentials) -> dict:
        """Record the pushed credential ids, or raise the canned error."""
        if type(self).error is not None:
            raise type(self).error
        credential_ids = [credential.pk for credential in credentials]
        type(self).calls.append({"op": "sync", "device": device.pk, "credentials": credential_ids})
        return {"ok": True, "pushed": len(credential_ids), "detail": f"Pushed {len(credential_ids)}."}

    def fetch_events(self, device, since=None) -> list:
        """Return the canned event list, or raise the canned error."""
        if type(self).error is not None:
            raise type(self).error
        type(self).calls.append({"op": "fetch", "device": device.pk, "since": since})
        return list(type(self).events)

    def test_connection(self, device) -> dict:
        """Report the canned reachability."""
        return {"online": type(self).error is None, "detail": "recording adapter"}


class AccessTestBase(TestCase):
    """Shared fixture for access app tests."""

    def setUp(self) -> None:
        """Set up test data with proper user FK for customer."""
        self.tenant = Tenant.objects.create(name="Test Gym", contact_email="gym@test.com")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch", branch_type="gym")
        self.user = User.objects.create_user(
            email="owner@test.com",
            password="test123",
            first_name="Gym",
            last_name="Owner",
            role="owner",
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=self.user,
            name="John Doe",
            phone="+919999999999",
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="hikvision",
            model="DS-K1T321MFWX",
            serial_number="SN123456",
            name="Main Entrance",
        )


class DeviceRegistryTest(AccessTestBase):
    """Test biometric device registration and scoping."""

    def test_device_creation(self) -> None:
        """Create a biometric device."""
        device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="hikvision",
            model="DS-K1T321MFWX",
            serial_number="SN789",
            name="Second Entrance",
        )
        assert device.pk is not None
        assert device.tenant == self.tenant

    def test_device_unique_serial_per_branch(self) -> None:
        """Enforce unique serial per branch."""
        with self.assertRaises(Exception):
            BiometricDevice.objects.create(
                tenant=self.tenant,
                branch=self.branch,
                vendor="zkteco",
                model="MB10",
                serial_number="SN123456",
                name="Second Device",
            )


class AccessOverrideTest(AccessTestBase):
    """Test access override logic."""

    def test_owner_override_grants_access(self) -> None:
        """Owner override can grant access to members."""
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            allow_access=True,
            reason="grace_period",
            created_by=self.user,
        )
        result = get_customer_access_state(customer=self.customer, device=self.device)
        assert result["allowed"] is True
        assert result["source"] == "override"

    def test_owner_override_denies_access(self) -> None:
        """Owner override can revoke access from members."""
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            allow_access=False,
            reason="violation",
            created_by=self.user,
        )
        result = get_customer_access_state(customer=self.customer, device=self.device)
        assert result["allowed"] is False
        assert result["source"] == "override"

    def test_expired_override_ignored(self) -> None:
        """Expired overrides are not applied."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            allow_access=True,
            reason="grace_period",
            expires_at=past,
        )
        result = get_customer_access_state(customer=self.customer, device=self.device)
        # Should fall through to plan check
        assert result["source"] != "override"


class AccessLogTest(AccessTestBase):
    """Test access event logging."""

    def test_record_entry_event(self) -> None:
        """Log an entry event."""
        log = AccessLog.objects.create(
            tenant=self.tenant,
            device=self.device,
            customer=self.customer,
            device_user_id="D001",
            credential_type="fingerprint",
            event_type="entry",
            event_timestamp=datetime.now(timezone.utc),
        )
        assert log.pk is not None
        assert log.tenant == self.tenant


class AdapterRegistryTest(AccessTestBase):
    """Test vendor->adapter registry resolution."""

    def test_generic_vendor_resolves_to_http_adapter(self) -> None:
        """The 'generic' vendor maps to the generic HTTP bridge adapter."""
        assert get_adapter_class(Vendor.GENERIC) is GenericHTTPAdapter

    def test_stub_vendors_are_registered(self) -> None:
        """Vendors without native adapters resolve to stub adapter classes."""
        for vendor in ("hikvision", "zkteco", "essl", "matrix", "supervision"):
            assert issubclass(get_adapter_class(vendor), BiometricAdapter)

    def test_registry_covers_all_vendor_choices(self) -> None:
        """Every Vendor model choice has a registered adapter."""
        assert set(registered_vendors()) == set(Vendor.values)

    def test_unknown_vendor_raises(self) -> None:
        """Unregistered vendors raise AdapterNotRegisteredError."""
        with self.assertRaises(AdapterNotRegisteredError):
            get_adapter_class("nope-vendor")

    def test_get_adapter_builds_instance_for_device(self) -> None:
        """get_adapter returns an adapter instance for the device's vendor."""
        adapter = get_adapter(self.device)
        assert isinstance(adapter, BiometricAdapter)
        # Base fixture device is hikvision — a stub that reports offline.
        assert adapter.test_connection(self.device)["online"] is False


class GenericHTTPAdapterTest(AccessTestBase):
    """Test the generic HTTP bridge adapter against a mocked HTTP layer."""

    def setUp(self) -> None:
        """Create a generic bridge device with enrolled credentials."""
        super().setUp()
        self.http_device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="generic",
            model="HTTP Bridge v1",
            serial_number="SN-HTTP-1",
            name="Gate Bridge",
            connection_type="agent",
            api_endpoint="https://bridge.example.com",
            api_key="bridge-secret",
        )
        self.credentials = [
            BiometricCredential.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                device=self.http_device,
                credential_type="fingerprint",
                device_user_id="D001",
            ),
            BiometricCredential.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                device=self.http_device,
                credential_type="card",
                device_user_id="D002",
            ),
        ]

    def test_allow_list_push_posts_credentials(self) -> None:
        """Allow-list push POSTs the credential list with bearer auth."""
        with mock.patch("apps.access.adapters.generic_http.requests.post") as post:
            post.return_value = _mock_response(200, {"ok": True})
            result = GenericHTTPAdapter().sync_allow_list(self.http_device, self.credentials)

        assert result["ok"] is True
        assert result["pushed"] == 2
        args, kwargs = post.call_args
        assert args[0] == "https://bridge.example.com/allowlist"
        assert kwargs["headers"]["Authorization"] == "Bearer bridge-secret"
        assert [c["device_user_id"] for c in kwargs["json"]["credentials"]] == ["D001", "D002"]
        self.http_device.refresh_from_db()
        assert self.http_device.last_sync_at is not None

    def test_allow_list_push_unauthorized_raises(self) -> None:
        """A 401 from the bridge raises AdapterError."""
        with mock.patch("apps.access.adapters.generic_http.requests.post") as post:
            post.return_value = _mock_response(401)
            with self.assertRaises(AdapterError):
                GenericHTTPAdapter().sync_allow_list(self.http_device, self.credentials)

    def test_allow_list_push_missing_endpoint_raises(self) -> None:
        """A device without api_endpoint cannot push its allow-list."""
        self.http_device.api_endpoint = ""
        with mock.patch("apps.access.adapters.generic_http.requests.post") as post:
            with self.assertRaises(AdapterError):
                GenericHTTPAdapter().sync_allow_list(self.http_device, self.credentials)
        post.assert_not_called()

    def test_fetch_events_returns_event_list(self) -> None:
        """Event fetch GETs /events and returns the events payload."""
        events = [{"device_user_id": "D001", "event_type": "entry"}]
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            get.return_value = _mock_response(200, {"events": events})
            result = GenericHTTPAdapter().fetch_events(self.http_device)

        assert result == events
        assert get.call_args.args[0] == "https://bridge.example.com/events"
        assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer bridge-secret"

    def test_fetch_events_passes_since_param(self) -> None:
        """The since timestamp is sent as an ISO-8601 query param."""
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            get.return_value = _mock_response(200, [])
            GenericHTTPAdapter().fetch_events(self.http_device, since=since)

        assert get.call_args.kwargs["params"] == {"since": since.isoformat()}

    def test_fetch_events_server_error_raises(self) -> None:
        """A 5xx from the bridge raises AdapterError."""
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            get.return_value = _mock_response(500)
            with self.assertRaises(AdapterError):
                GenericHTTPAdapter().fetch_events(self.http_device)

    def test_fetch_events_unauthorized_raises(self) -> None:
        """A 401 from the bridge raises AdapterError."""
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            get.return_value = _mock_response(401)
            with self.assertRaises(AdapterError):
                GenericHTTPAdapter().fetch_events(self.http_device)

    def test_connection_success_marks_device_online(self) -> None:
        """A 200 status response marks the device online and stamps last_seen_at."""
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            get.return_value = _mock_response(200, {"status": "ok"})
            result = GenericHTTPAdapter().test_connection(self.http_device)

        assert result["online"] is True
        assert get.call_args.args[0] == "https://bridge.example.com/status"
        self.http_device.refresh_from_db()
        assert self.http_device.last_seen_at is not None

    def test_connection_unauthorized_reports_offline(self) -> None:
        """A 401 from the bridge reports offline with an auth failure detail."""
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            get.return_value = _mock_response(401)
            result = GenericHTTPAdapter().test_connection(self.http_device)

        assert result["online"] is False
        assert "401" in result["detail"]
        self.http_device.refresh_from_db()
        assert self.http_device.last_seen_at is None

    def test_connection_network_error_reports_offline(self) -> None:
        """Transport failures report offline instead of raising."""
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            get.side_effect = requests.exceptions.ConnectTimeout("timed out")
            result = GenericHTTPAdapter().test_connection(self.http_device)

        assert result["online"] is False
        assert "timed out" in result["detail"]
        self.http_device.refresh_from_db()
        assert self.http_device.last_seen_at is None

    def test_connection_without_endpoint_reports_offline(self) -> None:
        """Devices without api_endpoint report offline without any HTTP call."""
        self.http_device.api_endpoint = ""
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            result = GenericHTTPAdapter().test_connection(self.http_device)

        assert result["online"] is False
        get.assert_not_called()


class DeviceTestConnectionAPITests(APITestCase):
    """Integration tests for POST /api/v1/access/devices/{id}/test-connection/."""

    def setUp(self) -> None:
        """Create tenant, owner token, branch, and a generic bridge device."""
        self.tenant = provision_tenant(name="Bridge Gym", contact_email="owner@bridge.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@bridge.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Bridge Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant, name="Main Branch", branch_type="gym"
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="generic",
            model="HTTP Bridge v1",
            serial_number="SN-API-1",
            name="API Gate",
            connection_type="agent",
            api_endpoint="https://bridge.example.com",
            api_key="bridge-secret",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.url = f"/api/v1/access/devices/{self.device.pk}/test-connection/"

    def test_test_connection_online_persists_timestamps(self) -> None:
        """A successful test returns online=true and stamps sync timestamps."""
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            get.return_value = _mock_response(200, {"status": "ok"})
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["online"])
        self.assertIn("detail", response.data)
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_seen_at)
        self.assertIsNotNone(self.device.last_sync_at)

    def test_test_connection_offline_does_not_persist_timestamps(self) -> None:
        """A failed test returns online=false and leaves timestamps untouched."""
        with mock.patch("apps.access.adapters.generic_http.requests.get") as get:
            get.side_effect = requests.exceptions.ConnectionError("no route to host")
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["online"])
        self.assertIn("no route to host", response.data["detail"])
        self.device.refresh_from_db()
        self.assertIsNone(self.device.last_seen_at)
        self.assertIsNone(self.device.last_sync_at)

    def test_test_connection_tenant_isolation(self) -> None:
        """Devices belonging to another tenant are not visible (404)."""
        other_tenant = provision_tenant(
            name="Other Gym", contact_email="owner@other.test"
        )
        other_owner = create_owner_user(
            tenant=other_tenant,
            email="owner@other.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        other_token = issue_token(other_owner, other_tenant)
        other_client = self.client_class()
        other_client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")

        response = other_client.post(self.url)

        self.assertEqual(response.status_code, 404)
        self.device.refresh_from_db()
        self.assertIsNone(self.device.last_seen_at)

    def test_test_connection_requires_edit_permission(self) -> None:
        """Trainers (no customers.edit_customer) are forbidden from testing."""
        trainer = User.objects.create_user(
            email="trainer@bridge.test",
            password="test123",
            first_name="Train",
            last_name="Er",
            role="trainer",
            tenant=self.tenant,
        )
        trainer_token = issue_token(trainer, self.tenant)
        trainer_client = self.client_class()
        trainer_client.credentials(HTTP_AUTHORIZATION=f"Token {trainer_token.key}")

        response = trainer_client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.device.refresh_from_db()
        self.assertIsNone(self.device.last_seen_at)


class AllowListTestBase(AccessTestBase):
    """Fixture base with a generic device, plan, and member helpers."""

    def setUp(self) -> None:
        """Add a generic bridge device and a membership plan."""
        super().setUp()
        self.http_device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="generic",
            model="HTTP Bridge v1",
            serial_number="SN-ALLOW-1",
            name="Allow List Gate",
            connection_type="agent",
            api_endpoint="https://bridge.example.com",
            api_key="bridge-secret",
        )
        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Gold Monthly",
            price=Decimal("1000.00"),
            duration_days=30,
        )

    def _make_customer(self, username: str, phone: str) -> Customer:
        """Create a user + customer pair with unique contact details."""
        user = User.objects.create_user(
            email=f"{username}@test.com",
            password="test123",
            first_name=username.title(),
            last_name="Member",
            role="customer",
            tenant=self.tenant,
        )
        return Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name=username.title(),
            email=f"{username}@test.com",
            phone=phone,
        )

    def _make_membership(
        self,
        customer: Customer,
        *,
        end: date | None = None,
    ) -> Membership:
        """Create a membership (active by default, expired when end is past)."""
        today = localdate()
        return Membership.objects.create(
            tenant=self.tenant,
            customer=customer,
            plan=self.plan,
            start_date=today - timedelta(days=5),
            end_date=end or today + timedelta(days=25),
        )


class AllowListRuleTest(AllowListTestBase):
    """Test allow-list resolution against the access rule engine."""

    def setUp(self) -> None:
        """Enroll an active member on the generic device."""
        super().setUp()
        self.member = self._make_customer("member", "+918000000001")
        self._make_membership(self.member)
        self.member_credential = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.member,
            device=self.http_device,
            credential_type="fingerprint",
            device_user_id="M001",
        )

    def _allow_list_ids(self) -> list:
        """Return device_user_ids currently on the resolved allow-list."""
        return [
            credential.device_user_id
            for credential in get_device_allow_list(device=self.http_device)
        ]

    def test_active_plan_credential_included(self) -> None:
        """A customer with an active membership stays on the allow-list."""
        assert "M001" in self._allow_list_ids()

    def test_customer_without_membership_excluded(self) -> None:
        """Customers without any membership are not on the allow-list."""
        assert self._allow_list_ids() == ["M001"]

    def test_expired_plan_excluded(self) -> None:
        """An expired membership removes the customer from the allow-list."""
        self._make_membership(
            self._make_customer("expired", "+918000000002"),
            end=localdate() - timedelta(days=1),
        )
        BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=Customer.objects.get(user__email="expired@test.com"),
            device=self.http_device,
            credential_type="card",
            device_user_id="E001",
        )
        assert "E001" not in self._allow_list_ids()

    def test_allow_override_keeps_expired_plan_on_allow_list(self) -> None:
        """An ALLOW override keeps access even after plan expiry."""
        expired_member = self._make_customer("vip", "+918000000003")
        self._make_membership(expired_member, end=localdate() - timedelta(days=1))
        BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=expired_member,
            device=self.http_device,
            credential_type="face",
            device_user_id="V001",
        )
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=expired_member,
            device=self.http_device,
            allow_access=True,
            reason="vip",
        )
        assert "V001" in self._allow_list_ids()

    def test_deny_override_excludes_active_plan(self) -> None:
        """A DENY override removes an otherwise-active member."""
        AccessOverride.objects.create(
            tenant=self.tenant,
            customer=self.member,
            device=self.http_device,
            allow_access=False,
            reason="violation",
        )
        assert "M001" not in self._allow_list_ids()

    def test_cancelled_membership_excluded(self) -> None:
        """A cancelled membership removes the customer from the allow-list."""
        self.member.memberships.first().delete()
        membership = self._make_membership(self.member)
        membership.status = "cancelled"
        membership.save(update_fields=["status"])
        assert "M001" not in self._allow_list_ids()

    def test_inactive_credential_excluded(self) -> None:
        """Deactivated credentials are never pushed."""
        self.member_credential.is_active = False
        self.member_credential.save(update_fields=["is_active"])
        assert self._allow_list_ids() == []


class SyncServiceTest(AllowListTestBase):
    """Test sync_device / sync_customer_devices with a recording adapter."""

    def setUp(self) -> None:
        """Register the recording adapter for the 'generic' vendor."""
        super().setUp()
        original = get_adapter_class("generic")
        register_adapter("generic", RecordingAdapter)
        self.addCleanup(register_adapter, "generic", original)
        RecordingAdapter.reset()
        self.addCleanup(RecordingAdapter.reset)
        self.member = self._make_customer("member", "+918000000001")
        self._make_membership(self.member)
        self.member_credential = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.member,
            device=self.http_device,
            credential_type="fingerprint",
            device_user_id="M001",
        )

    def test_sync_device_pushes_resolved_allow_list(self) -> None:
        """sync_device pushes exactly the rule-engine allow-list."""
        result = sync_device(self.http_device)
        assert result["synced"] is True
        assert result["pushed"] == 1
        assert RecordingAdapter.calls == [
            {
                "op": "sync",
                "device": self.http_device.pk,
                "credentials": [self.member_credential.pk],
            }
        ]

    def test_sync_device_stamps_last_sync_at(self) -> None:
        """A successful sync stamps device.last_sync_at."""
        assert self.http_device.last_sync_at is None
        sync_device(self.http_device)
        self.http_device.refresh_from_db()
        assert self.http_device.last_sync_at is not None

    def test_sync_device_offline_returns_not_synced(self) -> None:
        """An unreachable device is reported, not raised."""
        RecordingAdapter.error = AdapterError("bridge down")
        result = sync_device(self.http_device)
        assert result["synced"] is False
        assert "bridge down" in result["detail"]
        assert "pushed" not in result
        self.http_device.refresh_from_db()
        assert self.http_device.last_sync_at is None

    def test_sync_device_stub_vendor_reports_unimplemented(self) -> None:
        """Vendors without native adapters report a clear failure."""
        result = sync_device(self.device)  # hikvision stub from AccessTestBase
        assert result["synced"] is False
        assert "not implemented" in result["detail"].lower()

    def test_sync_customer_devices_targets_customer_devices(self) -> None:
        """Only devices with the customer's credentials are synced."""
        other_device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="generic",
            model="HTTP Bridge v1",
            serial_number="SN-ALLOW-2",
            name="Other Gate",
            connection_type="agent",
            api_endpoint="https://bridge2.example.com",
            api_key="bridge-secret",
        )
        other_member = self._make_customer("othermember", "+918000000004")
        self._make_membership(other_member)
        BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=other_member,
            device=other_device,
            credential_type="card",
            device_user_id="O001",
        )

        results = sync_customer_devices(self.member)

        assert [entry["device_id"] for entry in results] == [self.http_device.pk]
        assert all(entry["synced"] for entry in results)

    def test_sync_devices_command_syncs_active_devices(self) -> None:
        """The management command syncs active devices and skips inactive ones."""
        BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="generic",
            model="HTTP Bridge v1",
            serial_number="SN-ALLOW-INACTIVE",
            name="Dead Gate",
            connection_type="agent",
            api_endpoint="https://dead.example.com",
            api_key="bridge-secret",
            is_active=False,
        )
        # The base fixture also carries an active Hikvision device whose stub
        # adapter is intentionally unimplemented — take it out of this count.
        BiometricDevice.objects.filter(vendor="hikvision").update(is_active=False)
        stdout = StringIO()
        call_command("sync_devices", stdout=stdout)
        output = stdout.getvalue()
        assert "Synced 1 device(s); 0 failed." in output
        assert len([c for c in RecordingAdapter.calls if c["op"] == "sync"]) == 1


class MembershipSyncTriggerTest(APITestCase):
    """Test that membership changes propagate to device allow-list syncs."""

    def setUp(self) -> None:
        """Create tenant, owner token, member, device, and credential."""
        self.tenant = provision_tenant(name="Trigger Gym", contact_email="owner@trigger.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@trigger.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Trigger Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant, name="Main Branch", branch_type="gym"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Silver Monthly",
            price=Decimal("500.00"),
            duration_days=30,
        )
        user = User.objects.create_user(
            email="member@trigger.test",
            password="test123",
            first_name="Carl",
            last_name="Customer",
            role="customer",
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name="Carl Customer",
            email="member@trigger.test",
            phone="+917000000001",
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="generic",
            model="HTTP Bridge v1",
            serial_number="SN-TRIG-1",
            name="Trigger Door",
            connection_type="agent",
            api_endpoint="https://bridge.example.com",
            api_key="bridge-secret",
        )
        BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="T001",
        )
        today = localdate()
        self.membership_payload = {
            "customer": self.customer.pk,
            "plan": self.plan.pk,
            "start_date": str(today - timedelta(days=5)),
            "end_date": str(today + timedelta(days=25)),
        }

    def _create_membership(self) -> Membership:
        """Create an active membership directly via the ORM."""
        today = localdate()
        return Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=self.plan,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
        )

    @mock.patch("apps.memberships.views.sync_customer_devices")
    def test_create_membership_triggers_sync(self, sync_mock: mock.MagicMock) -> None:
        """Creating a membership syncs the customer's devices."""
        response = self.client.post(
            "/api/v1/memberships/memberships/", self.membership_payload, format="json"
        )
        self.assertEqual(response.status_code, 201)
        sync_mock.assert_called_once_with(self.customer)

    @mock.patch("apps.memberships.views.sync_customer_devices")
    def test_renew_membership_triggers_sync(self, sync_mock: mock.MagicMock) -> None:
        """Renewing a membership syncs the customer's devices."""
        membership = self._create_membership()
        response = self.client.post(
            f"/api/v1/memberships/memberships/{membership.pk}/renewal/",
            {"days": 30},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        sync_mock.assert_called_once_with(self.customer)

    @mock.patch("apps.memberships.views.sync_customer_devices")
    def test_cancel_membership_triggers_sync(self, sync_mock: mock.MagicMock) -> None:
        """Cancelling a membership syncs the customer's devices."""
        membership = self._create_membership()
        response = self.client.post(
            f"/api/v1/memberships/memberships/{membership.pk}/cancel/", format="json"
        )
        self.assertEqual(response.status_code, 200)
        sync_mock.assert_called_once_with(self.customer)

    @mock.patch("apps.memberships.views.sync_customer_devices")
    def test_update_membership_triggers_sync(self, sync_mock: mock.MagicMock) -> None:
        """Editing a membership (e.g. end_date) syncs the customer's devices."""
        membership = self._create_membership()
        response = self.client.patch(
            f"/api/v1/memberships/memberships/{membership.pk}/",
            {"end_date": str(localdate() + timedelta(days=60))},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        sync_mock.assert_called_once_with(self.customer)

    def test_cancel_propagates_to_allow_list(self) -> None:
        """End-to-end: cancelling removes the credential from the allow-list."""
        membership = self._create_membership()
        allow_list = get_device_allow_list(device=self.device)
        assert [credential.device_user_id for credential in allow_list] == ["T001"]

        response = self.client.post(
            f"/api/v1/memberships/memberships/{membership.pk}/cancel/", format="json"
        )
        self.assertEqual(response.status_code, 200)
        assert get_device_allow_list(device=self.device) == []


class DeviceSyncEnrollFetchAPITests(APITestCase):
    """Integration tests for the sync / enroll / fetch-events endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner token, member with plan, device, credential."""
        self.tenant = provision_tenant(name="Sync Gym", contact_email="owner@sync.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@sync.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Sync Owner",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.branch = Branch.objects.create(
            tenant=self.tenant, name="Main Branch", branch_type="gym"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        original = get_adapter_class("generic")
        register_adapter("generic", RecordingAdapter)
        self.addCleanup(register_adapter, "generic", original)
        RecordingAdapter.reset()
        self.addCleanup(RecordingAdapter.reset)

        plan = MembershipPlan.objects.create(
            tenant=self.tenant,
            name="Bronze Monthly",
            price=Decimal("750.00"),
            duration_days=30,
        )
        user = User.objects.create_user(
            email="member@sync.test",
            password="test123",
            first_name="Mia",
            last_name="Member",
            role="customer",
            tenant=self.tenant,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            user=user,
            name="Mia Member",
            email="member@sync.test",
            phone="+916000000001",
        )
        today = localdate()
        Membership.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            plan=plan,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
        )
        self.device = BiometricDevice.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            vendor="generic",
            model="HTTP Bridge v1",
            serial_number="SN-SYNC-1",
            name="Sync Gate",
            connection_type="agent",
            api_endpoint="https://bridge.example.com",
            api_key="bridge-secret",
        )
        self.credential = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="S001",
        )
        self.device_url = f"/api/v1/access/devices/{self.device.pk}"
        self.enroll_url = "/api/v1/access/devices/enroll/"

    def _make_trainer_client(self):
        """Create a trainer token client (customers.view_customer only)."""
        trainer = User.objects.create_user(
            email="trainer@sync.test",
            password="test123",
            first_name="Tina",
            last_name="Trainer",
            role="trainer",
            tenant=self.tenant,
        )
        trainer_token = issue_token(trainer, self.tenant)
        trainer_client = self.client_class()
        trainer_client.credentials(HTTP_AUTHORIZATION=f"Token {trainer_token.key}")
        return trainer_client

    def test_sync_action_pushes_allow_list(self) -> None:
        """POST sync pushes the allow-list and stamps last_sync_at."""
        response = self.client.post(f"{self.device_url}/sync/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["synced"])
        self.assertEqual(response.data["pushed"], 1)
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_sync_at)
        assert RecordingAdapter.calls[0]["credentials"] == [self.credential.pk]

    def test_sync_action_offline_device(self) -> None:
        """An offline device returns synced=false with the failure detail."""
        RecordingAdapter.error = AdapterError("bridge unreachable")
        response = self.client.post(f"{self.device_url}/sync/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["synced"])
        self.assertIn("bridge unreachable", response.data["detail"])
        self.device.refresh_from_db()
        self.assertIsNone(self.device.last_sync_at)

    def test_enroll_action_creates_credential_and_syncs(self) -> None:
        """POST enroll creates the credential then syncs that device."""
        response = self.client.post(
            self.enroll_url,
            {
                "customer": self.customer.pk,
                "device": self.device.pk,
                "credential_type": "card",
                "device_user_id": "S002",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["credential"]["device_user_id"], "S002")
        self.assertTrue(response.data["sync"]["synced"])
        assert BiometricCredential.objects.filter(
            device=self.device, device_user_id="S002"
        ).exists()
        sync_calls = [c for c in RecordingAdapter.calls if c["op"] == "sync"]
        assert len(sync_calls) == 1
        assert set(sync_calls[0]["credentials"]) == {self.credential.pk, response.data["credential"]["id"]}

    def test_enroll_action_cross_tenant_rejected(self) -> None:
        """Enrollment referencing another tenant's device is rejected."""
        other_tenant = provision_tenant(name="Rival Gym", contact_email="owner@rival.test")
        other_device = BiometricDevice.objects.create(
            tenant=other_tenant,
            branch=Branch.objects.create(tenant=other_tenant, name="Rival Branch", branch_type="gym"),
            vendor="generic",
            model="HTTP Bridge v1",
            serial_number="SN-RIVAL-1",
            name="Rival Gate",
            connection_type="agent",
            api_endpoint="https://rival.example.com",
            api_key="rival-secret",
        )
        response = self.client.post(
            self.enroll_url,
            {
                "customer": self.customer.pk,
                "device": other_device.pk,
                "credential_type": "card",
                "device_user_id": "X001",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        assert not BiometricCredential.objects.filter(device_user_id="X001").exists()

    def test_fetch_events_records_access_logs(self) -> None:
        """POST fetch-events records each fetched event as an AccessLog."""
        now_iso = datetime.now(timezone.utc).isoformat()
        RecordingAdapter.events = [
            {
                "device_user_id": "S001",
                "credential_type": "fingerprint",
                "event_type": "entry",
                "timestamp": now_iso,
            },
            {
                "device_user_id": "STRANGER",
                "event_type": "denied",
                "timestamp": now_iso,
            },
        ]
        response = self.client.post(f"{self.device_url}/fetch-events/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["fetched"])
        self.assertEqual(response.data["recorded"], 2)

        logs = AccessLog.objects.filter(device=self.device).order_by("device_user_id")
        assert [log.device_user_id for log in logs] == ["S001", "STRANGER"]
        assert logs[0].customer == self.customer
        assert logs[1].customer is None
        assert logs[1].event_type == "denied"

    def test_fetch_events_offline_device(self) -> None:
        """An offline device returns fetched=false without recording logs."""
        RecordingAdapter.error = AdapterError("bridge unreachable")
        response = self.client.post(f"{self.device_url}/fetch-events/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["fetched"])
        self.assertEqual(response.data["recorded"], 0)
        assert AccessLog.objects.filter(device=self.device).count() == 0

    def test_fetch_events_rejects_invalid_since(self) -> None:
        """A malformed since param yields a 400."""
        response = self.client.post(f"{self.device_url}/fetch-events/?since=not-a-date")
        self.assertEqual(response.status_code, 400)

    def test_sync_action_tenant_isolation(self) -> None:
        """Devices belonging to another tenant are not syncable (404)."""
        other_tenant = provision_tenant(name="Other Sync Gym", contact_email="owner@othersync.test")
        other_owner = create_owner_user(
            tenant=other_tenant,
            email="owner@othersync.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Sync Owner",
        )
        other_token = issue_token(other_owner, other_tenant)
        other_client = self.client_class()
        other_client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")

        response = other_client.post(f"{self.device_url}/sync/")

        self.assertEqual(response.status_code, 404)
        self.device.refresh_from_db()
        self.assertIsNone(self.device.last_sync_at)

    def test_fetch_events_allowed_for_trainer_but_sync_forbidden(self) -> None:
        """Trainers (view only) may fetch events but cannot force a sync."""
        trainer_client = self._make_trainer_client()

        fetch_response = trainer_client.post(f"{self.device_url}/fetch-events/")
        sync_response = trainer_client.post(f"{self.device_url}/sync/")

        self.assertEqual(fetch_response.status_code, 200)
        self.assertTrue(fetch_response.data["fetched"])
        self.assertEqual(sync_response.status_code, 403)
