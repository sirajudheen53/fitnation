"""Biometric vendor adapter framework (Sprint 8, issue #22).

Exposes the abstract adapter contract, the vendor->adapter registry, and the
concrete adapters shipped with the framework.
"""

from apps.access.adapters.base import (
    AdapterError,
    AdapterNotRegisteredError,
    BiometricAdapter,
)
from apps.access.adapters.registry import (
    get_adapter,
    get_adapter_class,
    register_adapter,
    registered_vendors,
)

__all__ = [
    "AdapterError",
    "AdapterNotRegisteredError",
    "BiometricAdapter",
    "get_adapter",
    "get_adapter_class",
    "register_adapter",
    "registered_vendors",
]
