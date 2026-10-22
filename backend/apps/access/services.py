"""Access app domain services — all write operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.access.adapters import AdapterError, get_adapter
from apps.access.models import (
    AccessLog,
    AccessOverride,
    BiometricCredential,
    BiometricDevice,
    ConnectionType,
    CredentialType,
    DeviceCommandQueue,
    PunchLogRaw,
    Vendor,
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

#: Vendors whose firmware speaks the ZKTeco ADMS push protocol — the only
#: family that can be told to re-upload stored transactions (eSSL = rebranded ZKTeco).
ADMS_HISTORY_VENDORS = frozenset({Vendor.ZKTECO, Vendor.ESSL})

#: Server command that makes an ADMS device re-upload stored attendance.
#: Delivered verbatim over /iclock/getrequest; the device answers by
#: POSTing its stored rows to /iclock/cdata?table=ATTLOG (push SDK "data
#: query" — verified against a pushver-2.4.x production reference).
HISTORY_PULL_COMMAND = "DATA QUERY ATTLOG"

#: Identifier reported in the pull-history API response.
HISTORY_PULL_MECHANISM = "data_query_attlog"

#: Default window start — far enough back to cover any device's stored log.
#: Deliberately naive; made aware in the project timezone at use.
HISTORY_EPOCH = datetime(2000, 1, 1, 0, 0, 0)  # noqa: DTZ001


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


def resolve_device_user_id(*, tenant: Tenant, customer: Customer) -> str:
    """Return the customer's canonical device_user_id within the tenant.

    Owner decision 2026-10-22: one canonical id per customer per tenant,
    reused on every device the customer enrolls on. The id of the
    customer's oldest active credential wins; new customers get the next
    integer id — max(existing tenant-wide integer ids) + 1. Gaps are
    deliberately never reused: monotonic allocation cannot collide with
    an id a device still holds for a deactivated credential.
    """
    existing = (
        BiometricCredential.objects.for_tenant(tenant)
        .filter(customer=customer, is_active=True)
        .order_by("enrolled_at", "pk")
        .values_list("device_user_id", flat=True)
        .first()
    )
    if existing:
        return existing
    max_id = 0
    for value in BiometricCredential.objects.for_tenant(tenant).values_list("device_user_id", flat=True).distinct():
        try:
            max_id = max(max_id, int(value))
        except (TypeError, ValueError):
            continue  # legacy non-integer ids don't participate in allocation
    return str(max_id + 1)


def _assert_device_slot_free(*, device: BiometricDevice, device_user_id: str, exclude_pk: int | None = None) -> None:
    """Raise unless (device, device_user_id) is free or held by the same row."""
    conflict = BiometricCredential.objects.filter(device=device, device_user_id=device_user_id).first()
    if conflict is not None and conflict.pk != exclude_pk:
        raise ValidationError(
            {"device_user_id": f"User id '{device_user_id}' is already enrolled on this device for another customer."},
            code="device_user_id_taken",
        )


def enroll_credential(
    *,
    tenant: Tenant,
    device: BiometricDevice,
    customer: Customer,
    credential_type: str = CredentialType.FINGERPRINT,
    device_user_id: str | None = None,
) -> BiometricCredential:
    """Enroll a customer credential on a device (idempotent).

    Re-enrolling an existing (customer, device) pair refreshes the row —
    credential type, active flag, canonical id — instead of erroring.
    ``device_user_id`` defaults to the customer's canonical tenant-wide
    id (owner decision 2026-10-22); an explicit id is honored verbatim.

    Raises:
        ValidationError: If the credential type is unknown, or the
            requested id is held by a different customer on the device.
    """
    if credential_type not in _CREDENTIAL_TYPES:
        raise ValidationError({"credential_type": f"Unsupported credential type '{credential_type}'."})
    if device_user_id is None:
        device_user_id = resolve_device_user_id(tenant=tenant, customer=customer)
    canonical_id = device_user_id

    with transaction.atomic():
        credential = (
            BiometricCredential.objects.for_tenant(tenant)
            .filter(customer=customer, device=device)
            .order_by("enrolled_at", "pk")
            .first()
        )
        if credential is None:
            _assert_device_slot_free(device=device, device_user_id=canonical_id)
            return BiometricCredential.objects.create(
                tenant=tenant,
                customer=customer,
                device=device,
                credential_type=credential_type,
                device_user_id=canonical_id,
            )

        # Idempotent re-enroll: refresh the row in place.
        if credential.device_user_id != canonical_id:
            _assert_device_slot_free(device=device, device_user_id=canonical_id, exclude_pk=credential.pk)
            credential.device_user_id = canonical_id
        credential.credential_type = credential_type
        credential.is_active = True
        credential.save(update_fields=["device_user_id", "credential_type", "is_active", "updated_at"])
        return credential


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


def resolve_punch_customer(*, device: BiometricDevice, device_user_id: str) -> Customer | None:
    """Resolve the puncher: exact (device, id) first, then tenant-wide.

    Phase-2 canonical ids are shared across devices, so a punch on
    device B may belong to a credential enrolled on device A — the
    tenant-wide same-id fallback resolves it.
    """
    if not device_user_id:
        return None
    exact = (
        BiometricCredential.objects.for_tenant(device.tenant)
        .filter(device=device, device_user_id=device_user_id, is_active=True)
        .select_related("customer")
        .first()
    )
    if exact is not None:
        return exact.customer
    fallback = (
        BiometricCredential.objects.for_tenant(device.tenant)
        .filter(device_user_id=device_user_id, is_active=True)
        .select_related("customer")
        .first()
    )
    return fallback.customer if fallback else None


def parse_attlog_punch(raw_line: str) -> tuple[str, datetime | None]:
    """Parse an ATTLOG row: ``<tab>PIN\\tYYYY-MM-DD HH:MM:SS\\t...``.

    The device pushes gym-local wall time (handshake ``TimeZone=5.5``),
    so the naive stamp is made aware in the project timezone (IST) —
    its local date then matches what the gym sees.
    """
    fields = raw_line.split("\t")
    while fields and not fields[0].strip():
        fields.pop(0)
    if len(fields) < 2:
        return "", None
    pin = fields[0].strip()
    try:
        stamp = datetime.strptime(  # noqa: DTZ007 — device stamps carry no tz; make_aware below
            fields[1].strip(), "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        logger.warning("Unparseable ATTLOG timestamp in row %r.", raw_line[:80])
        return pin, None
    return pin, timezone.make_aware(stamp)


def ingest_attlog_rows(*, device: BiometricDevice, rows: list) -> dict:
    """Resolve and pair ATTLOG rows pushed to ``/iclock/cdata``.

    Runs right after the raw bulk_create. Contract with the device-facing
    endpoint: this is best-effort — callers swallow exceptions so the
    plain-text OK response never breaks. Punches whose device_user_id is
    not linked to any active credential are flagged ``is_orphan`` for the
    debug dashboard and excluded from attendance pairing.

    Idempotency: each raw row is processed exactly once — rows carrying
    an ``ingested_at`` stamp are skipped, and every processed row is
    stamped afterwards (orphans included: the sanctioned replay for a
    punch enrolled later is a fresh device re-dump, which arrives as new
    raw rows). Identical punches re-sent by the device therefore fold
    into attendance at most once per raw row; the pairing state machine
    additionally ignores double-reads and stale/out-of-order repeats.

    Returns:
        ``{"paired": int, "orphaned": int, "skipped": int}``.
    """
    from apps.attendance.services import pair_punch

    paired = 0
    skipped = 0
    orphan_pks = []
    done_pks = []
    for row in rows:
        if row.ingested_at is not None:
            skipped += 1
            continue
        pin, punch_ts = parse_attlog_punch(row.raw_line)
        if punch_ts is None:
            punch_ts = row.received_at
        customer = resolve_punch_customer(device=device, device_user_id=pin)
        if customer is None:
            if row.pk is not None:
                orphan_pks.append(row.pk)
        else:
            pair_punch(tenant=device.tenant, customer=customer, branch=device.branch, punch_ts=punch_ts)
            paired += 1
        if row.pk is not None:
            done_pks.append(row.pk)
    if orphan_pks:
        PunchLogRaw.objects.filter(pk__in=orphan_pks).update(is_orphan=True)
    stamped = timezone.now()
    if done_pks:
        PunchLogRaw.objects.filter(pk__in=done_pks).update(ingested_at=stamped)
    # Sync the caller's in-memory rows so a repeated call with the same
    # list sees the stamps and stays a no-op.
    orphan_set = set(orphan_pks)
    done_set = set(done_pks)
    for row in rows:
        if row.pk in done_set:
            row.ingested_at = row.ingested_at or stamped
        if row.pk in orphan_set:
            row.is_orphan = True
    return {"paired": paired, "orphaned": len(orphan_pks), "skipped": skipped}


def _device_walltime(value: datetime) -> str:
    """Render a timestamp the way the device's wall clock reads it (IST)."""
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")


