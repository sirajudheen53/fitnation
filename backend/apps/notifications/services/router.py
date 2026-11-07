"""Channel-aware outbound send policy (issue #66).

One place resolves how every outbound communication is delivered, per tenant
and per recipient:

1. WhatsApp — WATI when configured, then Gupshup.
2. MSG91 SMS — only where a platform template exists for the message type.
3. Email — last resort (real mailboxes only).
4. Otherwise — skipped + audited.

Recipient capability checks: WhatsApp/SMS need a phone; email needs a real
(non-synthetic) mailbox — phone-keyed OTP identities carry
``…@fitnation.local`` addresses no provider can deliver to, so a gym with
only WhatsApp configured still reaches every member. Every attempt is
recorded in ``NotificationLog`` with the semantic ``channel`` (whatsapp |
sms | email) and the ``provider`` (wati | gupshup | msg91 | sendgrid) that
carried it. Sends never raise — failures are returned and logged.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.conf import settings

from apps.notifications.models import NotificationLog
from apps.notifications.services.channels import (
    CHANNEL_EMAIL,
    CHANNEL_SMS,
    CHANNEL_WHATSAPP,
    OTP_CHANNEL_BY_SENDER,
    PROVIDER_GUPSHUP,
    PROVIDER_MSG91,
    PROVIDER_SENDGRID,
    PROVIDER_WATI,
    gupshup_template_status,
    normalize_msisdn,
    post_gupshup_template,
    post_gupshup_text,
    post_wati_template,
)
from apps.notifications.services.wati_service import build_message, post_wati_session_text
from apps.users.services import SYNTHETIC_EMAIL_DOMAIN

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)

# Re-exported for consumers of the policy (send services, invite service) —
# the canonical definitions live in channels.py next to the transports.
__all__ = [
    "CHANNEL_EMAIL",
    "CHANNEL_SMS",
    "CHANNEL_WHATSAPP",
    "OTP_CHANNEL_BY_SENDER",
    "PROVIDER_GUPSHUP",
    "PROVIDER_MSG91",
    "PROVIDER_SENDGRID",
    "PROVIDER_WATI",
    "WHATSAPP_TEMPLATE_NAMES",
    "WhatsAppAttempt",
    "gupshup_ready",
    "gupshup_template_approval",
    "is_emailable",
    "send_verification_message",
    "send_welcome_notification",
    "send_whatsapp_template",
    "wati_ready",
    "whatsapp_providers",
]

# Platform-wide approved WhatsApp template slugs (issue #66). The same names
# are approved once per tenant in each BSP console — mirrors the WATI
# convention, so ``fitnation_app_invite`` works identically over Gupshup.
WHATSAPP_TEMPLATE_NAMES: dict[str, str] = {
    "app_invite": "fitnation_app_invite",
    # Issue #72/#85: pending-payment nudge with a Razorpay payment link.
    # Gupshup template: body "Hi {{1}}, your payment of ₹{{2}} for {{3}} is
    # pending." + "Pay Now" CTA URL button "https://rzp.io/i/{{1}}" (WhatsApp
    # policy: links never ride body variables) — Gupshup positional params =
    # [customer_name, amount, gym_name, short_url_suffix]. WATI's template
    # inlines the whole link as its 4th body variable instead.
    "payment_link": "fitnation_payment_link",
    # Issue #98: the member/gym welcome — business-initiated (a brand-new
    # member has never messaged the gym, so no 24h session window exists and
    # freeform text can never deliver on either provider). The same 4
    # positional body params ride both BSP templates:
    # [customer_name, gym_name, plan_name, end_date].
    "welcome": "fitnation_welcome",
}


def wati_ready(tenant: Tenant) -> bool:
    """Whether the tenant's WATI leg can carry a send (enabled + keyed)."""
    return bool(tenant is not None and tenant.is_wati_enabled and tenant.wati_api_key)


