"""Generic HTTP/MQTT bridge adapter (Sprint 8, issue #22).

Devices behind an edge-agent bridge expose a minimal HTTP API:
``POST /allowlist`` (push credentials), ``GET /events`` (pull events),
``GET /status`` (health). Auth is a static bearer token.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from apps.access.adapters.base import AdapterError, BiometricAdapter

if TYPE_CHECKING:

    from apps.access.models import BiometricDevice


class GenericHTTPAdapter(BiometricAdapter):
    """Generic adapter for devices behind an HTTP bridge/agent.

    The gym's edge agent (bridge) translates our calls into
    device-specific protocols. Stateless — every method receives the
    device (endpoint + credentials included).
    """

    vendor_label = "Generic"
    protocol = "generic_http"

    def _headers(self, device: BiometricDevice) -> dict[str, str]:
        """Bearer auth headers for the bridge."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {device.api_key or ''}",
        }

    def sync_allow_list(
        self,
        device: BiometricDevice,
        credentials: Any,
    ) -> dict:
        """POST the credential list to the bridge as its allow-list.

        Args:
            device: The target biometric device (bridge endpoint on it).
            credentials: An iterable of ``BiometricCredential``.

        Returns:
            ``{"ok": bool, "pushed": int, "detail": str}``.

        Raises:
            AdapterError: On missing endpoint, auth failure, or 5xx.
        """
        if not device.api_endpoint:
            raise AdapterError("Device has no api_endpoint configured.")

        payload = {
            "credentials": [
                {
                    "device_user_id": cred.device_user_id,
                    "name": cred.customer.name,
                    "credential_type": cred.credential_type,
                }
                for cred in credentials
            ],
        }
        try:
            response = requests.post(
                f"{device.api_endpoint}/allowlist",
                json=payload,
                headers=self._headers(device),
                timeout=15,
            )
        except requests.exceptions.RequestException as exc:
            raise AdapterError(f"Bridge unreachable: {exc}") from exc

        if response.status_code in (401, 403):
            raise AdapterError(f"Bridge rejected credentials: HTTP {response.status_code}")
        if response.status_code >= 500:
            raise AdapterError(f"Bridge error: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise AdapterError(f"Bridge rejected the push: HTTP {response.status_code}")

        pushed = len(payload["credentials"])
        device.last_sync_at = timezone_now()
        device.save(update_fields=["last_sync_at"])
        return {
            "ok": True,
            "pushed": pushed,
            "detail": f"Bridge accepted {pushed} credentials.",
        }

    def fetch_events(
        self,
        device: BiometricDevice,
        since: Any = None,
    ) -> list[dict]:
        """GET ``/events`` from the bridge (optionally after ``since``).

        Raises:
            AdapterError: On missing endpoint, auth failure, or 5xx.
        """
        if not device.api_endpoint:
            raise AdapterError("Device has no api_endpoint.")

        params: dict[str, str] = {}
        if since is not None:
            params["since"] = since.isoformat()
        try:
            response = requests.get(
                f"{device.api_endpoint}/events",
                params=params,
                headers=self._headers(device),
                timeout=15,
            )
        except requests.exceptions.RequestException as exc:
            raise AdapterError(f"Bridge unreachable: {exc}") from exc

        if response.status_code in (401, 403):
            raise AdapterError(f"Bridge rejected credentials: HTTP {response.status_code}")
        if response.status_code >= 500:
            raise AdapterError(f"Bridge error: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise AdapterError(f"Bridge refused the fetch: HTTP {response.status_code}")

        data = response.json()
        if isinstance(data, list):
            return data
        return data.get("events", [])

    def test_connection(self, device: BiometricDevice) -> dict:
        """GET ``/status`` — 200 means online; stamps ``last_seen_at``."""
        if not device.api_endpoint:
            return {
                "online": False,
                "detail": "No api_endpoint configured on the device.",
            }
        try:
            response = requests.get(
                f"{device.api_endpoint}/status",
                headers=self._headers(device),
                timeout=8,
            )
        except requests.exceptions.RequestException as exc:
            return {"online": False, "detail": str(exc)}

        if response.status_code == 200:
            device.last_seen_at = timezone_now()
            device.save(update_fields=["last_seen_at"])
            return {"online": True, "detail": "Bridge reachable."}
        if response.status_code in (401, 403):
            return {
                "online": False,
                "detail": f"Authentication failed: HTTP {response.status_code}",
            }
        return {"online": False, "detail": f"Bridge error: HTTP {response.status_code}"}


def timezone_now():
    """Return the current timezone-aware datetime (import-lazy)."""
    from django.utils import timezone

    return timezone.now()
