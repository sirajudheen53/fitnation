"""App invite service — WhatsApp (WATI → Gupshup) first, MSG91 SMS fallback
(FBOS-011 §5, issue #66).

Every invocation is audited as a ``NotificationLog`` row (type ``app_invite``,
with the triggering ``actor``, the delivery ``channel`` and the ``provider``
that carried it). Sends never raise — transport failures are recorded and
returned as statuses so an onboarding flow or a front-desk resend can always
complete.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.notifications.models import NotificationLog
from apps.notifications.services.channels import normalize_msisdn, post_msg91_flow
from apps.notifications.services.router import (
    CHANNEL_SMS,
    CHANNEL_WHATSAPP,
    PROVIDER_MSG91,
    WHATSAPP_TEMPLATE_NAMES,
    send_whatsapp_template,
)
from apps.notifications.services.wati_service import build_message

logger = logging.getLogger(__name__)

# Outcome statuses (the API contract — FBOS-011 §5.1).
STATUS_SENT = "sent"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_ALREADY_SENT = "already_sent"

# Reasons.
REASON_FLAG_OFF = "flag_off"
REASON_PLAN_EXCLUDES_APP = "plan_excludes_app"
REASON_WATI_NOT_CONFIGURED = "wati_not_configured"
REASON_DAILY_LIMIT = "daily_limit_reached"


@dataclass(frozen=True)
class AppInviteResult:
    """Outcome of one invite invocation.

    Attributes:
        status: One of ``sent`` / ``skipped`` / ``failed`` /
            ``not_applicable`` / ``already_sent``.
        reason: Machine-readable reason for non-sent outcomes (``flag_off``,
            ``plan_excludes_app``, ``wati_not_configured``,
            ``daily_limit_reached``), ``None`` when sent.
        channel: Delivery channel used (``whatsapp`` | ``sms``), when sent.
        log: The audit row (``None`` for dedupe short-circuits and caps).
        sent_at: When the delivered/previous invite was sent.
        resend_allowed_after: When the 24h dedupe window frees up.
    """

    status: str
    reason: str | None = None
    channel: str | None = None
    log: NotificationLog | None = None
    sent_at: Any = None
    resend_allowed_after: Any = None


def build_app_invite_links(tenant) -> dict[str, str]:
    """Build the gym-anchored invite links (FBOS-011 §5.4).

    The tappable WhatsApp/SMS link is the App Link (prong 1) — it survives
    Play install→open together with the Play referrer link (prong 2) and the
    human gym code (prong 3). The anchor is only the tenant uuid: it leaks
    nothing (the public lookup returns uuid + display name only), so no
    token is needed.

    Args:
        tenant: The gym the link anchors to.

    Returns:
        ``{"web", "scheme", "play"}`` — https App Link, custom scheme, and
        the Play Store URL carrying the install referrer.
    """
    web_base = getattr(settings, "APP_INVITE_WEB_BASE", "https://app.yougetfitwithus.com").rstrip("/")
    scheme = getattr(settings, "APP_INVITE_SCHEME", "fitnation")
    package = getattr(settings, "ANDROID_PACKAGE_NAME", "com.getfitwithus.app")
    return {
        "web": f"{web_base}/g/{tenant.uuid}",
        "scheme": f"{scheme}://g/{tenant.uuid}",
        "play": f"https://play.google.com/store/apps/details?id={package}&referrer=gym%3D{tenant.uuid}",
    }


def _latest_membership(customer):
    """The customer's live membership for plan context (may be ``None``)."""
    from apps.memberships.selectors import get_latest_membership

    return get_latest_membership(customer)


def _invite_not_applicable_reason(tenant, membership) -> str | None:
    """Return the not-applicable reason, or ``None`` when an invite may go out.

    Args:
        tenant: The tenant (per-tenant rollout flag, FBOS-011 D10).
        membership: The customer's latest membership (or ``None``).
    """
    if not ((tenant.features or {}).get("app_access")):
        return REASON_FLAG_OFF
    if membership is not None and not membership.plan.includes_app_access:
        return REASON_PLAN_EXCLUDES_APP
    return None


