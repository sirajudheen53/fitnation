"""Deterministic gym code generation (FBOS-011 mobile install-by-code flow).

A gym code is a short, human-readable, uppercase identifier that a member can
type when installing the app without an invite link
(``GET /api/v1/tenants/lookup/?code=...``).

Generation is *deterministic*: a code is derived from the tenant's immutable
UUID, so re-running the backfill (or regenerating a lost code) always yields
the same value and no code depends on creation order.
"""

import hashlib
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.tenants.models import Tenant

# 31 symbols with the look-alike characters (0/O, 1/I/L) removed so a code
# read off a poster is unambiguous.
GYM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
GYM_CODE_LENGTH = 7


def generate_gym_code(seed: str) -> str:
    """Deterministically derive a gym code from ``seed``.

    Args:
        seed: Any stable string (typically the tenant uuid — and a sequence
            number for collision walks).

    Returns:
        A ``GYM_CODE_LENGTH``-char code from :data:`GYM_CODE_ALPHABET`.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    value = int.from_bytes(digest, "big")
    alphabet_len = len(GYM_CODE_ALPHABET)
    chars: list[str] = []
    for _ in range(GYM_CODE_LENGTH):
        chars.append(GYM_CODE_ALPHABET[value % alphabet_len])
        value //= alphabet_len
    return "".join(chars)


def gym_code_candidates(seed: str) -> Iterator[str]:
    """Yield deterministic gym codes until one is free.

    The first candidate uses ``seed``; each subsequent candidate appends a
    sequence number to the seed, so the walk itself stays deterministic and
    two tenants that collide still resolve to stable, distinct codes.

    Args:
        seed: The walk seed (the tenant uuid).

    Yields:
        Candidate gym codes, one at a time.
    """
    counter = 0
    while True:
        yield generate_gym_code(f"{seed}:{counter}")
        counter += 1


def assign_gym_code(tenant: "Tenant") -> str:
    """Compute the deterministic, collision-free code for ``tenant``.

    Args:
        tenant: The tenant to assign a code to (uses ``tenant.uuid`` as seed).

    Returns:
        The first deterministic candidate already free in the database.
    """
    from apps.tenants.models import Tenant

    for candidate in gym_code_candidates(str(tenant.uuid)):
        # Own row must not count as "taken" (idempotent re-assignment).
        taken = Tenant.objects.filter(gym_code=candidate)
        if tenant.pk is not None:
            taken = taken.exclude(pk=tenant.pk)
        if not taken.exists():
            return candidate
    # Unreachable: candidates are unbounded, but keeps type checkers honest.
    raise RuntimeError("gym code space exhausted")


def backfill_gym_codes_for(tenant_model: type) -> int:
    """Assign a deterministic, collision-free gym code to every blank-code gym.

    Deterministic: codes derive from each tenant's uuid, independent of
    iteration order — running the backfill twice (or re-running a restored
    backup migration) yields identical assignments.

    Args:
        tenant_model: The (possibly historical) ``Tenant`` model class.

    Returns:
        How many tenants were assigned a code.
    """
    assigned = 0
    for tenant in tenant_model.objects.filter(gym_code__isnull=True).order_by("id"):
        for candidate in gym_code_candidates(str(tenant.uuid)):
            taken = tenant_model.objects.filter(gym_code=candidate)
            if tenant.pk is not None:
                taken = taken.exclude(pk=tenant.pk)
            if not taken.exists():
                tenant.gym_code = candidate
                tenant.save(update_fields=["gym_code", "updated_at"])
                assigned += 1
                break
    return assigned
