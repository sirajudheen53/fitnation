"""Tenant provisioning and read services."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from apps.tenants.features import seed_default_features
from apps.tenants.models import Tenant, TenantSettings

if TYPE_CHECKING:
    from apps.notifications.models import NotificationLog

logger = logging.getLogger(__name__)

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "starter": {"max_branches": 1, "max_customers": 100, "max_trainers": 5},
    "professional": {"max_branches": 5, "max_customers": 1000, "max_trainers": 50},
    "enterprise": {"max_branches": 50, "max_customers": 10000, "max_trainers": 500},
}


def provision_tenant(
    name: str,
    contact_email: str,
    subscription_plan: str = "starter",
    **kwargs: Any,
) -> Tenant:
    """Create a new tenant and its settings.

    Called during vendor onboarding. The created tenant is configured with plan-based
    usage limits and defaults to a trial status.

    Args:
        name: Display name of the tenant (gym business).
        contact_email: Primary contact email for the tenant. Must be unique globally.
        subscription_plan: One of ``starter``, ``professional``, ``enterprise``.
        **kwargs: Additional fields accepted by the ``Tenant`` model. A
            ``features`` mapping is merged OVER the module-flag registry
            defaults (issue #46) so every new gym starts with a fully-populated
            feature map; non-module keys pass through untouched.

    Returns:
        The fully provisioned ``Tenant`` instance.
    """
    features = seed_default_features(kwargs.pop("features", None))
    tenant = Tenant.objects.create(
        name=name,
        contact_email=contact_email,
        subscription_plan=subscription_plan,
        status=Tenant.Status.TRIAL,
        features=features,
        **kwargs,
    )
    TenantSettings.objects.create(tenant=tenant)

    limits = PLAN_LIMITS.get(subscription_plan, PLAN_LIMITS["starter"])
    tenant.config.max_branches = limits["max_branches"]
    tenant.config.max_customers = limits["max_customers"]
    tenant.config.max_trainers = limits["max_trainers"]
    tenant.config.save()

    return tenant


@dataclass(frozen=True)
class WhatsappTestOutcome:
    """Outcome envelope of the settings-page WhatsApp test send (issue #73).

    The ``provider`` attributes carry the provider's own response verbatim:
    Gupshup's ``/wa/api/v1/msg`` HTTP-202s *every* submit (``"submitted"`` +
    message id) — including undeliverable content — so the UI must show
    SUCCESS only from this verbatim status, never from raw HTTP success.

    Attributes:
        log: The audited ``NotificationLog`` row for the attempt.
        provider: The BSP that was tested (the requested one, even when skipped).
        provider_status: The provider's response status word (e.g. Gupshup
            ``"submitted"``), verbatim; empty when none was returned.
        provider_message_id: The provider's message id, when returned.
        detail: Human/provider detail — the provider error text verbatim
            on failure, empty on success.
    """

    log: "NotificationLog"
    provider: str
    provider_status: str
    provider_message_id: str
    detail: str


# Gupshup's msg API reports acceptance with these in-body ``status`` words
# (transport layers always 2xx a queued submit; the body is the truth).
GUPSHUP_ACCEPTED_STATUS = {"submitted", "success", "accepted"}


def _welcome_test_context(phone: str) -> dict[str, str]:
    """Template context for the settings-page welcome test message."""
    return {
        "customer_name": phone,
        "plan_name": "Membership (test)",
        "end_date": "—",
        "phone": phone,
    }


def verbatim_provider_error(response: Any, fallback: str) -> str:
    """The provider's response body verbatim (an HTTPError only carries a summary)."""
    body = getattr(response, "text", None)
    return body if body is not None else fallback


def send_whatsapp_test(
    tenant: Tenant,
    phone: str,
    actor: Any = None,
    sender: Any = None,
    poster: Any = None,
    provider: str = "wati",
) -> WhatsappTestOutcome:
    """Send the settings-page test message via the tenant's WhatsApp config.

    The chosen provider's own outcome is reported, never a silent fallback to
    the other one. The attempt (sent/failed/skipped) is recorded in
    ``NotificationLog`` with that provider.

    - ``wati`` (default, the original contract): rides the WATI session-post
      path via :func:`...wati_service.send_notification` — unchanged behavior.
    - ``gupshup`` (issue #73): delivers an APPROVED template message through
      the tenant's Gupshup app — freeform business-initiated text gets provider
      ACK (HTTP 202 + message id) but is silently never delivered outside a
      24h session, which is exactly the "SUCCESS but nothing arrives" bug.
      The template name/params come from settings (approved per tenant in the
      Gupshup console).

    Args:
        tenant: The tenant whose WhatsApp configuration to use.
        phone: Recipient phone number from the settings form.
        actor: The staff user who triggered the send (audit trail).
        sender: Injectable WATI HTTP post callable (tests).
        poster: Injectable Gupshup HTTP post callable (tests).
        provider: ``"wati"`` or ``"gupshup"`` — the BSP under test.

    Returns:
        The :class:`WhatsappTestOutcome` (log + verbatim provider response).
    """
    from apps.notifications.models import NotificationLog

    if provider == "gupshup":
        return _send_gupshup_test(tenant, phone, actor=actor, poster=poster)

    from apps.notifications.services.wati_service import send_notification

    log = send_notification(
        tenant,
        customer=None,
        notification_type=NotificationLog.NotificationType.WELCOME,
        context_data=_welcome_test_context(phone),
        to_phone=phone,
        actor=actor,
        sender=sender,
        provider="wati",
    )
    return WhatsappTestOutcome(
        log=log,
        provider="wati",
        provider_status="",
        provider_message_id=log.wati_message_id,
        detail=log.error_message,
    )


