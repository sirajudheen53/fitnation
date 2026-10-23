"""Email helpers for vendor onboarding (issue #66 channel policy).

The vendor-signup funnel runs at platform level: verification happens BEFORE
a tenant exists, so there is no per-gym WhatsApp config to consult and the
email leg is the only channel — these helpers therefore log the payloads the
way they always have, now with the policy stated and the recipient
capability check in place.

The post-provisioning welcome is tenant-aware: once the gym exists, its
WhatsApp channels (WATI → Gupshup) carry the welcome when configured and a
phone number was provided, per the "a configured channel carries everything"
rule; the logged email remains the last resort.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.tenants.models import Tenant
    from apps.vendors.models import VendorRegistration

logger = logging.getLogger(__name__)


def send_verification_email(registration: "VendorRegistration") -> None:
    """Log a verification email payload for the given registration.

    Pre-tenant platform flow: no WhatsApp channel exists yet (per-gym config
    is provisioned later), so email is the only possible channel.

    Args:
        registration: The vendor registration to verify.
    """
    logger.info(
        "Verification email to %s (token=%s)",
        registration.email,
        registration.email_verification_token,
    )


def send_welcome_email(registration: "VendorRegistration", tenant: "Tenant") -> None:
    """Deliver the post-provisioning welcome — WhatsApp first, email logged.

    When the freshly provisioned gym already has a WhatsApp channel and the
    vendor left a contact phone, the welcome goes out over it (the channel
    policy applies to every communication, issue #66). Otherwise the email
    payload is logged for the operator as before.

    Args:
        registration: The provisioned vendor registration.
        tenant: The provisioned tenant.
    """
    from apps.notifications.services.router import whatsapp_providers

    if registration.contact_phone and whatsapp_providers(tenant, ready_only=True):
        from apps.notifications.services.wati_service import send_notification

        send_notification(
            tenant,
            customer=None,
            notification_type="welcome",
            context_data={
                "customer_name": registration.contact_name or registration.business_name,
                "plan_name": tenant.subscription_plan,
                "end_date": "—",
                "phone": registration.contact_phone,
            },
            to_phone=registration.contact_phone,
        )
        return

    logger.info(
        "Welcome email to %s (tenant=%s, plan=%s)",
        registration.email,
        tenant.name,
        tenant.subscription_plan,
    )