def queue_history_pull(
    *,
    device: BiometricDevice,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    """Queue a stored-transaction re-upload for an ADMS device.

    Mechanism (push SDK "data query", pushver 2.4.x): the command
    ``DATA QUERY ATTLOG StartTime=<ts>\\tEndTime=<ts>`` rides the
    existing :class:`~apps.access.models.DeviceCommandQueue` — the
    device receives it verbatim on its next ``/iclock/getrequest`` poll,
    acks via ``/iclock/devicecmd``, and re-uploads its stored attendance
    as ATTLOG rows to ``/iclock/cdata?table=ATTLOG``, where they land in
    :class:`~apps.access.models.PunchLogRaw` verbatim and flow through
    :func:`ingest_attlog_rows` like live punches. The handshake options
    stay untouched.

    Args:
        device: The ADMS push-mode device to pull from.
        start: Window start (aware datetime); defaults to :data:`HISTORY_EPOCH`.
        end: Window end (aware datetime); defaults to now.

    Returns:
        ``{"queued": True, "mechanism": ..., "detail": ..., "device_id": ...,
        "last_seen_at": ...}`` — the API response payload.

    Raises:
        ValidationError: For devices that do not speak ADMS (non-eSSL/ZKTeco
            vendors, or push-mode is not webhook).
    """
    if device.connection_type != ConnectionType.WEBHOOK or device.vendor not in ADMS_HISTORY_VENDORS:
        raise ValidationError(
            {
                "detail": (
                    f"History pull requires an ADMS push-mode eSSL/ZKTeco device; "
                    f"'{device.name}' is vendor '{device.vendor}' via '{device.connection_type}'."
                )
            }
        )

    if start is None:
        start = timezone.make_aware(HISTORY_EPOCH)
    elif timezone.is_naive(start):
        start = timezone.make_aware(start)
    if end is None:
        end = timezone.now()
    elif timezone.is_naive(end):
        end = timezone.make_aware(end)

    pending = (
        DeviceCommandQueue.objects.filter(device=device, command=HISTORY_PULL_COMMAND, executed_at__isnull=True)
        .order_by("created_at", "pk")
        .first()
    )
    if pending is not None:
        detail = "A history pull is already queued and undelivered; the device will re-upload on its next poll."
    else:
        DeviceCommandQueue.objects.create(
            tenant=device.tenant,
            device=device,
            command=HISTORY_PULL_COMMAND,
            payload={
                "text": f"{HISTORY_PULL_COMMAND} StartTime={_device_walltime(start)}\tEndTime={_device_walltime(end)}",
                "mechanism": HISTORY_PULL_MECHANISM,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        detail = (
            f"Queued {HISTORY_PULL_COMMAND} for the next poll; stored punches arrive at "
            "/iclock/cdata between the requested window bounds."
        )
    return {
        "queued": True,
        "mechanism": HISTORY_PULL_MECHANISM,
        "detail": detail,
        "device_id": device.pk,
        "last_seen_at": device.last_seen_at,
    }


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
