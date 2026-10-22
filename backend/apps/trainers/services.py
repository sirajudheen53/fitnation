"""Trainer session business logic (issue #52).

All writes go through this module: booking enforces the PT pack entitlement
and the per-trainer overlap guard under a trainer row lock; status
transitions feed ``TrainerPerformance.sessions_completed`` (+1 on
completed/no-show, −1 when a redeemed session is cancelled back out).
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.trainers.models import TrainerPerformance, TrainerSession
from apps.trainers.selectors import PTPackReason, get_pt_entitlement
from apps.users.models import Trainer

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.tenants.models import Tenant

#: Overlap-candidate lookback bound: no session may exceed the model's
#: duration check constraint, so any overlapping slot starts within this window.
_MAX_DURATION = timedelta(minutes=480)

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    TrainerSession.Status.BOOKED: {
        TrainerSession.Status.COMPLETED,
        TrainerSession.Status.NO_SHOW,
        TrainerSession.Status.CANCELLED,
    },
    # Completed/no-show already redeemed a credit — cancelling restores it
    # (redemption is a derived count, so the rollback is automatic).
    TrainerSession.Status.COMPLETED: {TrainerSession.Status.CANCELLED},
    TrainerSession.Status.NO_SHOW: {TrainerSession.Status.CANCELLED},
    # Terminal — book a new session instead.
    TrainerSession.Status.CANCELLED: set(),
}


class SessionBookingError(APIException):
    """409 raised when a booking violates the entitlement or the trainer's slot."""

    status_code = 409
    default_detail = "Session booking rejected."
    default_code = "session_booking_conflict"


def _conflict(reason: str, detail: str, **extra: object) -> SessionBookingError:
    """Build a 409 carrying a machine-readable ``reason``."""
    return SessionBookingError({"reason": reason, "detail": detail, **extra})


def assert_no_slot_conflict(
    *,
    tenant: Tenant,
    trainer: Trainer,
    scheduled_at,
    duration_minutes: int,
    exclude_pk: int | None = None,
) -> None:
    """Raise 409 when the trainer already holds a non-cancelled overlapping slot.

    Args:
        tenant: The tenant whose sessions are considered.
        trainer: The trainer whose calendar is checked.
        scheduled_at: Candidate slot start (tz-aware).
        duration_minutes: Candidate slot length in minutes.
        exclude_pk: Session pk to skip (reschedule path).

    Raises:
        SessionBookingError: With ``reason="trainer_slot_conflict"`` on overlap.
    """
    # Self-contained atomic block: the row locks are only legal inside a
    # transaction (view PATCH path calls this directly, outside any wrapper).
    with transaction.atomic():
        # Lock the trainer row itself so concurrent bookings for the same
        # trainer serialize (session-row locks alone miss empty-slot races).
        Trainer.objects.select_for_update().get(pk=trainer.pk)
        slot_end = scheduled_at + timedelta(minutes=duration_minutes)
        # Any overlapping session must start before the candidate ends and
        # within the max-duration lookback of its start. Cancelled sessions
        # free the slot.
        candidates = (
            TrainerSession.objects.select_for_update()
            .filter(
                tenant=tenant,
                trainer=trainer,
                scheduled_at__gt=scheduled_at - _MAX_DURATION,
                scheduled_at__lt=slot_end,
            )
            .exclude(status=TrainerSession.Status.CANCELLED)
            .exclude(pk=exclude_pk)
        )
        for session in candidates:
            if session.scheduled_at < slot_end and session.ends_at > scheduled_at:
                raise _conflict(
                    "trainer_slot_conflict",
                    (
                        f"Trainer already has a session from "
                        f"{timezone.localtime(session.scheduled_at):%Y-%m-%d %H:%M} "
                        f"to {timezone.localtime(session.ends_at):%Y-%m-%d %H:%M}."
                    ),
                )


def book_session(
    *,
    tenant: Tenant,
    trainer: Trainer,
    customer: Customer,
    scheduled_at,
    duration_minutes: int = 60,
    branch=None,
    notes: str = "",
) -> TrainerSession:
    """Book a new PT session after entitlement and overlap gates.

    Args:
        tenant: The booking tenant.
        trainer: The trainer to book.
        customer: The customer the session is for.
        scheduled_at: Slot start (tz-aware).
        duration_minutes: Slot length in minutes (1–480).
        branch: Optional branch context.
        notes: Free-text notes.

    Returns:
        The created ``TrainerSession`` (status ``booked``).

    Raises:
        SessionBookingError: 409 when the customer has no active PT
            membership, it is expired, the pack is exhausted, or the trainer's
            slot overlaps an existing booked session.
    """
    pack = get_pt_entitlement(customer)
    if pack.membership_status == "none":
        raise _conflict(
            PTPackReason.NO_ACTIVE_PT_MEMBERSHIP,
            "Customer has no active PT membership; sell a 'pt' plan before booking sessions.",
            remaining=0,
        )
    if pack.membership_status != "active":
        raise _conflict(
            PTPackReason.PT_MEMBERSHIP_EXPIRED,
            f"Customer's PT membership expired on {pack.end_date.isoformat()}.",
            remaining=0,
        )
    if not pack.can_book:
        raise _conflict(
            PTPackReason.PACK_EXHAUSTED,
            f"Session pack exhausted ({pack.redeemed}/{pack.sessions_allowed} redeemed).",
            remaining=pack.remaining,
        )

    with transaction.atomic():
        assert_no_slot_conflict(
            tenant=tenant,
            trainer=trainer,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
        )
        return TrainerSession.objects.create(
            tenant=tenant,
            trainer=trainer,
            customer=customer,
            branch=branch,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            notes=notes,
            status=TrainerSession.Status.BOOKED,
        )


def transition_session(session: TrainerSession, target: str) -> TrainerSession:
    """Move a session through its lifecycle and feed the performance aggregate.

    Completed and no-show transitions feed ``+1`` into the trainer's monthly
    ``TrainerPerformance.sessions_completed``; cancelling a session that had
    redeemed feeds ``−1`` (credit restored). Cancelled sessions never redeem.

    Args:
        session: The session to transition.
        target: Target status — one of ``completed`` / ``no_show`` /
            ``cancelled``.

    Returns:
        The refreshed session.

    Raises:
        ValidationError: 400 when the transition is not allowed.
    """
    allowed = _ALLOWED_TRANSITIONS.get(session.status, set())
    if target not in allowed:
        raise ValidationError(
            {"status": f"Cannot transition session from '{session.status}' to '{target}'."},
        )

    redeemed_before = session.is_redeemed
    session.status = target
    with transaction.atomic():
        session.save(update_fields=["status", "updated_at"])
        redeemed_after = session.is_redeemed
        if redeemed_after and not redeemed_before:
            _feed_performance(session, +1)
        elif redeemed_before and not redeemed_after:
            _feed_performance(session, -1)
    session.refresh_from_db()
    return session


def _feed_performance(session: TrainerSession, delta: int) -> None:
    """Apply ``delta`` to the trainer's monthly performance record (creating it)."""
    month = timezone.localtime(session.scheduled_at).date().replace(day=1)
    record, _created = TrainerPerformance.objects.get_or_create(
        tenant=session.tenant,
        trainer=session.trainer,
        month=month,
        defaults={"sessions_completed": max(delta, 0)},
    )
    if _created:
        return
    if delta > 0:
        TrainerPerformance.objects.filter(pk=record.pk).update(sessions_completed=F("sessions_completed") + delta)
    else:
        TrainerPerformance.objects.filter(pk=record.pk).update(
            sessions_completed=Greatest(F("sessions_completed") + delta, 0),
        )