def gupshup_ready(tenant: Tenant) -> bool:
    """Whether the tenant's Gupshup leg can carry a send.

    Gupshup needs all three credentials — without ``source``/``src.name`` the
    provider rejects every message, so a half-configured app counts as not
    ready rather than guaranteeing a failed send.
    """
    return bool(
        tenant is not None
        and tenant.is_gupshup_enabled
        and tenant.gupshup_api_key
        and tenant.gupshup_source
        and tenant.gupshup_app_name
    )


def whatsapp_providers(tenant: Tenant, *, ready_only: bool = False) -> list[str]:
    """The tenant's WhatsApp providers in policy order (WATI → Gupshup).

    Args:
        tenant: The sending tenant.
        ready_only: When ``True`` only fully-configured providers are
            returned; when ``False`` every *enabled* provider is (senders
            that distinguish "enabled but misconfigured" from "off" pass
            ``False`` and check readiness per leg).
    """
    providers: list[str] = []
    if tenant is not None and tenant.is_wati_enabled and (not ready_only or wati_ready(tenant)):
        providers.append(PROVIDER_WATI)
    if tenant is not None and tenant.is_gupshup_enabled and (not ready_only or gupshup_ready(tenant)):
        providers.append(PROVIDER_GUPSHUP)
    return providers


def gupshup_template_approval(
    tenant: Tenant,
    template_name: str,
    *,
    status_getter: Callable[[Any, str], str] | None = None,
) -> str:
    """The verifiable approval verdict for one template on the tenant's Gupshup leg.

    Gupshup 202-acks every ``/msg`` submit and silently drops the ones whose
    template is unapproved (issues #73/#74), so senders that must guarantee
    delivery gate the Gupshup leg on this check before firing. The verdict
    comes from
    :func:`apps.notifications.services.channels.gupshup_template_status`
    (Meta Graph → portal-key template list → env allow-list, issue #86);
    WATI needs no such gate — its API rejects unapproved templates with a
    real HTTP error.

    Cache semantics mirror the OTP sender's gate: only verified APPROVED
    verdicts are cached (same ``gupshup-tpl:<tenant>:<template>`` key family,
    ``GUPSHUP_TEMPLATE_CHECK_TTL``, default 30 min) so steady-state sends
    skip the status GET; blocking verdicts are never cached — approving the
    template in the console flips delivery on the very next send. Cache
    trouble must not block a send.

    Args:
        tenant: The sending tenant (its Gupshup app scopes the check).
        template_name: The platform-wide approved template slug.
        status_getter: Injectable verdict lookup (tests); defaults to the
            channels-module gate chain.

    Returns:
        ``"APPROVED"`` or the blocking verdict — a raw status word
        (``PENDING``/``REJECTED``/…) or ``""`` when no gate could verify.
    """
    from django.core.cache import cache

    cache_key = f"gupshup-tpl:{tenant.pk}:{template_name}"
    try:
        if cache.get(cache_key):
            return "APPROVED"
    except Exception:  # noqa: BLE001 - cache trouble must not block sends
        pass
    resolve = status_getter or gupshup_template_status
    verdict = str(resolve(tenant, template_name)).strip().upper()
    if verdict == "APPROVED":
        with contextlib.suppress(Exception):  # accounting must never block delivery
            cache.set(cache_key, True, timeout=int(getattr(settings, "GUPSHUP_TEMPLATE_CHECK_TTL", 1800)))
    return verdict


def is_emailable(email: str | None) -> bool:
    """Whether the address is a real, deliverable mailbox.

    Phone-keyed OTP identities get synthetic ``…@fitnation.local`` addresses
    (ADR-002) that no mailbox exists behind — they are never emailable, so
    the email leg is skipped and a messaging channel carries instead (the
    issue #66 "email is the last resort" rule).

    Args:
        email: The candidate address (may be blank).

    Returns:
        ``True`` only for a non-blank, non-synthetic address.
    """
    normalized = (email or "").strip().lower()
    return bool(normalized) and not normalized.endswith(SYNTHETIC_EMAIL_DOMAIN)


