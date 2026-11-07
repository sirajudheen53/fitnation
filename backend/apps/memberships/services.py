"""Membership write-path guards.

Issue #104 (owner decision, 2026-11-07): BLOCK the overlapping membership —
no auto-supersede. A member must never hold two ACTIVE memberships whose
periods overlap; when a write (create, renew, plan/date edit) would produce
one, the API rejects it with a 400 naming the conflicting membership so the
desk can cancel or adjust that row instead.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from django.utils import timezone
from rest_framework import serializers

from apps.memberships.models import Membership

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.memberships.models import MembershipPlan
    from apps.tenants.models import Tenant

#: DRF error code carried on the conflict message, in the style of
#: ``phone_already_registered`` (the code is not part of the rendered body).
MEMBERSHIP_OVERLAP_CODE = "membership_period_overlap"


def assert_no_membership_overlap(
    *,
    tenant: Tenant,
    customer: Customer,
    start_date,
    end_date,
    exclude_pk: int | None = None,
) -> None:
    """Reject a membership period that overlaps the member's ACTIVE memberships.

    Overlap is inclusive on both boundary dates: a row sharing even one day
    with an ACTIVE membership conflicts (use the renewal action to extend a
    membership rather than creating a successor that starts on its end date).
    Cancelled and expired rows do not count, and a period ending before today
    is skipped entirely — ``save()`` computes status from dates, so such a
    row is born/stays expired and can never hold ACTIVE status.

    Args:
        tenant: The tenant whose memberships are considered.
        customer: The member whose memberships are checked.
        start_date: Candidate period start (inclusive).
        end_date: Candidate period end (inclusive).
        exclude_pk: Membership pk to skip — the row being renewed or edited
            is not a conflict against itself.

    Raises:
        serializers.ValidationError: With ``non_field_errors`` carrying code
            ``membership_period_overlap`` and a message citing the conflicting
            membership's id, plan, and period.
    """
    if end_date is None or end_date < timezone.localdate():
        return
    conflict = (
        Membership.objects.for_tenant(tenant)
        .filter(
            customer=customer,
            status=Membership.Status.ACTIVE,
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        .exclude(pk=exclude_pk)
        .select_related("plan")
        .order_by("id")
        .first()
    )
    if conflict is None:
        return
    raise serializers.ValidationError(
        {
            "non_field_errors": [
                serializers.ErrorDetail(
                    (
                        f"This member already has an active membership #{conflict.pk} "
                        f"({conflict.plan.name}, {conflict.start_date.isoformat()} to "
                        f"{conflict.end_date.isoformat()}) overlapping these dates. "
                        "Cancel or edit that membership first."
                    ),
                    code=MEMBERSHIP_OVERLAP_CODE,
                )
            ]
        },
    )


def prorated_upgrade_suggestion(
    *,
    current_plan: MembershipPlan,
    new_plan: MembershipPlan,
    end_date,
    today=None,
) -> dict:
    """Compute the DISPLAY-ONLY upgrade amount suggestion for a membership (#105).

    The suggestion is the plan price difference prorated over the remaining
    days of the paid window: ``(new_plan.price - current_plan.price)`` spread
    across the CURRENT plan's ``duration_days`` gives a per-day difference,
    multiplied by the inclusive remaining days (a membership ending today
    still has one day left, matching the #104 inclusive overlap rule). It is
    advisory only — the desk can override the amount at capture time and the
    entered amount is what gets recorded.

    Args:
        current_plan: The plan the membership is on now.
        new_plan: The (higher-priced) plan being upgraded to.
        end_date: The membership's end date (unchanged by the upgrade).
        today: Override "today" (defaults to the local date); for tests.

    Returns:
        ``{"remaining_days": int, "suggested_amount": Decimal}`` with the
        amount quantized to 2 decimal places (ROUND_HALF_UP). Zero remaining
        days yields a zero suggestion; a zero-day current plan falls back to
        the full price difference instead of dividing by zero.
    """
    if today is None:
        today = timezone.localdate()
    remaining_days = max(0, (end_date - today).days + 1)
    price_diff = Decimal(new_plan.price) - Decimal(current_plan.price)
    if remaining_days == 0:
        suggested = Decimal("0.00")
    elif current_plan.duration_days:
        per_day = price_diff / Decimal(current_plan.duration_days)
        suggested = (per_day * remaining_days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        suggested = price_diff.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"remaining_days": remaining_days, "suggested_amount": suggested}