def _blank_notification_log(
    tenant: Tenant,
    notification_type: str,
    content: str,
    actor: Any = None,
) -> "NotificationLog":
    """Open an audit row before the legs run (mirrors wati_service logging)."""
    from apps.notifications.models import NotificationLog

    return NotificationLog.objects.create(
        tenant=tenant,
        customer=None,
        actor=actor,
        notification_type=notification_type,
        status=NotificationLog.Status.PENDING,
        content=content,
    )


def _finish_notification_log(
    log: "NotificationLog",
    status: str,
    *,
    channel: str = "",
    provider: str = "",
    message_id: str = "",
    error: str = "",
    fields: list[str] | None = None,
) -> None:
    """Persist the outcome of one send attempt on an open audit row."""
    log.status = status
    update_fields = ["status", "updated_at"]
    if channel:
        log.channel = channel
        update_fields.append("channel")
    if provider:
        log.provider = provider
        update_fields.append("provider")
    if message_id:
        log.wati_message_id = message_id
        update_fields.append("wati_message_id")
    if error:
        log.error_message = error
        update_fields.append("error_message")
    log.save(update_fields=update_fields)


def _send_gupshup_test(
    tenant: Tenant,
    phone: str,
    *,
    actor: Any = None,
    poster: Any = None,
) -> WhatsappTestOutcome:
    """Deliver the gupshup settings-test as an approved template message.

    Audit mirror of ``wati_service.send_notification``'s gupshup leg — same
    skip/fail gating and log shapes — except the content is a TEMPLATE send
    (the platform's approved-slug convention) and the provider response is
    parsed verbatim instead of being equated with HTTP success.

    Args:
        tenant: The tenant whose Gupshup configuration is tested.
        phone: Recipient phone number from the settings form.
        actor: The staff user who triggered the send (audit trail).
        poster: Injectable Gupshup HTTP post callable (tests).

    Returns:
        The :class:`WhatsappTestOutcome` for the chosen provider.
    """
    from django.conf import settings

    from apps.notifications.models import NotificationLog
    from apps.notifications.services.channels import (
        CHANNEL_WHATSAPP,
        PROVIDER_GUPSHUP,
        normalize_msisdn,
        post_gupshup_template,
    )
    from apps.notifications.services.wati_service import build_message

    content = build_message(notification_type="welcome", context=_welcome_test_context(phone))
    log = _blank_notification_log(tenant, NotificationLog.NotificationType.WELCOME, content, actor=actor)

    if not tenant.is_gupshup_enabled:
        _finish_notification_log(
            log,
            NotificationLog.Status.SKIPPED,
            error="Gupshup is not enabled for this tenant",
        )
        return WhatsappTestOutcome(
            log=log, provider=PROVIDER_GUPSHUP, provider_status="", provider_message_id="", detail=log.error_message
        )

    recipient = (phone or "").strip()
    if not recipient:
        _finish_notification_log(
            log,
            NotificationLog.Status.SKIPPED,
            error="No recipient phone for this notification",
        )
        return WhatsappTestOutcome(
            log=log, provider=PROVIDER_GUPSHUP, provider_status="", provider_message_id="", detail=log.error_message
        )

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
        _finish_notification_log(
            log,
            NotificationLog.Status.FAILED,
            channel=CHANNEL_WHATSAPP,
            provider=PROVIDER_GUPSHUP,
            error=f"Gupshup {missing} is not configured",
        )
        return WhatsappTestOutcome(
            log=log, provider=PROVIDER_GUPSHUP, provider_status="", provider_message_id="", detail=log.error_message
        )

    template_name = str(getattr(settings, "GUPSHUP_TEST_TEMPLATE_NAME", "welcome"))
    template_params = [
        param.strip()
        for param in str(getattr(settings, "GUPSHUP_TEST_TEMPLATE_PARAMS", "")).split(",")
        if param.strip()
    ]

    try:
        response = post_gupshup_template(
            tenant,
            template_name,
            normalize_msisdn(recipient, getattr(settings, "OTP_DEFAULT_COUNTRY_CODE", "91")),
            template_params,
            poster=poster,
        )
        provider_body: Any = response.json() if hasattr(response, "json") else {}
    except Exception as exc:  # noqa: BLE001 - the audit row carries the failure
        detail = verbatim_provider_error(getattr(exc, "response", None), str(exc))
        _finish_notification_log(
            log,
            NotificationLog.Status.FAILED,
            channel=CHANNEL_WHATSAPP,
            provider=PROVIDER_GUPSHUP,
            error=detail,
        )
        return WhatsappTestOutcome(
            log=log, provider=PROVIDER_GUPSHUP, provider_status="", provider_message_id="", detail=detail
        )

    if not isinstance(provider_body, dict):
        provider_body = {}
    status_word = str(provider_body.get("status", ""))
    message_id = str(provider_body.get("messageId") or provider_body.get("message_id") or "")

    if status_word not in GUPSHUP_ACCEPTED_STATUS:
        # HTTP 2xx with a non-accepted body — the provider queued nothing
        # (Gupshup never reports "undeliverable" synchronously); verbatim text.
        detail = str(provider_body.get("message") or provider_body)
        _finish_notification_log(
            log,
            NotificationLog.Status.FAILED,
            channel=CHANNEL_WHATSAPP,
            provider=PROVIDER_GUPSHUP,
            error=detail,
        )
        return WhatsappTestOutcome(
            log=log, provider=PROVIDER_GUPSHUP, provider_status=status_word, provider_message_id="", detail=detail
        )

    _finish_notification_log(
        log,
        NotificationLog.Status.SENT,
        channel=CHANNEL_WHATSAPP,
        provider=PROVIDER_GUPSHUP,
        message_id=message_id,
    )
    return WhatsappTestOutcome(
        log=log, provider=PROVIDER_GUPSHUP, provider_status=status_word, provider_message_id=message_id, detail=""
    )


