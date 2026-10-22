"""Per-tenant module feature flags (issue #46).

Each gym can switch individual product modules on/off in its settings; the
stored values live in ``Tenant.features``. Semantics are **default-allow**:
a missing key means the module is enabled, only an explicit ``False`` disables
it. That keeps every existing tenant (whose ``features`` JSON carries other
keys — ``app_access``, ``biometric_cool_off_days`` — and no module keys) on
its current behaviour the moment this ships, with no backfill.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from apps.tenants.models import Tenant


@dataclass(frozen=True)
class ModuleFeature:
    """One toggleable module: JSON key, settings-page metadata, default."""

    key: str
    label: str
    description: str = ""
    default: bool = True


MODULE_FEATURES: ClassVar[tuple[ModuleFeature, ...]] = (
    ModuleFeature(
        key="marketplace",
        label="Marketplace",
        description="Product catalogue, cart, and member orders.",
        default=True,
    ),
    ModuleFeature(
        key="ai_coach",
        label="AI Coach",
        description="Conversational AI workout coach and recommendations.",
        default=True,
    ),
    ModuleFeature(
        key="ai_nutrition",
        label="AI Nutrition",
        description="AI meal plans, macro tracking, shopping lists.",
        default=True,
    ),
    ModuleFeature(
        key="body_analysis",
        label="Body Analysis",
        description="AI body composition analysis and progress photos.",
        default=True,
    ),
    ModuleFeature(
        key="reviews",
        label="Reviews",
        description="Member reviews and replies.",
        default=True,
    ),
)

FEATURE_KEYS: ClassVar[frozenset[str]] = frozenset(feature.key for feature in MODULE_FEATURES)
DEFAULT_FEATURE_FLAGS: ClassVar[dict[str, bool]] = {feature.key: feature.default for feature in MODULE_FEATURES}


def seed_default_features(preset: dict[str, Any] | None = None) -> dict[str, bool]:
    """Return the features dict for a NEW tenant: module defaults + any preset keys.

    Module flags are filled from the registry defaults so the settings UI lists
    every toggle with an explicit value from day one. Keys already present in
    the preset (e.g. the ``app_access`` rollout flag) always win — seeding
    never clobbers or removes them.

    Args:
        preset: Caller-supplied starting features (``None`` → empty).

    Returns:
        The merged features mapping (does NOT persist — assign to
        ``tenant.features`` and save).
    """
    merged: dict[str, Any] = dict(DEFAULT_FEATURE_FLAGS)
    merged.update(preset or {})
    return merged


def get_feature_flags(tenant: Tenant) -> dict[str, bool]:
    """Resolve every registered flag for a tenant (stored value or default).

    Args:
        tenant: The gym to resolve flags for.

    Returns:
        ``{key: enabled}`` for all registered module features.
    """
    return {feature.key: is_module_enabled(tenant, feature.key) for feature in MODULE_FEATURES}


def is_module_enabled(tenant: Tenant | None, key: str) -> bool:
    """Whether a module is enabled for the tenant (default-allow semantics).

    Args:
        tenant: The gym the request runs against.
        key: The ``Tenant.features`` key of the module.

    Returns:
        ``False`` only for an explicit stored ``False``; anything else
        (missing, ``True``, seed default) enables the module.
    """
    if key not in FEATURE_KEYS:
        return True  # unregistered keys are not enforced
    stored = (tenant.features or {}) if tenant is not None else {}
    value = stored.get(key)
    if value is None:
        return DEFAULT_FEATURE_FLAGS.get(key, True)
    return value is not False


def apply_feature_overrides(tenant: Tenant, updates: dict[str, bool]) -> dict[str, bool]:
    """Merge boolean overrides into ``tenant.features`` and return the result.

    Unknown keys raise — the settings API must never write a key no runtime
    check reads (a typo would silently become a dead toggle). Non-module keys
    already in ``features`` are preserved untouched.

    Args:
        tenant: The gym whose flags change.
        updates: ``{key: bool}`` overrides (validated by the serializer).

    Returns:
        The final ``tenant.features`` mapping (mutated in place on the bound
        ``Tenant``; the caller persists it with ``update_fields=["features"]``).

    Raises:
        KeyError: On any unregistered key.
    """
    unknown = [key for key in updates if key not in FEATURE_KEYS]
    if unknown:
        raise KeyError(f"Unknown feature keys: {', '.join(sorted(unknown))}")
    features = dict(tenant.features or {})
    features.update(updates)
    tenant.features = features
    return features
