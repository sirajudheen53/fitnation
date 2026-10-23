"""Tenant provisioning and read services."""

import logging
from typing import Any

from apps.tenants.features import seed_default_features
from apps.tenants.models import Tenant, TenantSettings

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


def send_whatsapp_test(
    tenant: Tenant,
    phone: str,
    actor: Any = None,
    sender: Any = None,
    provider: str = "wati",
) -> Any:
    """Send the settings-page test message via the tenant's WhatsApp config.

    Reuses :func:`apps.notifications.services.wati_service.send_notification`
    with the welcome template copy; there is no customer record for the test
    phone, so ``to_phone`` carries the recipient. ``provider`` selects which
    BSP is tested — ``wati`` (default, the original contract) or ``gupshup``
    (issue #67): the chosen provider's own outcome is reported, never a
    silent fallback to the other one. The attempt (sent/failed/skipped) is
    recorded in ``NotificationLog`` with that provider.

    Args:
        tenant: The tenant whose WhatsApp configuration to use.
        phone: Recipient phone number from the settings form.
        actor: The staff user who triggered the send (audit trail).
        sender: Injectable WATI HTTP post callable (tests).
        provider: ``"wati"`` or ``"gupshup"`` — the BSP under test.

    Returns:
        The created ``NotificationLog`` record.
    """
    from apps.notifications.models import NotificationLog
    from apps.notifications.services.wati_service import send_notification

    context = {
        "customer_name": phone,
        "plan_name": "Membership (test)",
        "end_date": "—",
        "phone": phone,
    }
    return send_notification(
        tenant,
        customer=None,
        notification_type=NotificationLog.NotificationType.WELCOME,
        context_data=context,
        to_phone=phone,
        actor=actor,
        sender=sender,
        provider=provider,
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