def whatsapp_status_counts(tenant: Tenant) -> dict[str, int]:
    """Today's WhatsApp usage counters for the settings page.

    Mirrors the invite cap convention (local-midnight day start, all attempts
    of the type regardless of status). ``daily_cap`` is the WATI OTP cap —
    the frontend ships a single cap value for the settings page.

    Args:
        tenant: The tenant to count for.

    Returns:
        ``{otp_sent_today, invites_sent_today, daily_cap}`` as ints.
    """
    from django.conf import settings
    from django.utils import timezone

    from apps.notifications.models import NotificationLog

    day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = NotificationLog.objects.for_tenant(tenant).filter(created_at__gte=day_start)
    return {
        "otp_sent_today": today.filter(notification_type=NotificationLog.NotificationType.OTP).count(),
        "invites_sent_today": today.filter(notification_type=NotificationLog.NotificationType.APP_INVITE).count(),
        "daily_cap": int(getattr(settings, "TENANT_WATI_OTP_DAILY_CAP", 200)),
    }


# Unauthenticated gym-lookup throttle (per IP), mirroring the style of
# ``apps.users.services._throttle_lookup`` (best-effort, fail-open on cache
# errors). Kept IP-only: the lookup carries no phone or identity.
GYM_LOOKUP_THROTTLE_LIMIT = 10
GYM_LOOKUP_THROTTLE_WINDOW_SECONDS = 600


def throttle_gym_lookup(ip: str | None) -> None:
    """Rate-limit the public gym-code lookup (per IP, 10 per 10 minutes).

    Fail-open on cache failure (like ``_throttle_lookup``) — the lookup itself
    reveals nothing beyond a gym's public identity (uuid + name), and DRF's
    global throttles remain as a backstop.

    Args:
        ip: The client IP, or ``None`` when unavailable.

    Raises:
        Throttled: DRF exception surfaced as HTTP 429 once over the limit.
    """
    from django.core.cache import cache
    from rest_framework.exceptions import Throttled

    try:
        key = f"gym-lookup:{ip or 'noip'}"
        count = (cache.get(key) or 0) + 1
        cache.set(key, count, timeout=GYM_LOOKUP_THROTTLE_WINDOW_SECONDS)
    except Throttled:
        raise
    except Exception:  # noqa: BLE001 — throttle best-effort — cache loss must not block
        logger.warning("Gym lookup throttle skipped (cache unavailable)")
        return
    if count > GYM_LOOKUP_THROTTLE_LIMIT:
        raise Throttled(detail="Too many requests. Try again later.")
