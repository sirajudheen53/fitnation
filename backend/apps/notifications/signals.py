"""Django signal receivers that trigger Wati notifications.

Each receiver is defensive: it swallows exceptions so a notification failure
never breaks the primary workflow that triggered it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.notifications.models import NotificationLog
from apps.notifications.services.wati_service import send_notification


@receiver(post_save, sender="attendance.AttendanceRecord")
def on_attendance_created(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    """Send a check-in notification when an attendance record is created."""
    if not created:
        return
    _try_send(
        instance.tenant,
        instance.customer,
        NotificationLog.NotificationType.CHECK_IN,
        {"customer_name": instance.customer.name},
    )


@receiver(post_save, sender="memberships.Membership")
def on_membership_saved(sender: Any, instance: Any, **kwargs: Any) -> None:
    """Send an expiry reminder when a membership is within 7 days of expiry."""
    if instance.end_date is None:
        return
    today = timezone.localdate()
    if instance.end_date < today:
        return
    if instance.end_date - today > timedelta(days=7):
        return
    _try_send(
        instance.tenant,
        instance.customer,
        NotificationLog.NotificationType.MEMBERSHIP_EXPIRY,
        {
            "customer_name": instance.customer.name,
            "expiry_date": instance.end_date.isoformat(),
        },
    )


@receiver(post_save, sender="workouts.WorkoutAssignment")
def on_workout_assigned(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    """Send a notification when a workout plan is assigned to a customer."""
    if not created:
        return
    plan_name = getattr(instance.workout_plan, "name", "New workout plan")
    _try_send(
        instance.tenant,
        instance.customer,
        NotificationLog.NotificationType.WORKOUT_ASSIGNED,
        {
            "customer_name": instance.customer.name,
            "plan_name": plan_name,
        },
    )


@receiver(post_save, sender="payments.Payment")
def on_payment_paid(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    """Send a receipt notification when a payment becomes paid/completed."""
    if instance.status not in (
        "completed",
        "paid",
        "success",
    ):
        return
    _try_send(
        instance.tenant,
        instance.customer,
        NotificationLog.NotificationType.PAYMENT_RECEIVED,
        {
            "customer_name": instance.customer.name,
            "amount": instance.amount,
        },
    )


def _try_send(
    tenant: Any,
    customer: Any,
    notification_type: str,
    context: dict[str, Any],
) -> None:
    """Dispatch a notification, swallowing exceptions so the caller is unaffected."""
    try:
        send_notification(tenant, customer, notification_type, context)
    except Exception:  # noqa: BLE001 - notifications must never break the workflow
        # The service logs failures itself; keep the signal side-effect free.
        pass
