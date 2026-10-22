"""Membership → biometric device metadata propagation (phase 2).

Devices on the ADMS push protocol hold their own user table; we mirror
membership state into it by queuing ``DATA UPDATE/DELETE USERINFO``
commands on :class:`~apps.access.models.DeviceCommandQueue` — the device
applies them on its next ``/iclock/getrequest`` poll.

Owner decisions locked 2026-10-22:

1. **Expiry cool-off** — device access stays valid until membership
   ``end_date + COOL_OFF_DAYS``, then is revoked. Per-tenant override via
   ``tenant.features["biometric_cool_off_days"]``.
2. **One canonical device_user_id per customer** — allocated once per
   tenant and reused on every device the customer enrolls on.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

from apps.access.models import BiometricCredential, DeviceCommandQueue

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.memberships.models import Membership
    from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)

#: Grace days a member keeps biometric access after membership end_date.
DEFAULT_COOL_OFF_DAYS = 3

FEATURE_COOL_OFF_KEY = "biometric_cool_off_days"


def cool_off_days_for(tenant: Tenant) -> int:
    """Cool-off length for a tenant (features override, default 3)."""
    raw = (tenant.features or {}).get(FEATURE_COOL_OFF_KEY, DEFAULT_COOL_OFF_DAYS)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r for tenant %s; using default.", FEATURE_COOL_OFF_KEY, raw, tenant.pk)
        return DEFAULT_COOL_OFF_DAYS


def latest_membership_for_access(customer: Customer) -> Membership | None:
    """The membership that governs device access (newest non-cancelled)."""
    return customer.memberships.exclude(status="cancelled").order_by("-end_date", "-pk").select_related("plan").first()


def biometric_access_valid_until(membership: Membership, tenant: Tenant) -> date:
    """Last day biometric access stays valid: end_date + cool-off."""
    return membership.end_date + timedelta(days=cool_off_days_for(tenant))


def is_membership_in_cool_off(membership: Membership | None, tenant: Tenant, today: date | None = None) -> bool:
    """True while the membership is active or inside the expiry cool-off."""
    if membership is None or membership.status == "cancelled":
        return False
    day = today or timezone.localdate()
    return day <= biometric_access_valid_until(membership, tenant)


def propagate_enrollment(credential: BiometricCredential) -> DeviceCommandQueue | None:
    """Queue the user-metadata push for a freshly enrolled credential.

    Enrolls at the front desk must reach the device so the member can
    punch immediately: when the membership is active-or-in-cool-off a
    ``DATA UPDATE USERINFO`` command is queued for the credential's
    device; with no live membership the credential is created silently —
    the device learns the user only once a membership activates it.
    """
    tenant = credential.tenant
    membership = latest_membership_for_access(customer=credential.customer)
    if not is_membership_in_cool_off(membership, tenant):
        logger.info(
            "Credential %s enrolled without live membership; no device command queued.",
            credential.pk,
        )
        return None
    return DeviceCommandQueue.objects.create(
        tenant=tenant,
        device=credential.device,
        command="DATA UPDATE USERINFO",
        payload={
            "pin": credential.device_user_id,
            "name": credential.customer.name,
            "privilege": 0,
            "valid_date": biometric_access_valid_until(membership, tenant).isoformat(),
        },
    )
