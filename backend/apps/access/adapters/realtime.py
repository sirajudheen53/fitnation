"""Realtime HTTP push adapter (Sprint 9, issue #35)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from apps.access.adapters.base import AdapterError, BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class RealtimeAdapter(BiometricAdapter):
    """Realtime Biometrics HTTP adapter (port 50111)."""

    vendor_label = "Realtime"
    protocol = "http_push"
    PORT = 50111

    def _base(self, device: BiometricDevice) -> str:
        return f"http://{device.api_endpoint or 'localhost'}:{self.PORT}"

    def sync_allow_list(self, device: BiometricDevice, credentials: Any) -> dict:
        """Push users via the device HTTP API."""
        if not device.api_endpoint:
            raise AdapterError("Realtime device has no HTTP endpoint — agent-mode only.")
        pushed = 0
        for cred in credentials:
            try:
                resp = requests.post(
                    f"{self._base(device)}/api/users",
                    json={
                        "user_id": cred.device_user_id,
                        "name": cred.customer.name,
                        "credential_type": cred.credential_type,
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
        """Fetch punch logs from the device."""
        params: dict[str, str] = {"limit": "100"}
        if since:
            params["from_time"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            resp = requests.get(
                f"{self._base(device)}/api/logs", params=params, timeout=15
            )
            if resp.status_code == 200:
                return resp.json().get("logs", [])
        except requests.exceptions.RequestException:
            pass
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Probe device status on port 50111."""
        try:
            resp = requests.get(f"{self._base(device)}/api/status", timeout=8)
            online = resp.status_code == 200
            return {
                "online": online,
                "detail": f"Device {'reachable' if online else f'HTTP {resp.status_code}'}",
                "protocol": self.protocol,
            }
        except requests.exceptions.RequestException as exc:
            return {"online": False, "detail": str(exc), "protocol": self.protocol}
