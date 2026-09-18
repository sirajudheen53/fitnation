"""Abstract biometric vendor adapter contract (Sprint 8, issue #22)."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice


class AdapterError(Exception):
    """Raised when a vendor adapter operation fails (transport or device error)."""


class AdapterNotRegisteredError(AdapterError):
    """Raised when no adapter class is registered for a device vendor."""


class BiometricAdapter(abc.ABC):
    """Contract every biometric vendor adapter must implement.

    Adapters are stateless; every method receives the ``BiometricDevice``
    (which carries vendor, endpoint, and credentials) so a single instance
    can serve any device of its vendor.
    """

    @abc.abstractmethod
    def sync_allow_list(
        self,
        device: BiometricDevice,
        credentials: Any,
    ) -> dict:
        """Push the given credentials to the device as its allow-list.

        Args:
            device: The target biometric device.
            credentials: An iterable of ``BiometricCredential`` allowed on the device.

        Returns:
            A dict describing the push outcome, e.g. ``{"ok": bool, "pushed": int, "detail": str}``.

        Raises:
            AdapterError: If the device is unreachable or rejects the push.
        """

    @abc.abstractmethod
    def fetch_events(
        self,
        device: BiometricDevice,
        since: datetime | None = None,
    ) -> list[dict]:
        """Fetch access events recorded by the device.

        Args:
            device: The source biometric device.
            since: Only return events after this timestamp; ``None`` fetches all.

        Returns:
            A list of raw event dicts as returned by the device/bridge.

        Raises:
            AdapterError: If the device is unreachable or returns an error.
        """

    @abc.abstractmethod
    def test_connection(self, device: BiometricDevice) -> dict:
        """Check whether the device (or its bridge) is reachable and healthy.

        Never raises for connectivity problems; failures are reported as
        ``{"online": False, "detail": str}``.

        Args:
            device: The biometric device to probe.

        Returns:
            A dict with ``online`` (bool) and ``detail`` (str) keys.
        """
