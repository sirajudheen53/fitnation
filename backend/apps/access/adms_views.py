"""ADMS push-protocol endpoints for ZKTeco/eSSL devices (phase 1).

Real device firmware on gym LANs calls these root-level paths, so the
wire contract is strict:

- Responses are ALWAYS plain text — never JSON, even on errors.
- No token auth: the serial number (``SN``/``sn`` query param) is
  whitelisted against active :class:`BiometricDevice` rows.
- Paths are fixed by firmware (``/iclock/...``) — mount at root, never
  under ``/api/v1``.
"""

from __future__ import annotations

import logging
from typing import cast
from urllib.parse import parse_qs

from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.access.models import (
    AdmsRequestLog,
    BiometricCredential,
    BiometricDevice,
    DeviceCommandQueue,
    PunchLogRaw,
)

logger = logging.getLogger(__name__)

# Handshake option block served on GET /iclock/cdata (guide spellings).
_HANDSHAKE_LINES = (
    "GET OPTION FROM: {sn}",
    "ATTLOGStamp=None",
    "RealTime=1",
    "TransInterval=1",
    "Delay=10",
    "TimeZone=5.5",
)

_KNOWN_TABLES = ("ATTLOG", "OPERLOG", "ATTPHOTO", "USER")


def _plain(body: str, status: int = 200) -> HttpResponse:
    """Return a plain-text response — devices can never parse JSON."""
    return HttpResponse(body, status=status, content_type="text/plain")


def _request_sn(request: HttpRequest) -> str:
    """Serial number from the query string; casing varies by firmware."""
    return (request.GET.get("SN") or request.GET.get("sn") or "").strip()


def _resolve_device(sn: str) -> BiometricDevice | None:
    """Whitelist lookup across tenants — devices identify by serial only."""
    if not sn:
        return None
    return cast(BiometricDevice, BiometricDevice.objects.filter(serial_number=sn, is_active=True).first())


