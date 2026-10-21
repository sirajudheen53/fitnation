"""Tenant provisioning and read services."""

from typing import Any

from apps.tenants.models import Tenant, TenantSettings

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
        **kwargs: Additional fields accepted by the ``Tenant`` model.

    Returns:
        The fully provisioned ``Tenant`` instance.
    """
    tenant = Tenant.objects.create(
        name=name,
        contact_email=contact_email,
        subscription_plan=subscription_plan,
        status=Tenant.Status.TRIAL,
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
) -> Any:
    """Send the settings-page test message via the tenant's own WATI config.

    Reuses :func:`apps.notifications.services.wati_service.send_notification`
    (single WATI client) with the welcome template copy; there is no customer
    record for the test phone, so ``to_phone`` carries the recipient. The
    attempt (sent/failed/skipped) is recorded in ``NotificationLog``.

    Args:
        tenant: The tenant whose WATI configuration to use.
        phone: Recipient phone number from the settings form.
        actor: The staff user who triggered the send (audit trail).
        sender: Injectable HTTP post callable (tests).

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
