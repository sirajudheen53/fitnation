"""Payment-link send service (issue #72).

For a pending payment: create a Razorpay payment link, then deliver its
URL to the member over the tenant's messaging channels — WhatsApp templates
first (WATI → Gupshup), MSG91 SMS second (platform config), email last
(SendGrid). Every attempt is audited in ``NotificationLog`` (type
``payment_link``) with the triggering actor, the semantic ``channel`` and the
``provider`` that carried it. Sends never raise — outcomes are returned as a
:class:`PaymentLinkResult` so the API layer can always respond.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import timezone

from apps.core.services.email import send_email
from apps.notifications.models import NotificationLog
from apps.notifications.services.channels import (
    CHANNEL_EMAIL,
    CHANNEL_SMS,
    CHANNEL_WHATSAPP,
    PROVIDER_GUPSHUP,
    PROVIDER_MSG91,
    normalize_msisdn,
    post_msg91_flow,
)
from apps.notifications.services.router import (
    WHATSAPP_TEMPLATE_NAMES,
    gupshup_template_approval,
    is_emailable,
    send_whatsapp_template,
    whatsapp_providers,
)
from apps.notifications.services.wati_service import build_message
from apps.payments import razorpay_service
from apps.payments.models import Payment

if TYPE_CHECKING:
    from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)

STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_ALREADY_SENT = "already_sent"
STATUS_NOT_PENDING = "not_pending"


@dataclass(frozen=True)
class PaymentLinkResult:
    """Outcome of one send-payment-link invocation.

    Attributes:
        status: One of ``sent`` / ``failed`` / ``skipped`` / ``already_sent`` /
            ``not_pending``.
        reason: Machine- (and human-) readable reason for non-sent outcomes.
        channel: Delivery channel used (``whatsapp`` | ``sms`` | ``email``).
        provider: The provider that carried the message (wati | gupshup |
            msg91 | sendgrid).
        payment_link_url: The Razorpay ``short_url`` (also returned on
            delivery failures so front-desk can copy it manually).
        log: The audit row for the final outcome.
        resend_allowed_after: When the cooldown window frees up a resend.
    """

    status: str
    reason: str | None = None
    channel: str | None = None
    provider: str | None = None
    payment_link_url: str | None = None
    log: NotificationLog | None = None
    resend_allowed_after: Any = None


def _render_content(tenant, payment: Payment, link_url: str) -> str:
    """Human-readable payment-link copy stored on the log (audit trail)."""
    return build_message(
        "payment_link",
        {
            "customer_name": payment.customer.name,
            "gym_name": tenant.name,
            "amount": payment.amount,
            "payment_link": link_url,
        },
    )


def _was_sent_within_cooldown(payment: Payment, cooldown_minutes: int) -> timedelta | None:
    """Remainder of the resend cooldown, or ``None`` when resending is free."""
    if payment.payment_link_sent_at is None or cooldown_minutes <= 0:
        return None
    allow_at = payment.payment_link_sent_at + timedelta(minutes=cooldown_minutes)
    remainder = allow_at - timezone.now()
    return remainder if remainder.total_seconds() > 0 else None


def _audit(
    tenant,
    payment: Payment,
    actor,
    notification_type: str,
    status: str,
    channel: str = "",
    provider: str = "",
    content: str = "",
    error: str = "",
) -> NotificationLog:
    """Write one audit row for a send attempt."""
    return NotificationLog.objects.create(
        tenant=tenant,
        customer=payment.customer,
        actor=actor,
        notification_type=notification_type,
        status=status,
        channel=channel,
        provider=provider,
        content=content,
        error_message=error,
    )


def send_payment_link(
    tenant: Tenant,
    payment: Payment,
    *,
    actor=None,
    poster: Callable[..., Any] | None = None,
    template_status_getter: Callable[[Any, str], str] | None = None,
) -> PaymentLinkResult:
    """Create a Razorpay payment link for a pending payment and deliver it.

    Delivery policy: tenant WhatsApp templates (WATI → Gupshup) → MSG91 SMS
    (needs ``MSG91_PAYMENT_LINK_TEMPLATE_ID``) → email (real mailboxes only,
    mirroring the issue #66 "email is last resort" rule). A resend within
    ``PAYMENT_LINK_RESEND_COOLDOWN_MINUTES`` of the last *successful* send is
    short-circuited to ``already_sent`` so support cannot spam links. The
    Gupshup WhatsApp leg fires only when ``fitnation_payment_link`` is
    verifiably APPROVED (issue #79) — an unverified template skips loudly
    with its own audit row instead of 202-acking into the void.

    Args:
        tenant: The sending tenant.
        payment: The pending payment (must belong to the tenant).
        actor: The staff user triggering the send (audit trail).
        poster: Injectable WhatsApp/SMS HTTP post callable (tests).
        template_status_getter: Injectable Gupshup template-approval lookup
            (tests); defaults to the channels-module gate chain (issue #79).

    Returns:
        The :class:`PaymentLinkResult` describing what happened.
    """
    if payment.status != Payment.Status.PENDING:
        return PaymentLinkResult(status=STATUS_NOT_PENDING, reason="Payment is not pending")

    cooldown_minutes = int(getattr(settings, "PAYMENT_LINK_RESEND_COOLDOWN_MINUTES", 10))
    remainder = _was_sent_within_cooldown(payment, cooldown_minutes)
    if remainder is not None:
        return PaymentLinkResult(
            status=STATUS_ALREADY_SENT,
            reason="A payment link was sent recently. Retry after the cooldown.",
            resend_allowed_after=timezone.now() + remainder,
        )

    customer = payment.customer
    phone = (customer.phone or "").strip()
    email_ok = is_emailable(customer.email)
    if not phone and not email_ok:
        return PaymentLinkResult(
            status=STATUS_SKIPPED,
            reason="The customer has no phone number or a usable email address",
        )

    try:
        link = razorpay_service.create_payment_link(tenant, payment)
    except razorpay_service.RazorpayError as exc:
        logger.warning("Payment link creation failed for tenant %s: %s", tenant.pk, exc)
        log = _audit(
            tenant,
            payment,
            actor,
            NotificationLog.NotificationType.PAYMENT_LINK,
            NotificationLog.Status.FAILED,
            error=str(exc),
        )
        return PaymentLinkResult(status=STATUS_FAILED, reason=str(exc), log=log)

    link_url = link.get("short_url", "")
    link_id = link.get("id", "")
    payment.razorpay_payment_link_id = link_id
    payment.save(update_fields=["razorpay_payment_link_id", "updated_at"])

    content = _render_content(tenant, payment, link_url)

    def _log(
        status: str,
        channel: str = "",
        provider: str = "",
        error: str = "",
    ) -> NotificationLog:
        return _audit(
            tenant,
            payment,
            actor,
            NotificationLog.NotificationType.PAYMENT_LINK,
            status,
            channel=channel,
            provider=provider,
            content=content,
            error=error,
        )

    # WhatsApp legs in policy order (WATI → Gupshup) when the member has a
    # phone; every attempted leg that fails leaves its own audit row. The ₹
    # sign sits in the template body ({{2}} carries the raw amount) — BSP
    # consoles approve plain-text params, not symbols. Per issue #85 the two
    # BSP templates differ in shape: WATI's template inlines the whole link
    # as its 4th body variable; Gupshup's carries the link only inside the
    # "Pay Now" CTA URL button (fixed Razorpay prefix), whose positional
    # params are the 3 body variables + the link suffix. A non-Razorpay-
    # shaped link passes through whole (loudly warned in the helper).
    whatsapp_error = ""
    if phone:
        template_name = WHATSAPP_TEMPLATE_NAMES["payment_link"]
        providers = whatsapp_providers(tenant, ready_only=True)
        # Issue #79: the Gupshup leg is gated on the template being verifiably
        # APPROVED — the provider 202-acks unapproved sends and silently drops
        # them, so an unverified template steps aside with its own loud audit
        # row instead of reporting a "sent" that would never deliver (mirrors
        # the OTP sender's gate). WATI needs no gate: unapproved templates
        # fail there with a real HTTP error.
        gate_error = ""
        if PROVIDER_GUPSHUP in providers:
            verdict = gupshup_template_approval(tenant, template_name, status_getter=template_status_getter)
            if verdict != "APPROVED":
                providers = [name for name in providers if name != PROVIDER_GUPSHUP]
                gate_error = (
                    f"Gupshup template '{template_name}' is not approved for this app "
                    f"(status: {verdict or 'unverifiable'}) — the provider accepts but would never deliver"
                )
                logger.warning("Payment-link WhatsApp send skipped: %s", gate_error)
                _log(NotificationLog.Status.SKIPPED, CHANNEL_WHATSAPP, provider=PROVIDER_GUPSHUP, error=gate_error)
        params = [customer.name or "there", str(payment.amount), tenant.name, link_url]
        attempt = send_whatsapp_template(
            tenant,
            template_name,
            normalize_msisdn(phone),
            params,
            gupshup_params=[*params[:3], razorpay_service.payment_link_button_suffix(link_url)],
            providers=providers,
            poster=poster,
        )
        for provider, error in attempt.failures:
            logger.warning("%s payment-link send failed for payment %s: %s", provider, payment.pk, error)
            _log(NotificationLog.Status.FAILED, CHANNEL_WHATSAPP, provider=provider, error=error)
        if attempt.sent:
            log = _log(NotificationLog.Status.SENT, CHANNEL_WHATSAPP, provider=attempt.provider)
            _stamp_sent(payment)
            return PaymentLinkResult(
                status=STATUS_SENT,
                channel=CHANNEL_WHATSAPP,
                provider=attempt.provider,
                payment_link_url=link_url,
                log=log,
            )
        whatsapp_error = next((error for _, error in attempt.failures), "") or gate_error

    # SMS leg — platform MSG91 template (WhatsApp is off or both legs failed).
    sms_template_id = getattr(settings, "MSG91_PAYMENT_LINK_TEMPLATE_ID", "")
    if sms_template_id and getattr(settings, "MSG91_AUTH_KEY", "") and phone:
        try:
            post_msg91_flow(
                [
                    {
                        "mobiles": normalize_msisdn(phone),
                        "NAME": customer.name or "there",
                        "GYM": tenant.name,
                        "AMOUNT": str(payment.amount),
                        "LINK": link_url,
                    }
                ],
                sms_template_id,
                poster=poster,
            )
        except Exception as exc:  # noqa: BLE001 - fall through to the email leg
            logger.warning("SMS payment-link send failed for payment %s: %s", payment.pk, exc)
            _log(NotificationLog.Status.FAILED, CHANNEL_SMS, provider=PROVIDER_MSG91, error=str(exc))
        else:
            log = _log(NotificationLog.Status.SENT, CHANNEL_SMS, provider=PROVIDER_MSG91)
            _stamp_sent(payment)
            return PaymentLinkResult(
                status=STATUS_SENT,
                channel=CHANNEL_SMS,
                provider=PROVIDER_MSG91,
                payment_link_url=link_url,
                log=log,
            )

    # Email leg — last resort, real mailboxes only (issue #66 policy).
    if email_ok:
        sent = send_email(
            customer.email.strip(),
            f"Your {tenant.name} payment is pending",
            f"<p>{content}</p>",
            content,
        )
        if sent:
            log = _log(NotificationLog.Status.SENT, CHANNEL_EMAIL, provider="sendgrid")
            _stamp_sent(payment)
            return PaymentLinkResult(
                status=STATUS_SENT,
                channel=CHANNEL_EMAIL,
                provider="sendgrid",
                payment_link_url=link_url,
                log=log,
            )
        whatsapp_error = whatsapp_error or "Email delivery failed"

    error = whatsapp_error or "No messaging channel is configured for this tenant"
    log = _log(NotificationLog.Status.FAILED, "", error=error)
    return PaymentLinkResult(
        status=STATUS_FAILED,
        reason=error,
        payment_link_url=link_url,
        log=log,
    )


def _stamp_sent(payment: Payment) -> None:
    """Record a successful send for the resend-cooldown guard."""
    payment.payment_link_sent_at = timezone.now()
    payment.save(update_fields=["payment_link_sent_at", "updated_at"])
