"""Suprema BioStar 2 adapter (Sprint 9, issue #34)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from apps.access.adapters.base import AdapterError, BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class SupremaAdapter(BiometricAdapter):
    """Suprema BioStar 2 Open API adapter."""

    vendor_label = "Suprema"
    protocol = "biostar2"

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
        """Push users via BioStar 2 user API."""
        if not device.api_endpoint:
            raise AdapterError("BioStar 2 server URL not configured.")
        pushed = 0
        for cred in credentials:
            payload = {
                "user_id": cred.device_user_id,
                "name": cred.customer.name,
                "credential": {
                    "type": cred.credential_type,
                    "id": cred.device_user_id,
                },
            }
            try:
                resp = requests.post(
                    f"{device.api_endpoint}/api/users",
                    json=payload,
                    headers=self._headers(device),
                    timeout=10,
                )
                if resp.status_code in (200, 201, 204, 409):
                    pushed += 1
            except requests.exceptions.RequestException as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Suprema user sync failed: %s", exc
                )
        return {
            "ok": pushed > 0,
            "pushed": pushed,
            "detail": f"Pushed {pushed} users to BioStar 2",
            "protocol": self.protocol,
        }

    def fetch_events(
        self,
        device: BiometricDevice,
        since: datetime | None = None,
    ) -> list[dict]:
        """Fetch events from BioStar 2 event log."""
        params = {"limit": 100}
        if since:
            params["datetime"] = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        try:
            resp = requests.get(
                f"{device.api_endpoint}/api/events",
                params=params,
                headers=self._headers(device),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("rows", [])
        except requests.exceptions.RequestException:
            pass
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Test BioStar 2 API reachability."""
        if not device.api_endpoint:
            return {"online": False, "detail": "No BioStar 2 URL configured", "protocol": self.protocol}
        try:
            resp = requests.get(
                f"{device.api_endpoint}/api/users",
                params={"page": 1, "limit": 1},
                headers=self._headers(device),
                timeout=8,
            )
            online = resp.status_code in (200, 401, 403)
            return {
                "online": online,
                "detail": f"BioStar 2 API {'reachable' if online else f'HTTP {resp.status_code}'}",
                "protocol": self.protocol,
            }
        except requests.exceptions.ConnectionError:
            return {"online": False, "detail": "BioStar 2 unreachable", "protocol": self.protocol}
        except Exception as exc:
            return {"online": False, "detail": str(exc), "protocol": self.protocol}
