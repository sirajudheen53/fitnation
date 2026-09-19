"""Vendor adapter tests (Sprint 9, issues #27-#37).

Covers the vendor-facing adapter layer with mocked HTTP: registry
coverage, ZKTeco ADMS command queueing, connection freshness checks,
and the generic HTTP bridge contract. Complements ``tests.py`` —
does not duplicate its registry/API coverage.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests
from django.utils import timezone

from apps.access.adapters.base import AdapterError, AdapterNotRegisteredError, BiometricAdapter
from apps.access.adapters.generic_http import GenericHTTPAdapter
from apps.access.adapters.registry import get_adapter, get_adapter_class, registered_vendors
from apps.access.adapters.zkteco import ZKTecoADMSAdapter
from apps.access.models import BiometricCredential, DeviceCommandQueue
from apps.access.tests import AccessTestBase


class AdapterRegistryCoverageTest(AccessTestBase):
    """Test registry coverage for every vendor."""

    def test_all_vendors_registered(self) -> None:
        """Every Vendor choice resolves to a concrete adapter class."""
        from apps.access.models import Vendor

        assert set(registered_vendors()) == set(Vendor.values)

    def test_get_adapter_returns_instance(self) -> None:
        """get_adapter builds the right adapter per device vendor."""
        adapter = get_adapter(self.device)
        assert isinstance(adapter, BiometricAdapter)

    def test_unknown_vendor_raises(self) -> None:
        """Unregistered vendors raise AdapterNotRegisteredError."""
        with self.assertRaises(AdapterNotRegisteredError):
            get_adapter_class("nope-vendor")


class ZKTecoADMSAdapterTest(AccessTestBase):
    """Test the ZKTeco/eSSL ADMS adapter logic (command queue)."""

    def _adapter(self) -> ZKTecoADMSAdapter:
        return ZKTecoADMSAdapter()

    def test_sync_allow_list_queues_commands(self) -> None:
        """Allow-list sync creates queued commands, one per credential."""
        cred = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="fingerprint",
            device_user_id="U001",
        )
        result = self._adapter().sync_allow_list(self.device, [cred])

        assert result["ok"] is True
        assert result["pushed"] == 1
        assert DeviceCommandQueue.objects.filter(device=self.device).count() == 1

    def test_pop_pending_commands_formats_adms_line(self) -> None:
        """Pending commands pop as formatted ADMS update lines."""
        DeviceCommandQueue.objects.create(
            tenant=self.tenant,
            device=self.device,
            command="DATA UPDATE USER",
            payload={"pin": "U001", "name": "John Doe", "cardno": ""},
        )
        adapter = self._adapter()
        commands = adapter._pop_pending_commands(self.device)

        assert len(commands) == 1
        assert "PIN=U001" in commands[0]
        assert "Name=John Doe" in commands[0]
        assert DeviceCommandQueue.objects.filter(
            device=self.device, executed_at__isnull=True
        ).count() == 0

    def test_test_connection_never_seen(self) -> None:
        """A device that has never connected reports offline."""
        result = self._adapter().test_connection(self.device)
        assert result["online"] is False

    def test_test_connection_fresh(self) -> None:
        """A recently-seen device reports online."""
        self.device.last_seen_at = timezone.now()
        self.device.save(update_fields=["last_seen_at"])
        result = self._adapter().test_connection(self.device)
        assert result["online"] is True

    def test_test_connection_stale(self) -> None:
        """A device not seen for >10min reports offline (stale)."""
        self.device.last_seen_at = timezone.now() - timedelta(minutes=15)
        self.device.save(update_fields=["last_seen_at"])
        result = self._adapter().test_connection(self.device)
        assert result["online"] is False
        assert "stale" in result["detail"].lower()

    def test_handle_adms_request_touches_last_seen(self) -> None:
        """An ADMS poll updates last_seen_at."""
        adapter = self._adapter()
        assert self.device.last_seen_at is None
        reply = adapter.handle_adms_request({"options": "1"}, self.device)
        assert reply == "OK"
        self.device.refresh_from_db()
        assert self.device.last_seen_at is not None


class GenericHTTPBridgeTest(AccessTestBase):
    """Test the generic HTTP bridge adapter with mocked requests."""

    def _bridge_device(self):
        self.device.connection_type = "agent"
        self.device.api_endpoint = "https://bridge.example.com"
        self.device.api_key = "bridge-secret"
        self.device.save()
        return self.device

    def test_sync_allow_list_success(self) -> None:
        """Bridge accepting the payload reports ok with counts."""
        cred = BiometricCredential.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            device=self.device,
            credential_type="card",
            device_user_id="U002",
        )
        with patch("apps.access.adapters.generic_http.requests.post") as post:
            post.return_value = MagicMock(status_code=200)
            result = GenericHTTPAdapter().sync_allow_list(self._bridge_device(), [cred])

        assert result["ok"] is True
        assert result["pushed"] == 1

    def test_sync_allow_list_no_endpoint_raises(self) -> None:
        """Missing endpoint raises AdapterError."""
        self.device.api_endpoint = ""
        self.device.save()
        with self.assertRaises(AdapterError):
            GenericHTTPAdapter().sync_allow_list(self.device, [])

    def test_fetch_events_parses_bridge_response(self) -> None:
        """Events from the bridge JSON are returned."""
        with patch("apps.access.adapters.generic_http.requests.get") as get:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"events": [{"user_id": "U001"}]}
            get.return_value = resp
            events = GenericHTTPAdapter().fetch_events(self._bridge_device())
        assert events == [{"user_id": "U001"}]

    def test_test_connection_offline_on_transport_error(self) -> None:
        """Connection errors report offline, never raise."""
        self.device.api_endpoint = "https://unreachable.example.com"
        self.device.save()
        with patch(
            "apps.access.adapters.generic_http.requests.get",
            side_effect=requests.exceptions.ConnectionError("boom"),
        ):
            result = GenericHTTPAdapter().test_connection(self.device)
        assert result["online"] is False

    def test_test_connection_online(self) -> None:
        """A 200 status marks the device online."""
        with patch("apps.access.adapters.generic_http.requests.get") as get:
            get.return_value = MagicMock(status_code=200)
            result = GenericHTTPAdapter().test_connection(self._bridge_device())
        assert result["online"] is True


class HikvisionAdapterTest(AccessTestBase):
    """Test the Hikvision ISAPI adapter with mocked HTTP."""

    def test_test_connection_unreachable_reports_offline(self) -> None:
        """Unreachable device reports offline without raising."""
        from apps.access.adapters.hikvision import HikvisionAdapter

        self.device.api_endpoint = "192.0.2.9"  # TEST-NET, unroutable
        self.device.save()
        result = HikvisionAdapter().test_connection(self.device)
        assert result["online"] is False

    def test_sync_requires_endpoint(self) -> None:
        """Sync without an endpoint raises AdapterError."""
        from apps.access.adapters.hikvision import HikvisionAdapter

        self.device.api_endpoint = ""
        self.device.save()
        with self.assertRaises(AdapterError):
            HikvisionAdapter().sync_allow_list(self.device, [])


class RealtimeAdapterTest(AccessTestBase):
    """Test the Realtime HTTP push adapter."""

    def test_sync_requires_endpoint(self) -> None:
        """Agent-mode devices (no endpoint) raise AdapterError."""
        from apps.access.adapters.realtime import RealtimeAdapter

        self.device.api_endpoint = ""
        self.device.save()
        with self.assertRaises(AdapterError):
            RealtimeAdapter().sync_allow_list(self.device, [])


class MantraAdapterTest(AccessTestBase):
    """Test the Mantra HTTP adapter."""

    def test_sync_requires_endpoint(self) -> None:
        """USB/agent-mode devices raise AdapterError on sync."""
        from apps.access.adapters.mantra import MantraAdapter

        self.device.api_endpoint = ""
        self.device.save()
        with self.assertRaises(AdapterError):
            MantraAdapter().sync_allow_list(self.device, [])