@dataclass(frozen=True)
class WhatsAppAttempt:
    """Outcome of trying the tenant's WhatsApp providers for one message.

    Attributes:
        provider: The provider that produced this outcome (the last one
            tried when everything failed, the delivering one on success).
        sent: Whether a provider accepted the message.
        message_id: The provider's message id, when reported (WATI).
        error: Transport/provider error text on failure.
        attempted: ``False`` when no provider was enabled/configured at all.
        failures: ``(provider, error)`` per failed leg, in try order — each
            attempted leg is auditable even when a later leg delivers.
    """

    provider: str = ""
    sent: bool = False
    message_id: str = ""
    error: str = ""
    attempted: bool = False
    failures: tuple[tuple[str, str], ...] = ()


def _wati_message_id(response: Any) -> str:
    """The WATI message id from a send response, ``""`` when unusable.

    Mirrors the parse in :func:`...wati_service.post_wati_session_text`
    (``messageId`` / ``id`` / ``result``); a non-JSON body must not turn a
    delivered message into a failed leg, so every parse trouble is swallowed.
    """
    with contextlib.suppress(Exception):
        data = response.json() if hasattr(response, "json") else {}
        if isinstance(data, dict):
            return str(data.get("messageId") or data.get("id") or data.get("result") or "")
    return ""


def send_whatsapp_template(
    tenant: Tenant,
    template_name: str,
    to_msisdn: str,
    template_params: list[str],
    *,
    gupshup_params: list[str] | None = None,
    providers: list[str] | None = None,
    poster: Callable[..., Any] | None = None,
) -> WhatsAppAttempt:
    """Try the tenant's WhatsApp providers in policy order (template form).

    The first provider that accepts the template wins; every failure is
    swallowed and traced on the returned attempt so callers can fall through
    to SMS/email and audit each leg without a raise.

    The two BSP templates of one name can differ in shape (issue #85):
    Gupshup may only reveal the link inside a CTA URL button (WhatsApp policy
    forbids bare links as body variables), so its positional params stop at
    the body variables — the button's URL-variable value is appended at send
    time per Gupshup's order-of-occurrence rule — while WATI templates inline
    the whole link as a body variable. Pass ``template_params`` for WATI and
    ``gupshup_params`` for Gupshup; the Gupshup leg falls back to
    ``template_params`` when the override is omitted.

    Args:
        tenant: The sending tenant (per-provider credentials).
        template_name: The platform-wide approved template slug.
        to_msisdn: Recipient in ``<country_code><number>`` form.
        template_params: Positional ``{{1}}…{{n}}`` template variables (WATI).
        gupshup_params: Override for the Gupshup leg (button-shaped templates).
        providers: Explicit provider order (tests / forced provider);
            defaults to every fully-configured provider, policy order.
        poster: Injectable HTTP post callable (tests).

    Returns:
        The :class:`WhatsAppAttempt` describing what happened.
    """
    order = providers if providers is not None else whatsapp_providers(tenant, ready_only=True)
    attempt = WhatsAppAttempt(attempted=bool(order))
    failures: list[tuple[str, str]] = []
    for provider in order:
        message_id = ""
        try:
            if provider == PROVIDER_WATI:
                response = post_wati_template(tenant, template_name, to_msisdn, template_params, poster=poster)
                message_id = _wati_message_id(response)
            elif provider == PROVIDER_GUPSHUP:
                post_gupshup_template(
                    tenant,
                    template_name,
                    to_msisdn,
                    template_params if gupshup_params is None else gupshup_params,
                    poster=poster,
                )
            else:  # defensive — unknown provider names never loop forever
                error = f"unknown WhatsApp provider {provider}"
                failures.append((provider, error))
                attempt = WhatsAppAttempt(provider, False, "", error, True, tuple(failures))
                continue
        except Exception as exc:  # noqa: BLE001 - fall through to the next provider
            logger.warning("WhatsApp %s template send failed: %s", provider, exc)
            failures.append((provider, str(exc)))
            attempt = WhatsAppAttempt(provider, False, "", str(exc), True, tuple(failures))
            continue
        return WhatsAppAttempt(provider, True, message_id, "", True, tuple(failures))
    return attempt


