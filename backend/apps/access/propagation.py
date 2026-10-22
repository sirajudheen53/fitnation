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

from apps.access.models import BiometricCredential, BiometricDevice, DeviceCommandQueue

if TYPE_CHECKING:
    from apps.customers.models import Customer
    from apps.memberships.models import Membership
    from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)

#: Grace days a member keeps biometric access after membership end_date.
DEFAULT_COOL_OFF_DAYS = 3

FEATURE_COOL_OFF_KEY = "biometric_cool_off_days"

#: ADMS command names stored on DeviceCommandQueue rows.
UPDATE_COMMAND = "DATA UPDATE USERINFO"
DELETE_COMMAND = "DATA DELETE USERINFO"

#: A command identical to one delivered in the last 24h is not re-queued.
DEDUP_WINDOW = timedelta(hours=24)


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


def userinfo_update_text(*, pin: str, name: str, privilege: int, valid_date: date | None) -> str:
    """The ADMS wire line for a user upsert (tab-separated fields)."""
    valid = valid_date.isoformat() if valid_date is not None else ""
    return f"{UPDATE_COMMAND}\tPIN={pin}\tName={name}\tPrivilege={privilege}\tPasswd=\tCard=\tValid={valid}"


def userinfo_delete_text(*, pin: str) -> str:
    """The ADMS wire line for a user delete."""
    return f"{DELETE_COMMAND} PIN={pin}"


def enqueue_device_command(
    *,
    device: BiometricDevice,
    command: str,
    text: str,
    payload: dict,
) -> DeviceCommandQueue | None:
    """Queue one device command unless an identical one is in flight.

    Dedupe (deterministic, shared by realtime propagation and the daily
    reconciliation): an identical command string still pending on the
    device, or delivered within the last 24h, skips the enqueue — the
    device applies the queued state on its next poll anyway. The wire
    line rides in ``payload["text"]`` so the serving endpoint can emit
    it verbatim.
    """
    identical = DeviceCommandQueue.objects.filter(device=device, payload__text=text)
    if identical.filter(executed_at__isnull=True).exists():
        return None
    if executed_within_window(device=device, text=text):
        return None
    return DeviceCommandQueue.objects.create(
        tenant=device.tenant,
        device=device,
        command=command,
        payload={**payload, "text": text},
    )


def executed_within_window(*, device: BiometricDevice, text: str) -> bool:
    """True when the identical command was delivered in the last 24h."""
    cutoff = timezone.now() - DEDUP_WINDOW
    return DeviceCommandQueue.objects.filter(device=device, payload__text=text, executed_at__gte=cutoff).exists()


def desired_device_action(*, customer: "Customer", tenant: "Tenant") -> tuple[str, "Membership | None"]:
    """Resolve the device-side state the customer should have.

    Returns:
        ``("update", membership)`` while the membership is active or
        inside the expiry cool-off, else ``("delete", None)``.
    """
    membership = latest_membership_for_access(customer=customer)
    if is_membership_in_cool_off(membership, tenant):
        return "update", membership
    return "delete", None


def propagate_customer_biometric_state(*, customer: "Customer") -> list[dict]:
    """Mirror the customer's membership state onto their enrolled devices.

    The access-side half of membership propagation: for every active
    credential, queue ``DATA UPDATE USERINFO`` (PIN, Name, Privilege=0,
    Valid=end_date + cool-off) while the member is live, and
    ``DATA DELETE USERINFO`` once expired past the cool-off or
    cancelled. Renewals simply queue a fresh UPDATE with the extended
    Valid date — the device applies the latest command. Drift-guarded
    via :func:`enqueue_device_command`, so calling this on every
    membership touchpoint and from the daily reconciliation is safe.

    Returns:
        One result dict per credential: ``device_id``,
        ``device_user_id``, ``action`` (update/delete), ``enqueued``,
        and ``queue_id`` (when a row was created).
    """
    tenant = customer.tenant
    credentials = list(
        BiometricCredential.objects.for_tenant(tenant)
        .filter(customer=customer, is_active=True)
        .select_related("device", "customer")
    )
    if not credentials:
        return []

    action, membership = desired_device_action(customer=customer, tenant=tenant)
    valid_until = biometric_access_valid_until(membership, tenant) if action == "update" else None

    results = []
    for credential in credentials:
        device = credential.device
        if action == "update":
            row = enqueue_device_command(
                device=device,
                command=UPDATE_COMMAND,
                text=userinfo_update_text(
                    pin=credential.device_user_id,
                    name=customer.name,
                    privilege=0,
                    valid_date=valid_until,
                ),
                payload={
                    "pin": credential.device_user_id,
                    "name": customer.name,
                    "privilege": 0,
                    "valid_date": valid_until.isoformat() if valid_until else None,
                },
            )
        else:
            row = enqueue_device_command(
                device=device,
                command=DELETE_COMMAND,
                text=userinfo_delete_text(pin=credential.device_user_id),
                payload={"pin": credential.device_user_id},
            )
        results.append(
            {
                "device_id": device.pk,
                "device_user_id": credential.device_user_id,
                "action": action,
                "enqueued": row is not None,
                "queue_id": row.pk if row else None,
            }
        )
        if row is None:
            logger.info(
                "Customer %s %s on device %s already queued/delivered; skipped.",
                customer.pk,
                action,
                device.pk,
            )
    return results


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
    valid_until = biometric_access_valid_until(membership, tenant)
    return enqueue_device_command(
        device=credential.device,
        command=UPDATE_COMMAND,
        text=userinfo_update_text(
            pin=credential.device_user_id,
            name=credential.customer.name,
            privilege=0,
            valid_date=valid_until,
        ),
        payload={
            "pin": credential.device_user_id,
            "name": credential.customer.name,
            "privilege": 0,
            "valid_date": valid_until.isoformat(),
        },
    )
