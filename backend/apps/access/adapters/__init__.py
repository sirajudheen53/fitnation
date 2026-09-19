"""Access adapters package — vendor adapter contract + implementations."""

from apps.access.adapters.base import (
    AdapterError,
    AdapterNotRegisteredError,
    BiometricAdapter,
)
from apps.access.adapters.registry import (
    get_adapter,
    get_adapter_class,
    registered_vendors,
    register_adapter,
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
