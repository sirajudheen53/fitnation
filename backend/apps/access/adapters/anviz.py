"""Anviz CrossChex Cloud adapter (Sprint 9, issue #32)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from apps.access.adapters.base import BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class AnvizAdapter(BiometricAdapter):
    """Anviz CrossChex Cloud REST API adapter."""

    vendor_label = "Anviz"
    protocol = "crosschex"
    BASE_URL = "https://api.crosschex.net/we/v2"

    def _headers(self, device: BiometricDevice) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {device.api_key or ''}",
        }

    def sync_allow_list(self, device: BiometricDevice, credentials: Any) -> dict:
        """Push personnel to CrossChex."""
        pushed = 0
        for cred in credentials:
            try:
                resp = requests.put(
                    f"{self.BASE_URL}/employees/{cred.device_user_id}",
                    json={"name": cred.customer.name},
                    headers=self._headers(device),
                    timeout=10,
                )
                if resp.status_code in (200, 201, 204, 409):
                    pushed += 1
            except requests.exceptions.RequestException:
                continue
        return {
            "ok": pushed > 0,
            "pushed": pushed,
            "detail": f"Synced {pushed} personnel to CrossChex",
            "protocol": self.protocol,
        }

    def fetch_events(
        self, device: BiometricDevice, since: datetime | None = None
    ) -> list[dict]:
        """Fetch records from CrossChex."""
        params: dict[str, str] = {"limit": "100"}
        if since:
            params["start_time"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            resp = requests.get(
                f"{self.BASE_URL}/checkin/records",
                params=params,
                headers=self._headers(device),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("records", [])
        except requests.exceptions.RequestException:
            pass
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Test CrossChex API reachability."""
        try:
            resp = requests.get(
                f"{self.BASE_URL}/checkin/records",
                params={"limit": "1"},
                headers=self._headers(device),
                timeout=8,
            )
            online = resp.status_code in (200, 401, 403)
            return {
                "online": online,
                "detail": f"CrossChex {'reachable' if online else f'HTTP {resp.status_code}'}",
                "protocol": self.protocol,
            }
        except requests.exceptions.RequestException as exc:
            return {"online": False, "detail": str(exc), "protocol": self.protocol}
