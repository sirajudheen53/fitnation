"""Membership read selectors — the app-access entitlement engine (FBOS-011 §1).

The entitlement is *derived*, never stored: a pure function of the member's
current membership → its plan, recomputed on every call so plan toggles and
renewals take effect on the member's next request. There is no Celery in this
project, so a stored state (or a stored ``grace_until`` column) would need a
daily job to expire — see ADR-003 "Alternatives rejected".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.tenants.models import Tenant


class EntitlementStatus:
    """String values for :attr:`AppEntitlement.status`."""

    ACTIVE = "active"
    GRACE = "grace"
    EXPIRED = "expired"
    NONE = "none"


@dataclass(frozen=True)
class AppEntitlement:
    """The member's app-access state at a point in time.

    Attributes:
        status: One of ``active`` (full access), ``grace`` (read-only window
            after expiry), ``expired`` (gated out) or ``none`` (no membership,
            plan without app access, or tenant rollout flag off).
        read_only: ``True`` only when ``status == "grace"``.
        membership_id: The membership the state was derived from, if any.
        plan_name: Display name of the membership's plan, if any.
        plan_includes_app_access: The plan-level toggle (FBOS-011 D1).
        end_date: The membership's end date, if any.
        grace_end_date: Last day of the read-only grace window (only set in
            the ``grace`` and ``expired`` states).
    """

    status: str
    read_only: bool
    membership_id: int | None
    plan_name: str | None
    plan_includes_app_access: bool
    end_date: date | None
    grace_end_date: date | None

    @property
    def entitled(self) -> bool:
        """Whether the member may use the app right now (grace counts)."""
        return self.status in {EntitlementStatus.ACTIVE, EntitlementStatus.GRACE}

    def as_payload(self) -> dict:
        """Return the mobile-facing ``entitlement`` object (FBOS-011 §2.3).

        The contract the app builds its gate against: a status string, a
        read-only flag, plan/expiry copy fields and the anchored gym.
        """
        return {
            "status": self.status,
            "read_only": self.read_only,
            "plan_name": self.plan_name,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "grace_end_date": self.grace_end_date.isoformat() if self.grace_end_date else None,
        }


def _app_access_flag_enabled(tenant) -> bool:
    """Whether the per-tenant rollout flag is on (FBOS-011 D10 / §9.2).

    Flag off ⇒ the entitlement engine does not exist for that tenant: no
    ``app.access`` is ever granted and :class:`~apps.permissions.entitlements.EntitlementRequired`
    short-circuits to allow, so legacy tenants and old app builds are
    unaffected.
    """
    return bool((tenant.features or {}).get("app_access"))


def get_latest_membership(customer: "Customer"):
    """Return the member's live membership: the non-cancelled row with the max ``end_date``.

    Renewals extend ``end_date`` on the same row, so in practice there is one
    live row per customer; the max-rule makes history rows harmless
    (FBOS-011 §1.2).

    Args:
        customer: The customer whose memberships are considered.

    Returns:
        The latest non-cancelled ``Membership`` (plan joined), or ``None``.
    """
    return customer.memberships.exclude(status="cancelled").select_related("plan").order_by("-end_date", "-id").first()


def get_app_entitlement(customer: "Customer | None", *, tenant: "Tenant", on: date | None = None) -> AppEntitlement:
    """Compute the member's app-access state (single source of truth).

    Rules, in order (FBOS-011 §1.3):
    1. Tenant rollout flag off → ``none``.
    2. No non-cancelled membership → ``none``.
    3. Plan without ``includes_app_access`` → ``none``.
    4. Date rules (mirroring ``Membership.compute_status`` — active on
       ``end_date`` itself, grace from the day after):
       ``today ≤ end_date`` → active; ``end_date < today ≤ end_date + grace``
       → grace (read-only); beyond → expired. A cancelled membership never
       reaches the date rules (cancellation is a business act — immediate
       revoke, no grace).

    Args:
        customer: The customer (``None`` → ``none``; keeps call sites simple
            for users without a customer profile).
        tenant: The tenant whose rollout flag applies.
        on: Evaluate as of this date (defaults to today; tests).

    Returns:
        The frozen :class:`AppEntitlement` for the member.
    """
    today = on or timezone.localdate()
    base = AppEntitlement(
        status=EntitlementStatus.NONE,
        read_only=False,
        membership_id=None,
        plan_name=None,
        plan_includes_app_access=False,
        end_date=None,
        grace_end_date=None,
    )
    if customer is None:
        return base
    if not _app_access_flag_enabled(tenant):
        return base

    membership = get_latest_membership(customer)
    if membership is None:
        return base

    plan = membership.plan
    if not plan.includes_app_access:
        return AppEntitlement(
            status=EntitlementStatus.NONE,
            read_only=False,
            membership_id=membership.pk,
            plan_name=plan.name,
            plan_includes_app_access=False,
            end_date=membership.end_date,
            grace_end_date=None,
        )

    grace_days = int(getattr(settings, "APP_ACCESS_GRACE_DAYS", 7))
    grace_end = membership.end_date + timedelta(days=grace_days) if membership.end_date else None

    if membership.end_date is None or today <= membership.end_date:
        status, read_only, grace_end_date = EntitlementStatus.ACTIVE, False, None
    elif grace_end is not None and today <= grace_end:
        status, read_only, grace_end_date = EntitlementStatus.GRACE, True, grace_end
    else:
        status, read_only, grace_end_date = EntitlementStatus.EXPIRED, False, grace_end

    return AppEntitlement(
        status=status,
        read_only=read_only,
        membership_id=membership.pk,
        plan_name=plan.name,
        plan_includes_app_access=True,
        end_date=membership.end_date,
        grace_end_date=grace_end_date,
    )
