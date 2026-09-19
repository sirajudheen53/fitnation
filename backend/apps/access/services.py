"""Access app domain services — all write operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from django.utils import timezone

from apps.access.adapters import AdapterError, get_adapter
from apps.access.models import (
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
    ConnectionType,
    CredentialType,
)
from apps.access.selectors import get_device_allow_list

if TYPE_CHECKING:
    from apps.branches.models import Branch
    from apps.customers.models import Customer
    from apps.tenants.models import Tenant
    from apps.users.models import User

logger = logging.getLogger(__name__)

_DEVICE_EVENT_TYPES = {"entry", "exit", "denied", "error"}
_CREDENTIAL_TYPES = set(CredentialType.values)


def create_device(
    *,
    tenant: Tenant,
    branch: Branch,
    vendor: str,
    model: str,
    serial_number: str,
    name: str,
    connection_type: str = ConnectionType.WEBHOOK,
    api_endpoint: str = "",
    api_key: str = "",
) -> BiometricDevice:
    """Register a new biometric device for a branch."""
    return BiometricDevice.objects.create(
        tenant=tenant,
        branch=branch,
        vendor=vendor,
        model=model,
        serial_number=serial_number,
        name=name,
        connection_type=connection_type,
        api_endpoint=api_endpoint,
        api_key=api_key,
    )


def enroll_credential(
    *,
    tenant: Tenant,
    device: BiometricDevice,
    customer: Customer,
    credential_type: str = CredentialType.FINGERPRINT,
    device_user_id: str,
) -> BiometricCredential:
    """Enroll a customer credential on a device."""
    return BiometricCredential.objects.create(
        tenant=tenant,
        customer=customer,
        device=device,
        credential_type=credential_type,
        device_user_id=device_user_id,
    )


def create_override(
    *,
    tenant: Tenant,
    customer: Customer,
    device: BiometricDevice,
    allow_access: bool,
    reason: str,
    created_by: User | None = None,
    reason_notes: str = "",
    expires_at: str | None = None,
) -> AccessOverride:
    """Create an owner override for a customer's device access."""
    return AccessOverride.objects.create(
        tenant=tenant,
        customer=customer,
        device=device,
        allow_access=allow_access,
        reason=reason,
        reason_notes=reason_notes,
        expires_at=expires_at,
        created_by=created_by,
    )


def record_event(
    *,
    device: BiometricDevice,
    customer: Customer | None,
    credential_type: str,
    device_user_id: str,
    event_type: str,
    event_timestamp: str,
    raw_payload: dict | None = None,
) -> AccessLog:
    """Record an access event from a biometric device."""
    return AccessLog.objects.create(
        tenant=device.tenant,
        device=device,
        customer=customer,
        device_user_id=device_user_id,
        credential_type=credential_type,
        event_type=event_type,
        event_timestamp=event_timestamp,
        raw_payload=raw_payload or {},
    )


def sync_device(device: BiometricDevice) -> dict:
    """Push the resolved allow-list to a device via its vendor adapter.

    Offline/unreachable devices and vendors without a native adapter are
    reported as ``{"synced": False, "detail": ...}`` instead of raising.

    Args:
        device: The biometric device to sync.

    Returns:
        A dict with ``synced`` (bool), ``detail`` (str), and ``pushed`` (int,
        present on success).
    """
    credentials = get_device_allow_list(device=device)
    try:
        result = get_adapter(device).sync_allow_list(device, credentials)
    except (AdapterError, NotImplementedError) as exc:
        logger.warning("Allow-list sync failed for device %s: %s", device.pk, exc)
        return {"synced": False, "detail": str(exc)}

    if not result.get("ok", True):
        logger.warning("Allow-list sync reported failure for device %s", device.pk)
        return {"synced": False, "detail": result.get("detail", "Sync reported failure.")}

    device.last_sync_at = timezone.now()
    device.save(update_fields=["last_sync_at", "updated_at"])
    return {
        "synced": True,
        "pushed": result.get("pushed", len(credentials)),
        "detail": result.get("detail", f"Pushed allow-list to '{device.name}'."),
    }


def sync_customer_devices(customer: Customer) -> list[dict]:
    """Sync every active device the given customer has a credential on.

    Called synchronously from membership touchpoints (create/renew/cancel/
    update) so access changes propagate to door hardware within seconds.

    Args:
        customer: The customer whose access changed.

    Returns:
        A list of per-device sync result dicts.
    """
    devices = (
        BiometricDevice.objects.for_tenant(customer.tenant)
        .filter(
            is_active=True,
            credentials__customer=customer,
            credentials__is_active=True,
        )
        .distinct()
    )
    return [{"device_id": device.pk, **sync_device(device)} for device in devices]


def _parse_event_timestamp(raw_event: dict) -> datetime:
    """Parse an event timestamp from a raw device payload, defaulting to now."""
    value = raw_event.get("event_timestamp") or raw_event.get("timestamp")
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning("Unparseable event timestamp %r; defaulting to now.", value)
    return timezone.now()


def _resolve_event_customer(*, device: BiometricDevice, device_user_id: str) -> Customer | None:
    """Resolve the customer for a device user id via enrolled credentials."""
    if not device_user_id:
        return None
    credential = (
        BiometricCredential.objects.for_tenant(device.tenant)
        .filter(device=device, device_user_id=device_user_id)
        .select_related("customer")
        .first()
    )
    return credential.customer if credential else None


