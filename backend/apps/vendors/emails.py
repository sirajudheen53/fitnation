"""Email helpers for vendor onboarding.

These functions perform no actual email sending. They log the email content so the
backend can be wired to a real email provider without placeholders.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.tenants.models import Tenant
    from apps.vendors.models import VendorRegistration

logger = logging.getLogger(__name__)


def send_verification_email(registration: "VendorRegistration") -> None:
    """Log a verification email payload for the given registration.

    Args:
        registration: The vendor registration to verify.
    """
    logger.info(
        "Verification email to %s (token=%s)",
        registration.email,
        registration.email_verification_token,
    )


def send_welcome_email(registration: "VendorRegistration", tenant: "Tenant") -> None:
    """Log a welcome email payload after provisioning.

    Args:
        registration: The provisioned vendor registration.
        tenant: The provisioned tenant.
    """
    logger.info(
        "Welcome email to %s (tenant=%s, plan=%s)",
        registration.email,
        tenant.name,
        tenant.subscription_plan,
    )
