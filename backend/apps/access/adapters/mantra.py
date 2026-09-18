"""Mantra adapter (Sprint 9, issue #36) — network-capable MFS/Bio series."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from apps.access.adapters.base import AdapterError, BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class MantraAdapter(BiometricAdapter):
    """Mantra HTTP adapter for network-capable terminals (USB-only = agent)."""

    vendor_label = "Mantra"
    protocol = "mantra_http"
    PORT = 8080

    def _base(self, device: BiometricDevice) -> str:
        return f"http://{device.api_endpoint or 'localhost'}:{self.PORT}"

    def sync_allow_list(self, device: BiometricDevice, credentials: Any) -> dict:
        """Push users via the Mantra HTTP API."""
        if not device.api_endpoint:
            raise AdapterError("Mantra device has no HTTP endpoint — USB/agent-mode only.")
        pushed = 0
        for cred in credentials:
            try:
                resp = requests.post(
                    f"{self._base(device)}/users",
                    json={
                        "userName": cred.customer.name,
                        "userId": cred.device_user_id,
                        "privilege": 0,
                    },
                    timeout=10,
                )
                if resp.status_code in (200, 201, 204):
                    pushed += 1
            except requests.exceptions.RequestException:
                continue
        return {
            "ok": pushed > 0,
            "pushed": pushed,
            "detail": f"Pushed {pushed} users via HTTP",
            "protocol": self.protocol,
        }

    def fetch_events(
        self, device: BiometricDevice, since: datetime | None = None
    ) -> list[dict]:
        """Fetch attendance/access events from the device."""
        params: dict[str, str] = {"limit": "100"}
        if since:
            params["from"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            resp = requests.get(
                f"{self._base(device)}/attendance", params=params, timeout=15
            )
            if resp.status_code == 200:
                return resp.json().get("records", [])
        except requests.exceptions.RequestException:
            pass
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Probe device status endpoint."""
        try:
            resp = requests.get(f"{self._base(device)}/status", timeout=8)
            online = resp.status_code == 200
            return {
                "online": online,
                "detail": f"Mantra device {'reachable' if online else f'HTTP {resp.status_code}'}",
                "protocol": self.protocol,
            }
        except requests.exceptions.RequestException:
            detail = f"Mantra unreachable on port {self.PORT}"
            return {"online": False, "detail": detail, "protocol": self.protocol}