def fetch_device_events(*, device: BiometricDevice, since: datetime | None = None) -> dict:
    """Pull access events from a device and record them as AccessLogs.

    Args:
        device: The biometric device to pull events from.
        since: Optional cutoff timestamp forwarded to the adapter.

    Returns:
        A dict with ``fetched`` (bool), ``recorded`` (int), and ``detail`` (str).
    """
    try:
        events = get_adapter(device).fetch_events(device, since=since)
    except (AdapterError, NotImplementedError) as exc:
        logger.warning("Event fetch failed for device %s: %s", device.pk, exc)
        return {"fetched": False, "recorded": 0, "detail": str(exc)}

    recorded = 0
    for raw_event in events:
        if not isinstance(raw_event, dict):
            continue
        device_user_id = str(raw_event.get("device_user_id") or "")
        raw_type = raw_event.get("event_type")
        event_type = raw_type if raw_type in _DEVICE_EVENT_TYPES else ("entry" if not raw_type else "error")
        credential_type = (
            raw_event.get("credential_type")
            if raw_event.get("credential_type") in _CREDENTIAL_TYPES
            else CredentialType.CARD
        )
        record_event(
            device=device,
            customer=_resolve_event_customer(device=device, device_user_id=device_user_id),
            credential_type=credential_type,
            device_user_id=device_user_id,
            event_type=event_type,
            event_timestamp=_parse_event_timestamp(raw_event),
            raw_payload=raw_event,
        )
        recorded += 1

    return {"fetched": True, "recorded": recorded, "detail": f"Recorded {recorded} events."}


def decide_and_log(
    *,
    customer: Customer,
    device: BiometricDevice,
) -> dict:
    """Evaluate the access rule for a customer at a device and log the decision.

    Wraps :func:`apps.access.selectors.get_customer_access_state` and
    persists one :class:`~apps.access.models.AccessDecisionLog` row per
    evaluation so gyms can audit why a member was granted or denied
    entry (issue #19).

    Args:
        customer: The customer attempting entry.
        device: The biometric device being accessed.

    Returns:
        The rule-engine state dict (``allowed``, ``source``, ``reason``,
        and ``override_id`` when an override decided the outcome).
    """
    from apps.access.models import AccessDecisionLog
    from apps.access.selectors import get_customer_access_state

    state = get_customer_access_state(customer=customer, device=device)
    AccessDecisionLog.objects.create(
        tenant=device.tenant,
        customer=customer,
        device=device,
        allowed=state["allowed"],
        source=state["source"],
        reason=state.get("reason", "")[:255],
        override_id=state.get("override_id"),
    )
    return state


def ingest_event(
    *,
    device: BiometricDevice,
    device_user_id: str,
    event_type: str,
    event_timestamp: datetime,
    credential_type: str = "fingerprint",
    raw_payload: dict | None = None,
) -> dict:
    """Ingest a device access event — idempotent, with attendance wiring.

    Resolves the customer from the device's credential map, records the
    :class:`~apps.access.models.AccessLog` entry (skipping exact
    duplicates), and auto-creates a customer attendance check-in on
    entry events (issue #21).

    Args:
        device: The device reporting the event.
        device_user_id: The device-side user id from the event.
        event_type: One of ``entry`` / ``exit`` / ``denied`` / ``error``.
        event_timestamp: Timezone-aware event time.
        credential_type: Credential type reported by the device.
        raw_payload: Optional raw vendor payload for debugging.

    Returns:
        A dict with ``duplicate`` (bool), ``log`` (the AccessLog — new or
        pre-existing), and ``attendance_created`` (bool).

    Raises:
        AdapterError: If ``event_type`` is not a supported device event.
    """
    from apps.access.models import AccessLog, BiometricCredential

    if event_type not in _DEVICE_EVENT_TYPES:
        raise AdapterError(f"Unsupported event type '{event_type}'.")

    duplicate = AccessLog.objects.filter(
        device=device,
        device_user_id=device_user_id,
        event_type=event_type,
        event_timestamp=event_timestamp,
    ).first()
    if duplicate is not None:
        return {"duplicate": True, "log": duplicate, "attendance_created": False}

    credential = (
        BiometricCredential.objects.filter(
            device=device,
            device_user_id=device_user_id,
            is_active=True,
        )
        .select_related("customer")
        .first()
    )
    customer = credential.customer if credential else None

    log = record_event(
        device=device,
        customer=customer,
        credential_type=credential_type,
        device_user_id=device_user_id,
        event_type=event_type,
        event_timestamp=event_timestamp,
        raw_payload=raw_payload,
    )

    device.last_seen_at = timezone.now()
    device.save(update_fields=["last_seen_at"])

    attendance_created = False
    if customer is not None and event_type == "entry":
        from rest_framework.exceptions import ValidationError

        try:
            from apps.attendance.services import log_check_in

            log_check_in(
                tenant=device.tenant,
                person_id=customer.id,
                person_type="customer",
                branch_id=device.branch_id,
            )
            attendance_created = True
        except ValidationError:
            # Already checked in today — the attendance side is idempotent;
            # the access log itself is still recorded.
            logger.info(
                "Attendance check-in skipped for customer %s (already open).",
                customer.pk,
            )

    return {"duplicate": False, "log": log, "attendance_created": attendance_created}
