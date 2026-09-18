"""Vendor string -> adapter class registry (Sprint 8/9, issues #22, #27)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.access.adapters.base import AdapterNotRegisteredError, BiometricAdapter

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


def _bootstrap() -> None:
    """Register all known vendor adapters (deferred imports avoid cycles)."""
    from apps.access.adapters.anviz import AnvizAdapter
    from apps.access.adapters.dahua import DahuaAdapter
    from apps.access.adapters.essl import EsslAdapter
    from apps.access.adapters.generic_http import GenericHTTPAdapter
    from apps.access.adapters.hikvision import HikvisionAdapter
    from apps.access.adapters.mantra import MantraAdapter
    from apps.access.adapters.matrix import MatrixAdapter
    from apps.access.adapters.realtime import RealtimeAdapter
    from apps.access.adapters.suprema import SupremaAdapter
    from apps.access.adapters.timewatch import TimeWatchAdapter
    from apps.access.adapters.zkteco import ZKTecoADMSAdapter

    register_adapter("generic", GenericHTTPAdapter)
    register_adapter("hikvision", HikvisionAdapter)
    register_adapter("zkteco", ZKTecoADMSAdapter)
    register_adapter("essl", EsslAdapter)
    register_adapter("matrix", MatrixAdapter)
    register_adapter("suprema", SupremaAdapter)
    register_adapter("anviz", AnvizAdapter)
    register_adapter("dahua", DahuaAdapter)
    register_adapter("realtime", RealtimeAdapter)
    register_adapter("mantra", MantraAdapter)
    register_adapter("timewatch", TimeWatchAdapter)


_bootstrap()
