"""Dahua DSS adapter (Sprint 9, issue #33)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from apps.access.adapters.base import BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class DahuaAdapter(BiometricAdapter):
    """Dahua DSS / ASI series adapter."""

    vendor_label = "Dahua"
    protocol = "dss"

    def _base(self, device: BiometricDevice) -> str:
        return f"https://{device.api_endpoint or 'localhost'}"

    def _auth(self, device: BiometricDevice) -> tuple[str, str]:
        return ("admin", device.api_key or "")

    def sync_allow_list(self, device: BiometricDevice, credentials: Any) -> dict:
        """Push personnel via DSS person API."""
        pushed = 0
        for cred in credentials:
            try:
                resp = requests.post(
                    f"{self._base(device)}/api/face/person",
                    json={
                        "personId": cred.device_user_id,
                        "personName": cred.customer.name,
                        "credentialType": cred.credential_type,
                    },
                    auth=self._auth(device),
                    timeout=10,
                    verify=False,
                )
                if resp.status_code in (200, 201, 204):
                    pushed += 1
            except requests.exceptions.RequestException:
                continue
        return {
            "ok": pushed > 0,
            "pushed": pushed,
            "detail": f"Synced {pushed} personnel via DSS",
            "protocol": self.protocol,
        }

    def fetch_events(
        self, device: BiometricDevice, since: datetime | None = None
    ) -> list[dict]:
        """Fetch access events from DSS event center."""
        params: dict[str, str] = {"pageSize": "100"}
        if since:
            params["startTime"] = since.strftime("%Y-%m-%d %H:%M:%S")
        try:
            resp = requests.get(
                f"{self._base(device)}/api/event/attendance",
                params=params,
                auth=self._auth(device),
                timeout=15,
                verify=False,
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
        except requests.exceptions.RequestException:
            pass
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Probe DSS system info."""
        try:
            resp = requests.get(
                f"{self._base(device)}/api/system/deviceInfo",
                auth=self._auth(device),
                timeout=8,
                verify=False,
            )
            online = resp.status_code == 200
            return {
                "online": online,
                "detail": f"DSS {'OK' if online else f'HTTP {resp.status_code}'}",
                "protocol": self.protocol,
            }
        except requests.exceptions.RequestException as exc:
            return {"online": False, "detail": str(exc), "protocol": self.protocol}