def send_welcome_notification(
    tenant: Tenant,
    customer: Customer | None,
    context_data: dict[str, Any] | None = None,
    *,
    to_phone: str | None = None,
    actor: Any = None,
    poster: Callable[..., Any] | None = None,
) -> NotificationLog:
    """Send the welcome over the approved WhatsApp templates (issue #98).

    The welcome is business-initiated — a brand-new member has never messaged
    the gym, so no 24-hour customer-service window exists and freeform
    session text can never deliver (#98). Both legs therefore ride the
    approved ``fitnation_welcome`` template via
    :func:`send_whatsapp_template` (the app-invite pattern, #85) with the
    same positional body params ``[customer_name, gym_name, plan_name,
    end_date]``. Freeform session text stays only on the settings-page test
    send, which targets a phone the owner controls.

    Audit semantics mirror
    :func:`apps.notifications.services.wati_service.send_notification`: one
    ``NotificationLog`` row per attempt — ``skipped`` when no channel is
    enabled or the recipient has no phone, ``failed`` with the last leg's
    error when every enabled leg failed (an enabled-but-misconfigured leg is
    a failed leg, not a silent skip), ``sent`` with the carrying provider.

    Args:
        tenant: The sending tenant (per-provider credentials).
        customer: The recipient member (``None`` for the vendor-provisioning
            welcome, which addresses ``to_phone`` directly).
        context_data: Template context — ``plan_name`` and ``end_date`` feed
            body params 3 and 4; ``phone`` only feeds the audit copy.
        to_phone: Explicit recipient, overriding the customer phone.
        actor: The staff user who triggered the send (audit trail).
        poster: Injectable HTTP post callable (tests).

    Returns:
        The created ``NotificationLog`` record.
    """
    context = context_data or {}
    context.setdefault("gym_name", tenant.name)
    context.setdefault("customer_name", customer.name if customer else "there")

    content = build_message("welcome", context)
    log = NotificationLog.objects.create(
        tenant=tenant,
        customer=customer,
        actor=actor,
        notification_type=NotificationLog.NotificationType.WELCOME,
        status=NotificationLog.Status.PENDING,
        content=content,
    )

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

    # Enabled-but-misconfigured legs are failed legs carrying the same error
    # copy send_notification records; the ready legs carry the send in policy
    # order. A FAILED row names the last *enabled* provider, ready or not.
    ready: list[str] = []
    last_error = ""
    for candidate in enabled:
        if candidate == PROVIDER_WATI:
            if not tenant.wati_api_key:
                last_error = "Wati API key is not configured"
                continue
        else:
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
        ready.append(candidate)

    # Issue #98: no CTA button on either BSP template (unlike the invite /
    # payment-link shapes), so both legs carry the identical 4 body params.
    params = [
        str(context.get("customer_name") or "there"),
        str(context.get("gym_name") or tenant.name),
        str(context.get("plan_name") or ""),
        str(context.get("end_date") or ""),
    ]
    attempt = send_whatsapp_template(
        tenant,
        WHATSAPP_TEMPLATE_NAMES["welcome"],
        normalize_msisdn(recipient, getattr(settings, "OTP_DEFAULT_COUNTRY_CODE", "91")),
        params,
        gupshup_params=params,
        providers=ready,
        poster=poster,
    )
    if attempt.sent:
        log.wati_message_id = attempt.message_id
        log.channel = CHANNEL_WHATSAPP
        log.provider = attempt.provider
        log.status = NotificationLog.Status.SENT
        log.save(update_fields=["wati_message_id", "channel", "provider", "status", "updated_at"])
        return log

    for _, error in attempt.failures:
        last_error = error
    log.channel = CHANNEL_WHATSAPP
    log.provider = enabled[-1]
    log.status = NotificationLog.Status.FAILED
    log.error_message = last_error
    log.save(update_fields=["channel", "provider", "status", "error_message", "updated_at"])
    return log


