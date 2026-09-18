"""Generic HTTP bridge adapter for ``vendor="generic"`` devices (issue #22).

Talks to any device bridge that exposes a simple REST contract:

- ``POST {api_endpoint}/allowlist`` — push the credential allow-list
- ``GET  {api_endpoint}/events?since=<ISO-8601>`` — fetch access events
- ``GET  {api_endpoint}/status`` — connection health check

Authentication uses the device ``api_key`` as a bearer token.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.utils import timezone

import requests

from apps.access.adapters.base import AdapterError, BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 5


class GenericHTTPAdapter(BiometricAdapter):
    """Adapter for bridges implementing the generic REST contract."""

    def _base_url(self, device: BiometricDevice) -> str:
        """Return the device endpoint without a trailing slash."""
        if not device.api_endpoint:
            raise AdapterError(f"Device '{device.name}' has no api_endpoint configured.")
        return device.api_endpoint.rstrip("/")

    def _headers(self, device: BiometricDevice) -> dict:
        """Return auth headers for the device bridge."""
        return {
            "Authorization": f"Bearer {device.api_key}",
            "Content-Type": "application/json",
        }

    def sync_allow_list(
        self,
        device: BiometricDevice,
        credentials: Any,
    ) -> dict:
        """Push the allow-list of credentials to the device bridge."""
        payload = {
            "credentials": [
                {
                    "device_user_id": credential.device_user_id,
                    "credential_type": credential.credential_type,
                    "is_active": credential.is_active,
                }
                for credential in credentials
            ]
        }
        try:
            response = requests.post(
                f"{self._base_url(device)}/allowlist",
                json=payload,
                headers=self._headers(device),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise AdapterError(f"Allow-list push failed for '{device.name}': {exc}") from exc

        if response.status_code in (401, 403):
            raise AdapterError(
                f"Allow-list push rejected: authentication failed (HTTP {response.status_code})."
            )
        if response.status_code >= 400:
            raise AdapterError(
                f"Allow-list push rejected by '{device.name}' with HTTP {response.status_code}."
            )

        device.last_sync_at = timezone.now()
        device.save(update_fields=["last_sync_at", "updated_at"])
        pushed = len(payload["credentials"])
        return {"ok": True, "pushed": pushed, "detail": f"Pushed {pushed} credentials to '{device.name}'."}

    def fetch_events(
        self,
        device: BiometricDevice,
        since: datetime | None = None,
    ) -> list[dict]:
        """Fetch access events from the device bridge since a timestamp."""
        params = {"since": since.isoformat()} if since else {}
        try:
            response = requests.get(
                f"{self._base_url(device)}/events",
                params=params,
                headers=self._headers(device),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise AdapterError(f"Event fetch failed for '{device.name}': {exc}") from exc

        if response.status_code in (401, 403):
            raise AdapterError(
                f"Event fetch rejected: authentication failed (HTTP {response.status_code})."
            )
        if response.status_code >= 400:
            raise AdapterError(
                f"Event fetch rejected by '{device.name}' with HTTP {response.status_code}."
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterError(f"Device bridge '{device.name}' returned invalid JSON.") from exc

        if isinstance(body, dict):
            return list(body.get("events", []))
        if isinstance(body, list):
            return body
        return []

    def test_connection(self, device: BiometricDevice) -> dict:
        """Probe the device bridge status endpoint; report reachability."""
        if not device.api_endpoint:
            return {"online": False, "detail": "Device has no api_endpoint configured."}
        try:
            response = requests.get(
                f"{self._base_url(device)}/status",
                headers=self._headers(device),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.warning("Connection test failed for device %s: %s", device.pk, exc)
            return {"online": False, "detail": f"Device bridge unreachable: {exc}"}

        if response.status_code in (401, 403):
            return {
                "online": False,
                "detail": f"Authentication failed (HTTP {response.status_code}).",
            }
        if response.status_code >= 400:
            return {
                "online": False,
                "detail": f"Device bridge returned HTTP {response.status_code}.",
            }

        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at", "updated_at"])
        return {"online": True, "detail": "Device bridge is reachable."}