def _log_request(request: HttpRequest, *, sn: str, device: BiometricDevice | None, body: str) -> None:
    """Persist one audit row per inbound device request.

    Never raises: a logging failure must not break the device contract.
    """
    try:
        AdmsRequestLog.objects.create(
            device=device,
            tenant=device.tenant if device else None,
            path=request.path,
            query_string=request.META.get("QUERY_STRING", ""),
            raw_body=body,
            sn=sn,
            remote_addr=request.META.get("REMOTE_ADDR") or "",
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to write AdmsRequestLog for sn=%s", sn)


def _touch_device(device: BiometricDevice) -> None:
    """Stamp device liveness on any successful SN match."""
    device.last_seen_at = timezone.now()
    device.save(update_fields=["last_seen_at", "updated_at"])


def _detect_table(request: HttpRequest, body: str) -> str:
    """Table name from the ``table`` query param, else leading body markers.

    Field/param spellings vary by firmware, so parse defensively and fall
    back to ``UNKNOWN`` rather than guessing.
    """
    table = (request.GET.get("table") or "").strip().upper()
    if table:
        return table
    for line in body.splitlines()[:3]:
        stripped = line.strip().upper()
        for known in _KNOWN_TABLES:
            if stripped.startswith(known):
                return known
    return "UNKNOWN"


@csrf_exempt
def cdata(request: HttpRequest) -> HttpResponse:
    """/iclock/cdata — GET: options handshake; POST: attendance push."""
    sn = _request_sn(request)
    device = _resolve_device(sn)
    body = request.body.decode("utf-8", errors="replace") if request.method == "POST" else ""
    _log_request(request, sn=sn, device=device, body=body)
    if device is None:
        return _plain("", status=403)

    _touch_device(device)

    if request.method == "GET":
        return _plain("\n".join(line.format(sn=sn) for line in _HANDSHAKE_LINES) + "\n")

    table = _detect_table(request, body)
    rows = [
        PunchLogRaw(tenant=device.tenant, device=device, table_name=table, raw_line=line)
        for line in body.splitlines()
        if line.strip()
    ]
    if rows:
        PunchLogRaw.objects.bulk_create(rows)
        if table == "ATTLOG":
            # Phase-2 pairing is best-effort by contract: the device must
            # always get its plain-text OK, even if pairing blows up —
            # the raw rows are already stored for replay.
            try:
                from apps.access.services import ingest_attlog_rows

                ingest_attlog_rows(device=device, rows=rows)
            except Exception:  # noqa: BLE001
                logger.exception("ATTLOG pairing failed for device %s; raw rows kept.", device.pk)
    return _plain("OK")


def _command_identity(queued: DeviceCommandQueue) -> tuple[str, str]:
    """Resolve (pin, name) from the payload, falling back to the credential."""
    payload = queued.payload or {}
    pin = str(payload.get("pin") or payload.get("device_user_id") or "")
    name = str(payload.get("name") or "")
    credential_id = payload.get("credential_id") or payload.get("credential")
    if (not pin or not name) and credential_id:
        credential = BiometricCredential.objects.filter(pk=credential_id).select_related("customer").first()
        if credential is not None:
            pin = pin or credential.device_user_id
            name = name or credential.customer.name
    return pin, name


def _render_and_stamp(queued: DeviceCommandQueue) -> str:
    """Render the queue row into guide wire format and stamp delivery.

    Phase-2 rows (apps/access/propagation) carry the adapter-formatted
    command in ``payload["text"]`` and are delivered verbatim, prefixed
    ``C:<id>:`` so the devicecmd ack can reference the row. Legacy phase-1
    rows (payload without text) keep the guide rendering:
    ``C:<id>:DATA UPDATE USERINFO PIN=<pin>\\tName=<name>\\tPri=0\\tGrp=1``
    """
    text = (queued.payload or {}).get("text")
    if text:
        rendered = f"C:{queued.pk}:{text}"
    else:
        pin, name = _command_identity(queued)
        if "DELETE" in queued.command.upper():
            rendered = f"C:{queued.pk}:DATA DELETE USERINFO PIN={pin}"
        else:
            rendered = f"C:{queued.pk}:DATA UPDATE USERINFO PIN={pin}\tName={name}\tPri=0\tGrp=1"
    # Per the model docstring: commands are held until the device's next
    # poll delivers them — executed_at is stamped on delivery.
    queued.executed_at = timezone.now()
    queued.save(update_fields=["executed_at"])
    return rendered


@csrf_exempt
def getrequest(request: HttpRequest) -> HttpResponse:
    """/iclock/getrequest — deliver the oldest undelivered queued command."""
    sn = _request_sn(request)
    device = _resolve_device(sn)
    _log_request(request, sn=sn, device=device, body="")
    if device is None:
        return _plain("", status=403)

    _touch_device(device)

    queued = (
        DeviceCommandQueue.objects.filter(device=device, executed_at__isnull=True).order_by("created_at", "pk").first()
    )
    if queued is None:
        return _plain("OK")
    return _plain(_render_and_stamp(queued))


def _confirmed_row_id(body: str) -> int | None:
    """Extract the queue row id from an ``ID=<id>&Return=<code>`` body."""
    parsed = parse_qs(body or "", keep_blank_values=True)
    for key, values in parsed.items():
        if key.upper() == "ID" and values and values[0].strip().isdigit():
            return int(values[0].strip())
    return None


@csrf_exempt
def devicecmd(request: HttpRequest) -> HttpResponse:
    """/iclock/devicecmd — device acknowledges a delivered command."""
    sn = _request_sn(request)
    device = _resolve_device(sn)
    body = request.body.decode("utf-8", errors="replace")
    _log_request(request, sn=sn, device=device, body=body)
    if device is None:
        return _plain("", status=403)

    row_id = _confirmed_row_id(body)
    if row_id is not None:
        row = DeviceCommandQueue.objects.filter(pk=row_id, device=device, executed_at__isnull=True).first()
        if row is not None:
            row.executed_at = timezone.now()
            row.save(update_fields=["executed_at"])
    return _plain("OK")
