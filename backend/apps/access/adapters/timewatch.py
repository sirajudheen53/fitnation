"""TimeWatch adapter (Sprint 9, issue #37) — cloud API + agent-mode fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from apps.access.adapters.base import BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class TimeWatchAdapter(BiometricAdapter):
    """TimeWatch Cloud REST + agent-mode fallback adapter."""

    vendor_label = "TimeWatch"
    protocol = "timewatch_cloud"
    BASE_URL = "https://api.timewatch.com/api/v1"

    def _headers(self, device: BiometricDevice) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {device.api_key or ''}",
        }

    def sync_allow_list(self, device: BiometricDevice, credentials: Any) -> dict:
        """Push personnel via TimeWatch Cloud API, or queue for agent mode."""
        if not device.api_endpoint:
            from apps.access.models import DeviceCommandQueue

            queued = 0
            for cred in credentials:
                DeviceCommandQueue.objects.create(
                    tenant=device.tenant,
                    device=device,
                    command="enroll_user",
                    payload={
                        "user_id": cred.device_user_id,
                        "name": cred.customer.name,
                    },
                )
                queued += 1
            return {
                "ok": True,
                "pushed": queued,
                "detail": "Queued via agent-mode command queue",
                "protocol": "agent_mode",
            }

        pushed = 0
        for cred in credentials:
            payload = {
                "employeeId": cred.device_user_id,
                "name": cred.customer.name,
                "credentialType": cred.credential_type,
            }
            try:
                resp = requests.post(
                    f"{self.BASE_URL}/personnel",
                    json=payload,
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
            "detail": f"Synced {pushed} personnel to TimeWatch Cloud",
            "protocol": self.protocol,
        }

    def fetch_events(
        self, device: BiometricDevice, since: datetime | None = None
    ) -> list[dict]:
        """Fetch attendance punches from TimeWatch Cloud."""
        if not device.api_endpoint:
            return []
        params: dict[str, str] = {"limit": "100"}
        if since:
            params["fromDate"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            resp = requests.get(
                f"{self.BASE_URL}/attendance/logs",
                params=params,
                headers=self._headers(device),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("logEntries", [])
        except requests.exceptions.RequestException:
            pass
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Test TimeWatch Cloud API reachability."""
        if not device.api_endpoint:
            return {
                "online": False,
                "detail": "Agent-mode device — cloud API not applicable.",
                "protocol": "agent_mode",
            }
        try:
            resp = requests.get(
                f"{self.BASE_URL}/personnel",
                params={"limit": "1"},
                headers=self._headers(device),
                timeout=8,
            )
            online = resp.status_code in (200, 401, 403)
            return {
                "online": online,
                "detail": f"TimeWatch Cloud {'reachable' if online else f'HTTP {resp.status_code}'}",
                "protocol": self.protocol,
            }
        except requests.exceptions.RequestException as exc:
            return {"online": False, "detail": str(exc), "protocol": self.protocol}
