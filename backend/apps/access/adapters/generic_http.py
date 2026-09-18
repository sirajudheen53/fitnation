"""Generic HTTP/MQTT bridge adapter (Sprint 8, issue #27)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from apps.access.adapters.base import AdapterError, BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class GenericHTTPAdapter(BiometricAdapter):
    """Generic adapter for devices behind an HTTP bridge/agent.

    The gym's edge agent (bridge) exposes a simple HTTP API that
    translates our calls into device-specific protocols.
    """

    vendor_label = "Generic"
    protocol = "generic_http"

    def _url(self, device: BiometricDevice, path: str) -> str:
        return f"{device.api_endpoint or ''}{path}"

    def _headers(self, device: BiometricDevice) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {device.api_key or ''}",
        }

    def sync_allow_list(
        self,
        device: BiometricDevice,
        credentials: Any,
    ) -> dict:
        """Push the allow-list to the bridge."""
        endpoint = device.api_endpoint
        if not endpoint:
            raise AdapterError("Device has no API endpoint configured.")

        payload = [
            {
                "user_id": cred.device_user_id,
                "name": cred.customer.name,
                "credential_type": cred.credential_type,
            }
            for cred in credentials
        ]
        try:
            resp = requests.post(
                self._url(device, "/v1/access/allow-list"),
                json={"users": payload},
                headers=self._headers(device),
                timeout=15,
            )
            resp.raise_for_status()
            return {
                "ok": True,
                "pushed": len(payload),
                "detail": f"Bridge accepted {len(payload)} users.",
                "protocol": self.protocol,
            }
        except requests.exceptions.RequestException as exc:
            raise AdapterError(f"Bridge sync failed: {exc}") from exc

    def fetch_events(
        self,
        device: BiometricDevice,
        since: datetime | None = None,
    ) -> list[dict]:
        """Pull events from the bridge."""
        params: dict[str, str] = {"limit": "100"}
        if since is not None:
            params["since"] = since.isoformat()
        try:
            resp = requests.get(
                self._url(device, "/v1/access/events"),
                params=params,
                headers=self._headers(device),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("events", [])
        except requests.exceptions.RequestException:
            pass
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Ping the bridge health endpoint."""
        endpoint = device.api_endpoint
        if not endpoint:
            return {
                "online": False,
                "detail": "No API endpoint configured on the device.",
                "protocol": self.protocol,
            }
        try:
            resp = requests.get(
                self._url(device, "/health"),
                headers=self._headers(device),
                timeout=8,
            )
            online = resp.status_code == 200
            return {
                "online": online,
                "detail": f"Bridge {'reachable' if online else f'HTTP {resp.status_code}'}.",
                "protocol": self.protocol,
            }
        except requests.exceptions.RequestException as exc:
            return {"online": False, "detail": f"Bridge unreachable: {exc}", "protocol": self.protocol}
