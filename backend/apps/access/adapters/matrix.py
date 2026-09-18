"""Matrix COSEC adapter (Sprint 9, issue #31)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from apps.access.adapters.base import AdapterError, BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class MatrixAdapter(BiometricAdapter):
    """Matrix COSEC REST API adapter."""

    vendor_label = "Matrix"
    protocol = "cosec_rest"
    DEFAULT_PORT = 443

    def _base(self, device: BiometricDevice) -> str:
        return f"https://{device.api_endpoint or 'localhost'}"

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
        """Sync users via COSEC User API."""
        if not device.api_endpoint:
            raise AdapterError("Matrix device has no endpoint configured.")
        pushed = 0
        for cred in credentials:
            payload = {
                "refId": cred.device_user_id,
                "name": cred.customer.name,
                "credentialType": cred.credential_type,
            }
            try:
                resp = requests.post(
                    f"{self._base(device)}/api/v1/users",
                    json=payload,
                    headers=self._headers(device),
                    timeout=10,
                    verify=False,
                )
                if resp.status_code in (200, 201, 204, 409):
                    pushed += 1
            except requests.exceptions.RequestException as exc:
                import logging
                logging.getLogger(__name__).warning("Matrix push failed: %s", exc)
        return {
            "ok": pushed > 0,
            "pushed": pushed,
            "detail": f"Synced {pushed} users via COSEC",
            "protocol": self.protocol,
        }

    def fetch_events(
        self,
        device: BiometricDevice,
        since: datetime | None = None,
    ) -> list[dict]:
        """Fetch events from COSEC event log."""
        params = {"records": 100, "order": "desc"}
        if since:
            params["since"] = since.isoformat()
        try:
            resp = requests.get(
                f"{self._base(device)}/api/v1/events",
                params=params,
                headers=self._headers(device),
                timeout=15,
                verify=False,
            )
            if resp.status_code == 200:
                return resp.json().get("events", [])
        except requests.exceptions.RequestException:
            pass
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Probe COSEC device status."""
        if not device.api_endpoint:
            return {"online": False, "detail": "No endpoint configured", "protocol": self.protocol}
        try:
            resp = requests.get(
                f"{self._base(device)}/api/v1/device/status",
                headers=self._headers(device),
                timeout=8,
                verify=False,
            )
            online = resp.status_code == 200
            return {
                "online": online,
                "detail": f"COSEC API {'OK' if online else f'HTTP {resp.status_code}'}",
                "protocol": self.protocol,
            }
        except requests.exceptions.ConnectionError:
            return {"online": False, "detail": "Device unreachable", "protocol": self.protocol}
        except Exception as exc:
            return {"online": False, "detail": str(exc), "protocol": self.protocol}
