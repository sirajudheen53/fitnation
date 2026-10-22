"""PT session-pack entitlement engine (issue #52).

Like the app-access entitlement (``apps.memberships.selectors``), the PT pack
state is *derived*, never stored: remaining sessions are recomputed from the
customer's active PT membership plan and the redeemed session count on every
call, so plan edits and session transitions take effect immediately.

Redemption scope: a session redeems against the PT membership whose date
window contains its ``scheduled_at`` — only sessions within the *active*
membership's window count against that membership's pack, so a freshly sold
renewal pack starts clean.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

from apps.memberships.models import MembershipPlan
from apps.trainers.models import TrainerSession

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.memberships.models import Membership


class PTPackReason:
    """String values for :attr:`PTPackEntitlement.reason`."""

    OK = "ok"
    NO_ACTIVE_PT_MEMBERSHIP = "no_active_pt_membership"
    PT_MEMBERSHIP_EXPIRED = "pt_membership_expired"
    PACK_EXHAUSTED = "session_pack_exhausted"


@dataclass(frozen=True)
class PTPackEntitlement:
    """The customer's PT session-pack state at a point in time.

    Attributes:
        membership_id: The active PT membership the state derives from, if any.
        plan_name: Display name of that membership's plan, if any.
        membership_status: ``active`` / ``expired`` / ``none``.
        end_date: The membership's end date, if any.
        sessions_allowed: Pack size from the plan (``None`` = unlimited).
        redeemed: Completed + no-show sessions inside the membership window.
        remaining: Pack credits left (``None`` = unlimited, 0 when blocked).
        reason: Machine-readable state — one of :class:`PTPackReason`.
    """

    membership_id: int | None
    plan_name: str | None
    membership_status: str
    end_date: date | None
    sessions_allowed: int | None
    redeemed: int
    remaining: int | None
    reason: str

    @property
    def unlimited(self) -> bool:
        """Whether the pack has no session cap."""
        return self.membership_status == "active" and self.sessions_allowed is None

    @property
    def can_book(self) -> bool:
        """Whether a new session may be booked right now."""
        if self.membership_status != "active":
            return False
        return self.sessions_allowed is None or self.remaining > 0

    def as_payload(self) -> dict:
        """Return the ERP/mobile-facing ``pt-remaining`` payload."""
        return {
            "membership_id": self.membership_id,
            "plan_name": self.plan_name,
            "membership_status": self.membership_status,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "total": self.sessions_allowed,
            "redeemed": self.redeemed,
            "remaining": self.remaining,
            "unlimited": self.unlimited,
            "can_book": self.can_book,
            "reason": self.reason,
        }


def get_active_pt_membership(customer: Customer) -> Membership | None:
    """Return the customer's live PT membership: latest non-cancelled, PT-type plan.

    Mirrors ``apps.memberships.selectors.get_latest_membership`` but restricted
    to ``plan_type="pt"`` — non-PT plans never grant sessions, and a cancelled
    membership is dead regardless of dates.

    Args:
        customer: The customer whose memberships are considered.

    Returns:
        The latest non-cancelled PT ``Membership`` (plan joined), or ``None``.
    """
    return (
        customer.memberships.exclude(status="cancelled")
        .filter(plan__plan_type=MembershipPlan.PlanType.PT)
        .select_related("plan")
        .order_by("-end_date", "-id")
        .first()
    )


def _window_bounds(membership: Membership) -> tuple[datetime, datetime]:
    """Return tz-aware [start, end) datetimes spanning the membership window.

    ``scheduled_at`` is timezone-aware (USE_TZ) while the membership window is
    dates, so the dates are materialized in the project timezone — the same
    clock ``Membership.compute_status`` compares against.
    """
    tz = timezone.get_current_timezone()
    start = datetime.combine(membership.start_date, time.min, tzinfo=tz)
    end = datetime.combine(membership.end_date + timedelta(days=1), time.min, tzinfo=tz)
    return start, end


def count_redeemed_sessions(customer: Customer, membership: Membership) -> int:
    """Count completed + no-show sessions inside the membership's date window.

    Args:
        customer: The customer the sessions belong to.
        membership: The membership whose window bounds the count.

    Returns:
        Number of redeemed (completed or no-show) sessions in the window.
    """
    start, end = _window_bounds(membership)
    return TrainerSession.objects.filter(
        tenant_id=customer.tenant_id,
        customer=customer,
        status__in=TrainerSession.REDEEM_STATUSES,
        scheduled_at__gte=start,
        scheduled_at__lt=end,
    ).count()


def get_pt_entitlement(customer: Customer | None) -> PTPackEntitlement:
    """Compute the customer's PT session-pack state (single source of truth).

    Rules, in order (issue #52):
    1. No non-cancelled PT-plan membership → no pack, booking rejected.
    2. Membership past ``end_date`` (per ``Membership.compute_status``) →
       expired, booking rejected.
    3. ``plan.sessions_allowed is None`` → unlimited.
    4. ``remaining = sessions_allowed − redeemed``; booking requires > 0.

    Args:
        customer: The customer (``None`` → empty state, keeps call sites
            simple for users without a customer profile).

    Returns:
        The frozen :class:`PTPackEntitlement` for the customer.
    """
    if customer is None:
        return PTPackEntitlement(
            membership_id=None,
            plan_name=None,
            membership_status="none",
            end_date=None,
            sessions_allowed=None,
            redeemed=0,
            remaining=0,
            reason=PTPackReason.NO_ACTIVE_PT_MEMBERSHIP,
        )

    membership = get_active_pt_membership(customer)
    if membership is None:
        return PTPackEntitlement(
            membership_id=None,
            plan_name=None,
            membership_status="none",
            end_date=None,
            sessions_allowed=None,
            redeemed=0,
            remaining=0,
            reason=PTPackReason.NO_ACTIVE_PT_MEMBERSHIP,
        )

    plan = membership.plan
    status = membership.compute_status()
    if status != "active":
        return PTPackEntitlement(
            membership_id=membership.pk,
            plan_name=plan.name,
            membership_status=status,
            end_date=membership.end_date,
            sessions_allowed=plan.sessions_allowed,
            redeemed=0,
            remaining=0,
            reason=PTPackReason.PT_MEMBERSHIP_EXPIRED,
        )

    redeemed = count_redeemed_sessions(customer, membership)
    if plan.sessions_allowed is None:
        return PTPackEntitlement(
            membership_id=membership.pk,
            plan_name=plan.name,
            membership_status=status,
            end_date=membership.end_date,
            sessions_allowed=None,
            redeemed=redeemed,
            remaining=None,
            reason=PTPackReason.OK,
        )

    remaining = plan.sessions_allowed - redeemed
    return PTPackEntitlement(
        membership_id=membership.pk,
        plan_name=plan.name,
        membership_status=status,
        end_date=membership.end_date,
        sessions_allowed=plan.sessions_allowed,
        redeemed=redeemed,
        remaining=remaining,
        reason=PTPackReason.OK if remaining > 0 else PTPackReason.PACK_EXHAUSTED,
    )
