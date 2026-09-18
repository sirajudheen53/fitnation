"""Vendor string -> adapter class registry (Sprint 8, issue #22)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.access.adapters.base import AdapterNotRegisteredError, BiometricAdapter
from apps.access.adapters.generic_http import GenericHTTPAdapter
from apps.access.adapters.vendor_stubs import (
    EsslAdapter,
    HikvisionAdapter,
    MatrixAdapter,
    SupervisionAdapter,
    ZKTecoAdapter,
)

if TYPE_CHECKING:
    from apps.access.models import BiometricDevice

_REGISTRY: dict[str, type[BiometricAdapter]] = {}


def register_adapter(vendor: str, adapter_class: type[BiometricAdapter]) -> None:
    """Register (or replace) the adapter class for a vendor string."""
    _REGISTRY[vendor] = adapter_class


def get_adapter_class(vendor: str) -> type[BiometricAdapter]:
    """Return the registered adapter class for a vendor string.

    Raises:
        AdapterNotRegisteredError: If no adapter is registered for the vendor.
    """
    try:
        return _REGISTRY[vendor]
    except KeyError as exc:
        raise AdapterNotRegisteredError(
            f"No biometric adapter registered for vendor '{vendor}'."
        ) from exc


def get_adapter(device: BiometricDevice) -> BiometricAdapter:
    """Return an adapter instance suitable for the given device."""
    return get_adapter_class(device.vendor)()


def registered_vendors() -> list[str]:
    """Return the vendor strings currently covered by the registry."""
    return sorted(_REGISTRY)


# Default registrations — must cover every Vendor model choice.
register_adapter("generic", GenericHTTPAdapter)
register_adapter("hikvision", HikvisionAdapter)
register_adapter("zkteco", ZKTecoAdapter)
register_adapter("essl", EsslAdapter)
register_adapter("matrix", MatrixAdapter)
register_adapter("supervision", SupervisionAdapter)
