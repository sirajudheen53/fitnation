"""HIKVISION ISAPI adapter (Sprint 9, issue #29)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests
from requests.auth import HTTPDigestAuth

from apps.access.adapters.base import AdapterError, BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class HikvisionAdapter(BiometricAdapter):
    """HIKVISION ISAPI adapter for DS-K1T series face terminals."""

    vendor_label = "HIKVISION"
    protocol = "isapi"

    def _base(self, device: BiometricDevice) -> str:
        return f"http://{device.api_endpoint or 'localhost'}"

    def _auth(self, device: BiometricDevice) -> HTTPDigestAuth:
        return HTTPDigestAuth("admin", device.api_key or "")

    def sync_allow_list(
        self,
        device: BiometricDevice,
        credentials: Any,
    ) -> dict:
        """Push user records to the device via ISAPI."""
        if not device.api_endpoint:
            raise AdapterError("No ISAPI endpoint configured")

        pushed = 0
        for cred in credentials:
            user_data = {
                "UserInfo": {
                    "employeeNo": cred.device_user_id,
                    "name": cred.customer.name,
                    "userType": "normal",
                    "Valid": {
                        "enable": True,
                        "beginTime": "2020-01-01T00:00:00",
                        "endTime": "2030-12-31T23:59:59",
                        "timeType": "local",
                    },
                    "doorNo": "1",
                    "numOfCard": 1 if cred.credential_type == "card" else 0,
                    "numOfFP": 1 if cred.credential_type == "fingerprint" else 0,
                    "numOfFace": 1 if cred.credential_type == "face" else 0,
                }
            }
            try:
                resp = requests.put(
                    f"{self._base(device)}/ISAPI/AccessControl/UserInfo/Record?format=json",
                    json=user_data,
                    auth=self._auth(device),
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                    verify=False,
                )
                if resp.status_code in (200, 201):
                    pushed += 1
            except requests.exceptions.RequestException as exc:
                import logging
                logging.getLogger(__name__).warning("Hikvision push failed: %s", exc)
        return {
            "ok": pushed > 0,
            "pushed": pushed,
            "detail": f"Pushed {pushed} users via ISAPI",
            "protocol": self.protocol,
        }

    def fetch_events(
        self,
        device: BiometricDevice,
        since: datetime | None = None,
    ) -> list[dict]:
        """Fetch events from device event log."""
        if not device.api_endpoint:
            return []
        try:
            resp = requests.get(
                f"{self._base(device)}/ISAPI/AccessControl/AcsEvent?format=json"
                "&searchID=all&maxResults=100",
                auth=self._auth(device),
                timeout=10,
                verify=False,
            )
            if resp.status_code == 200:
                return resp.json().get("InfoList", [])
        except requests.exceptions.RequestException:
            pass
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Probe device info via ISAPI."""
        if not device.api_endpoint:
            return {"online": False, "detail": "No endpoint configured", "protocol": self.protocol}
        try:
            resp = requests.get(
                f"{self._base(device)}/ISAPI/System/deviceInfo",
                auth=self._auth(device),
                timeout=8,
                verify=False,
            )
            online = resp.status_code == 200
            return {
                "online": online,
                "detail": f"ISAPI {'OK' if online else f'HTTP {resp.status_code}'}",
                "protocol": self.protocol,
            }
        except requests.exceptions.ConnectionError:
            return {"online": False, "detail": "Device unreachable", "protocol": self.protocol}
        except Exception as exc:
            return {"online": False, "detail": str(exc), "protocol": self.protocol}