def send_verification_message(
    user,
    request: Any = None,
    *,
    poster: Callable[..., Any] | None = None,
) -> NotificationLog:
    """Deliver an email-verification link over the best available channel.

    Policy (issue #66): WhatsApp (WATI → Gupshup) when the user's tenant has
    a messaging channel and the user has a phone — a verification link is a
    URL and works identically over WhatsApp; email is the last resort and is
    attempted only when no messaging channel delivered. Synthetic
    ``…@fitnation.local`` addresses are never emailable.

    Every audited attempt lands in ``NotificationLog`` (type
    ``email_verification``). Accounts without a tenant (platform admins)
    have no channel config to consult; for them the email leg runs alone and
    the outcome is reported via logger plus an **unsaved** log instance
    (the audit table requires a tenant).

    Args:
        user: The recipient (token is created for them here).
        request: The HTTP request (builds the verification URL base).
        poster: Injectable WhatsApp HTTP post callable (tests).

    Returns:
        The ``NotificationLog`` describing the outcome (unsaved when the
        user has no tenant).
    """
    from apps.core.services.email import build_verification_url, send_verification_email

    tenant = getattr(user, "tenant", None)
    verify_url = build_verification_url(user, request)
    content = _verification_copy(tenant, user, verify_url)

    if tenant is None:
        sent = is_emailable(user.email) and send_verification_email(user, verify_url)
        if not sent:
            logger.warning("Verification for user %s could not be delivered (no tenant channel config)", user.pk)
        return NotificationLog(
            notification_type=NotificationLog.NotificationType.EMAIL_VERIFICATION,
            status=NotificationLog.Status.SENT if sent else NotificationLog.Status.SKIPPED,
            channel=CHANNEL_EMAIL if is_emailable(user.email) else "",
            provider=PROVIDER_SENDGRID,
            content=content,
        )

    log = NotificationLog.objects.create(
        tenant=tenant,
        notification_type=NotificationLog.NotificationType.EMAIL_VERIFICATION,
        status=NotificationLog.Status.PENDING,
        content=content,
    )

    to_phone = (getattr(user, "phone", "") or "").strip()
    whatsapp_error = ""
    if to_phone:
        # The verification link is a URL — it works identically over WhatsApp,
        # so the tenant's messaging channel carries it when one can.
        for provider in whatsapp_providers(tenant, ready_only=True):
            if provider == PROVIDER_WATI:
                message_id, error = post_wati_session_text(tenant, to_phone, content)
            else:
                try:
                    post_gupshup_text(
                        tenant,
                        normalize_msisdn(to_phone, getattr(settings, "OTP_DEFAULT_COUNTRY_CODE", "91")),
                        content,
                        poster=poster,
                    )
                    message_id, error = "", ""
                except Exception as exc:  # noqa: BLE001 - fall through to the next leg
                    message_id, error = "", str(exc)
            if error:
                whatsapp_error = error
                continue
            log.status = NotificationLog.Status.SENT
            log.channel = CHANNEL_WHATSAPP
            log.provider = provider
            log.wati_message_id = message_id
            log.save(update_fields=["status", "channel", "provider", "wati_message_id", "updated_at"])
            return log
    else:
        logger.info("No phone on user %s — verification goes straight to email", user.pk)

    if is_emailable(user.email):
        sent = send_verification_email(user, verify_url)
        log.status = NotificationLog.Status.SENT if sent else NotificationLog.Status.FAILED
        log.channel = CHANNEL_EMAIL
        log.provider = PROVIDER_SENDGRID
        log.error_message = "" if sent else (whatsapp_error or "Email delivery failed")
        log.save(update_fields=["status", "channel", "provider", "error_message", "updated_at"])
        return log

    log.status = NotificationLog.Status.SKIPPED
    log.error_message = whatsapp_error or "No messaging channel configured and no emailable address"
    log.save(update_fields=["status", "error_message", "updated_at"])
    return log


def _verification_copy(tenant, user, verify_url: str) -> str:
    """Human-readable verification copy (WhatsApp text + audit trail)."""
    return build_message(
        "email_verification",
        {
            "customer_name": (user.first_name or "").strip() or "there",
            "gym_name": tenant.name if tenant is not None else "FitNation",
            "verify_link": verify_url,
        },
    )
