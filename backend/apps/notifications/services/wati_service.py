"""Wati WhatsApp notification service.

Builds message content from per-type templates, dispatches to the tenant's Wati
endpoint (if enabled), and records every attempt in
:class:`~apps.notifications.models.NotificationLog`.

The HTTP transport is injectable (``send_notification(..., sender=...)``) so
tests can substitute a fake without network access. Multi-tenant isolation is
guaranteed by always using the tenant's own Wati configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from django.conf import settings

import requests

from apps.notifications.models import NotificationLog

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.tenants.models import Tenant


# Message templates per notification type. Context keys are substituted with
# ``str.format_map``; braces in the template itself are doubled where literal.
MESSAGE_TEMPLATES: dict[str, str] = {
    "check_in": "Hi {customer_name}, you've checked in at {gym_name}. Keep it up! 💪",
    "membership_expiry": (
        "Hi {customer_name}, your membership at {gym_name} expires on {expiry_date}. "
        "Renew now to continue your fitness journey."
    ),
    "workout_assigned": (
        "Hi {customer_name}, a new workout plan '{plan_name}' has been assigned to you "
        "at {gym_name}. Check your app for details."
    ),
    "payment_received": ("Hi {customer_name}, we've received your payment of ₹{amount} at {gym_name}. " "Thank you!"),
}

# Default Wati endpoint used when the tenant has not configured one.
DEFAULT_WATI_ENDPOINT = "https://api.wati.io/api/v1/sendSessionMessage"


def build_message(notification_type: str, context: dict[str, Any]) -> str:
    """Render a message from its template and context.

    Args:
        notification_type: One of the supported notification types.
        context: Values used to fill template placeholders.

    Returns:
        The rendered message string.
    """
    template = MESSAGE_TEMPLATES.get(notification_type, "")
    try:
        return template.format_map(context)
    except (KeyError, ValueError):
        # Fall back to the raw template if placeholders are missing.
        return template


def _default_sender() -> Callable[..., Any]:
    return requests.post


def send_notification(
    tenant: Tenant,
    customer: Customer | None,
    notification_type: str,
    context_data: dict[str, Any] | None = None,
    *,
    sender: Callable[..., Any] | None = None,
) -> NotificationLog:
    """Send a WhatsApp notification for a tenant, logging the attempt.

    Behavior:
    - If ``tenant.is_wati_enabled`` is False → log ``skipped`` and return.
    - If ``tenant.wati_endpoint`` is empty → fall back to the default endpoint.
    - On HTTP success (2xx) → log ``sent`` with the Wati message id.
    - On failure → log ``failed`` with the error message.

    Args:
        tenant: The tenant sending the notification.
        customer: The recipient customer (may be ``None``).
        notification_type: One of ``NotificationLog.NotificationType``.
        context_data: Template context values.
        sender: Injectable HTTP post callable (tests).

    Returns:
        The created ``NotificationLog`` record.
    """
    context = context_data or {}
    context.setdefault("gym_name", tenant.name)
    context.setdefault("customer_name", customer.name if customer else "there")

    content = build_message(notification_type, context)
    log = NotificationLog.objects.create(
        tenant=tenant,
        customer=customer,
        notification_type=notification_type,
        status=NotificationLog.Status.PENDING,
        content=content,
    )

    if not tenant.is_wati_enabled:
        log.status = NotificationLog.Status.SKIPPED
        log.error_message = "Wati is not enabled for this tenant"
        log.save(update_fields=["status", "error_message", "updated_at"])
        return log

    if not tenant.wati_api_key:
        log.status = NotificationLog.Status.FAILED
        log.error_message = "Wati API key is not configured"
        log.save(update_fields=["status", "error_message", "updated_at"])
        return log

    endpoint = tenant.wati_endpoint or DEFAULT_WATI_ENDPOINT
    payload: dict[str, Any] = {
        "sessionMessage": content,
        "to": customer.phone if customer else "",
    }
    headers = {"Authorization": tenant.wati_api_key}

    post = sender or _default_sender()
    try:
        response = post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=getattr(settings, "WATI_TIMEOUT", 10),
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - record any transport failure
        log.status = NotificationLog.Status.FAILED
        log.error_message = str(exc)
        log.save(update_fields=["status", "error_message", "updated_at"])
        return log

    data = response.json() if hasattr(response, "json") else {}
    log.wati_message_id = data.get("messageId") or data.get("id") or data.get("result", "")
    log.status = NotificationLog.Status.SENT
    log.save(update_fields=["wati_message_id", "status", "updated_at"])
    return log