def _sent_invite_within_window(customer, window_hours: int):
    """Return the latest ``sent`` invite log inside the dedupe window.

    Scoped to the customer's own gym, so one gym's invite history can never
    suppress another gym's invite to the same member (multi-tenant
    isolation). ``NotificationLog`` carries its own ``tenant`` column, so
    this filter is what keeps a log row filed under a different gym from
    deduping this member's send — the ``customer`` filter alone would not.

    Args:
        customer: The member whose invite history is checked.
        window_hours: The dedupe window length in hours.

    Returns:
        The matching ``NotificationLog`` row, or ``None``.
    """
    window_start = timezone.now() - timedelta(hours=window_hours)
    return (
        NotificationLog.objects.for_tenant(customer.tenant)
        .filter(
            customer=customer,
            notification_type=NotificationLog.NotificationType.APP_INVITE,
            status=NotificationLog.Status.SENT,
            created_at__gte=window_start,
        )
        .order_by("-created_at")
        .first()
    )


def _daily_invite_count(tenant) -> int:
    """Invites already attempted for the tenant today (hard cap check)."""
    day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        NotificationLog.objects.for_tenant(tenant)
        .filter(
            notification_type=NotificationLog.NotificationType.APP_INVITE,
            created_at__gte=day_start,
        )
        .count()
    )


def _render_content(tenant, customer, membership, link: str) -> str:
    """Human-readable invite copy stored on the log (audit trail)."""
    return build_message(
        "app_invite",
        {
            "customer_name": customer.name,
            "gym_name": tenant.name,
            "plan_name": membership.plan.name if membership else "your",
            "invite_link": link,
        },
    )


