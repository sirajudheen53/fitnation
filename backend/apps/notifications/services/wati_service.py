"""WhatsApp notification router (WATI → Gupshup, issue #66).

Builds message content from per-type templates, then dispatches over the
tenant's configured WhatsApp channels in policy order — WATI first (the
original per-tenant BSP), Gupshup second — and records every attempt in
:class:`~apps.notifications.models.NotificationLog` with the semantic
``channel`` and the ``provider`` that carried it.

The HTTP transports are injectable (``send_notification(..., sender=...,
poster=...)``) so tests can substitute fakes without network access.
Multi-tenant isolation is guaranteed by always using the tenant's own
channel configuration.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from django.conf import settings

import requests

from apps.notifications.models import NotificationLog
from apps.notifications.services.channels import (
    CHANNEL_WHATSAPP,
    PROVIDER_GUPSHUP,
    PROVIDER_WATI,
    normalize_msisdn,
    post_gupshup_text,
)

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
    # FBOS-011 §5.2 / onboarding-design §3.5: rendered copy stored on the
    # NotificationLog so the audit trail is human-readable. The actual WATI
    # sends for these types use APPROVED TEMPLATE messages (variable params),
    # not session messages — see invite_service / apps.users.otp.
    "welcome": (
        "Welcome to {gym_name}, {customer_name}! 🎉 Your {plan_name} membership is active until {end_date}. "
        "Install the FitNation app and sign in with {phone} to get your plans. See you at the gym! 💪"
    ),
    "app_invite": (
        "Hi {customer_name}! Welcome to {gym_name} 🎉 Your {plan_name} membership is active. "
        "Get your workout & diet plans, check-in QR and progress tracking in the FitNation app: {invite_link}"
    ),
    # Issue #66: the email-verification link rides the member's WhatsApp when
    # the gym has a messaging channel — a link works identically over either.
    "email_verification": (
        "Hi {customer_name}, please verify your email to finish setting up your {gym_name} account: "
        "{verify_link} The link is valid for 24 hours."
    ),
    # Issue #72/#85: pending-payment nudge with a Razorpay payment link.
    # The WhatsApp send is the approved fitnation_payment_link template —
    # body {{1}}={{customer_name}}, {{2}}={{amount}}, {{3}}={{gym_name}} plus
    # a "Pay Now" CTA URL button on the fixed Razorpay prefix (the link
    # suffix is the button's variable; WATI templates inline the whole link
    # as their 4th body variable instead). This entry renders the
    # human-readable audit copy (and the email-leg fallback), which must
    # still carry the URL.
    "payment_link": (
        "Hi {customer_name}, your payment of ₹{amount} for {gym_name} is pending. "
        "Tap Pay Now to pay securely online: {payment_link}"
    ),
}

# WATI approved template names (one-time approval per WATI account; fixed
# platform-wide — a tenant wanting custom copy approves the same template
# name in their own WATI console).
WATI_TEMPLATE_NAMES: dict[str, str] = {
    "app_invite": "fitnation_app_invite",
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


def post_wati_session_text(
    tenant: Tenant,
    to_phone: str,
    text: str,
    *,
    sender: Callable[..., Any] | None = None,
) -> tuple[str, str]:
    """POST one freeform session-window message via the tenant's WATI endpoint.

    Returns:
        ``(message_id, error)`` — ``error`` is empty on success. Kept in this
        module (with its ``requests.post`` default) so tests keep mocking the
        WATI transport here.
    """
    endpoint = tenant.wati_endpoint or DEFAULT_WATI_ENDPOINT
    post = sender or _default_sender()
    try:
        response = post(
            endpoint,
            json={"sessionMessage": text, "to": to_phone},
            headers={"Authorization": tenant.wati_api_key},
            timeout=getattr(settings, "WATI_TIMEOUT", 10),
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - the caller records the failure
        return "", str(exc)
    data = response.json() if hasattr(response, "json") else {}
    return (data.get("messageId") or data.get("id") or data.get("result", "")), ""


def send_notification(
    tenant: Tenant,
    customer: Customer | None,
    notification_type: str,
    context_data: dict[str, Any] | None = None,
    *,
    to_phone: str | None = None,
    actor: Any = None,
    sender: Callable[..., Any] | None = None,
    poster: Callable[..., Any] | None = None,
    provider: str | None = None,
) -> NotificationLog:
    """Send a WhatsApp notification for a tenant, logging the attempt.

    Channel policy (issue #66): the message rides the tenant's WhatsApp
    channels in order — WATI when enabled, then Gupshup. A failed provider
    falls through to the next one; when none delivers, the attempt is logged
    ``failed`` (or ``skipped`` when no channel is enabled at all — these
    types have no SMS/email template, so there is no further leg).

    Behavior:
    - No WhatsApp channel enabled → log ``skipped``.
    - Recipient has no phone → log ``skipped`` (capability check).
    - A provider enabled but misconfigured → counts as a failed leg (no
      HTTP call), recorded in the log.
    - On provider success (2xx) → log ``sent`` with channel + provider.
    - ``provider`` forces one leg (settings-page test send: test the chosen
      provider, never silently succeed via the other).

    Args:
        tenant: The tenant sending the notification.
        customer: The recipient customer (may be ``None``).
        notification_type: One of ``NotificationLog.NotificationType``.
        context_data: Template context values.
        to_phone: Explicit recipient for sends without a customer record
            (e.g. the settings-page test send). Overrides the customer phone.
        actor: The staff user who triggered the send (audit trail).
        sender: Injectable WATI session-post callable (tests).
        poster: Injectable Gupshup HTTP post callable (tests).
        provider: Force ``"wati"`` or ``"gupshup"`` (default: policy order).

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
        actor=actor,
        notification_type=notification_type,
        status=NotificationLog.Status.PENDING,
        content=content,
    )

    if provider is not None:
        enabled = [provider] if getattr(tenant, f"is_{provider}_enabled", False) else []
        if not enabled:
            name = "Wati" if provider == PROVIDER_WATI else "Gupshup"
            log.status = NotificationLog.Status.SKIPPED
            log.error_message = f"{name} is not enabled for this tenant"
            log.save(update_fields=["status", "error_message", "updated_at"])
            return log
    else:
        enabled = [name for name in (PROVIDER_WATI, PROVIDER_GUPSHUP) if getattr(tenant, f"is_{name}_enabled", False)]
        if not enabled:
            log.status = NotificationLog.Status.SKIPPED
            log.error_message = "No WhatsApp channel is enabled for this tenant (Wati and Gupshup are both not enabled)"
            log.save(update_fields=["status", "error_message", "updated_at"])
            return log

    recipient = (to_phone or (customer.phone if customer else "") or "").strip()
    if not recipient:
        log.status = NotificationLog.Status.SKIPPED
        log.error_message = "No recipient phone for this notification"
        log.save(update_fields=["status", "error_message", "updated_at"])
        return log

    last_provider = enabled[-1]
    last_error = ""
    for candidate in enabled:
        if candidate == PROVIDER_WATI:
            if not tenant.wati_api_key:
                last_error = "Wati API key is not configured"
                continue
            message_id, error = post_wati_session_text(tenant, recipient, content, sender=sender)
            if error:
                last_error = error
                continue
            log.wati_message_id = message_id
            log.channel = CHANNEL_WHATSAPP
            log.provider = PROVIDER_WATI
            log.status = NotificationLog.Status.SENT
            log.save(update_fields=["wati_message_id", "channel", "provider", "status", "updated_at"])
            return log

        # Gupshup leg — needs all three credentials or the provider would
        # reject every message; treat a half-configured app as a failed leg.
        missing = next(
            (
                label
                for label, value in (
                    ("API key", tenant.gupshup_api_key),
                    ("source number", tenant.gupshup_source),
                    ("app name", tenant.gupshup_app_name),
                )
                if not value
            ),
            "",
        )
        if missing:
            last_error = f"Gupshup {missing} is not configured"
            continue
        try:
            post_gupshup_text(
                tenant,
                normalize_msisdn(recipient, getattr(settings, "OTP_DEFAULT_COUNTRY_CODE", "91")),
                content,
                poster=poster,
            )
        except Exception as exc:  # noqa: BLE001 - fall through to the next provider
            last_error = str(exc)
            continue
        log.channel = CHANNEL_WHATSAPP
        log.provider = PROVIDER_GUPSHUP
        log.status = NotificationLog.Status.SENT
        log.save(update_fields=["channel", "provider", "status", "updated_at"])
        return log

    log.channel = CHANNEL_WHATSAPP
    log.provider = last_provider
    log.status = NotificationLog.Status.FAILED
    log.error_message = last_error
    log.save(update_fields=["channel", "provider", "status", "error_message", "updated_at"])
    return log