def send_app_invite(
    tenant,
    customer,
    *,
    invited_by=None,
    force: bool = False,
    poster: Callable[..., Any] | None = None,
) -> AppInviteResult:
    """Send (or resend) the app invite to a member over WhatsApp, then SMS.

    Behaviour (FBOS-011 §5, issue #66): the rollout flag or the plan toggle
    can make the invite ``not_applicable``; a sent invite inside
    ``APP_INVITE_RESEND_WINDOW_HOURS`` short-circuits to ``already_sent``
    unless ``force``; WhatsApp carries via WATI first, then Gupshup (tenant
    config), MSG91 SMS second (platform config), and no-channel-configured
    is ``skipped``. Never raises — outcomes are returned and logged.

    Args:
        tenant: The tenant sending the invite.
        customer: The member to invite (must belong to the tenant).
        invited_by: The staff user triggering the send (audit).
        force: Bypass the dedupe window (front-desk resend override).
        poster: Injectable HTTP post callable (tests).

    Returns:
        The :class:`AppInviteResult` describing what happened.
    """
    membership = _latest_membership(customer)
    reason = _invite_not_applicable_reason(tenant, membership)
    if reason is not None:
        return AppInviteResult(status=STATUS_NOT_APPLICABLE, reason=reason)

    window_hours = int(getattr(settings, "APP_INVITE_RESEND_WINDOW_HOURS", 24))
    if not force:
        recent = _sent_invite_within_window(customer, window_hours)
        if recent is not None:
            return AppInviteResult(
                status=STATUS_ALREADY_SENT,
                reason=None,
                channel=recent.channel or None,
                log=recent,
                sent_at=recent.created_at,
                resend_allowed_after=recent.created_at + timedelta(hours=window_hours),
            )

    if _daily_invite_count(tenant) >= int(getattr(settings, "APP_INVITE_DAILY_LIMIT", 20)):
        logger.warning("App invite daily cap reached for tenant %s", tenant.pk)
        return AppInviteResult(status=STATUS_FAILED, reason=REASON_DAILY_LIMIT)

    link = build_app_invite_links(tenant)["web"]
    content = _render_content(tenant, customer, membership, link)

    def _log(status: str, channel: str = "", error: str = "", provider: str = "") -> NotificationLog:
        return NotificationLog.objects.create(
            tenant=tenant,
            customer=customer,
            actor=invited_by,
            notification_type=NotificationLog.NotificationType.APP_INVITE,
            status=status,
            channel=channel,
            provider=provider,
            content=content,
            error_message=error,
        )

    template_name = WHATSAPP_TEMPLATE_NAMES["app_invite"]
    to = normalize_msisdn(customer.phone or "", getattr(settings, "OTP_DEFAULT_COUNTRY_CODE", "91"))

    # WhatsApp legs in policy order — WATI (tenant BSP #1), then Gupshup (#2).
    # A ready-but-failing provider falls through to the next leg; a provider
    # that is not fully configured is not attempted at all (the SMS leg
    # carries instead), matching the original WATI-only contract. Every
    # attempted leg is audited, so a failed leg leaves its own row.
    attempt = send_whatsapp_template(
        tenant,
        template_name,
        to,
        [customer.name, tenant.name, membership.plan.name if membership else "your", link],
        poster=poster,
    )
    failure_log: NotificationLog | None = None
    for provider, error in attempt.failures:
        logger.warning("%s app-invite delivery failed for customer %s: %s", provider, customer.pk, error)
        failure_log = _log(NotificationLog.Status.FAILED, CHANNEL_WHATSAPP, error, provider=provider)
    if attempt.sent:
        log = _log(NotificationLog.Status.SENT, CHANNEL_WHATSAPP, provider=attempt.provider)
        return AppInviteResult(status=STATUS_SENT, channel=CHANNEL_WHATSAPP, log=log, sent_at=log.created_at)

    if getattr(settings, "MSG91_INVITE_TEMPLATE_ID", "") and getattr(settings, "MSG91_AUTH_KEY", ""):
        try:
            post_msg91_flow(
                [
                    {
                        "mobiles": to,
                        "NAME": customer.name,
                        "GYM": tenant.name,
                        "LINK": link,
                        "PHONE": customer.phone or "",
                    }
                ],
                settings.MSG91_INVITE_TEMPLATE_ID,
                poster=poster,
            )
        except Exception as exc:  # noqa: BLE001 - recorded, never raised
            logger.warning("SMS app-invite delivery failed for customer %s: %s", customer.pk, exc)
            log = _log(NotificationLog.Status.FAILED, CHANNEL_SMS, str(exc), provider=PROVIDER_MSG91)
            return AppInviteResult(
                status=STATUS_FAILED,
                reason=str(exc),
                channel=CHANNEL_SMS,
                log=log,
            )
        log = _log(NotificationLog.Status.SENT, CHANNEL_SMS, provider=PROVIDER_MSG91)
        return AppInviteResult(status=STATUS_SENT, channel=CHANNEL_SMS, log=log, sent_at=log.created_at)

    if failure_log is not None:
        # A WhatsApp leg was configured but failed, and SMS is not set up.
        return AppInviteResult(
            status=STATUS_FAILED,
            reason=str(failure_log.error_message),
            channel=failure_log.channel,
            log=failure_log,
        )
    log = _log(NotificationLog.Status.SKIPPED, "", REASON_WATI_NOT_CONFIGURED)
    return AppInviteResult(status=STATUS_SKIPPED, reason=REASON_WATI_NOT_CONFIGURED, log=log)


def invite_result_payload(result: AppInviteResult) -> dict[str, Any]:
    """Render an :class:`AppInviteResult` as the API ``app_invite`` block.

    Args:
        result: The outcome to render.

    Returns:
        ``{"status", "reason", "channel", "sent_at", "resend_allowed_after"}``
        with ISO timestamps.
    """
    return {
        "status": result.status,
        "reason": result.reason,
        "channel": result.channel,
        "sent_at": result.sent_at.isoformat() if result.sent_at else None,
        "resend_allowed_after": (result.resend_allowed_after.isoformat() if result.resend_allowed_after else None),
    }
