"""Server-rendered debug dashboard for live ADMS device traffic.

Read-only diagnostics over the push-protocol stack: a plain Django
template (no JS/framework dependencies, 10s meta refresh) showing the
device registry with liveness, the newest raw punch lines, and the
newest inbound ``/iclock/*`` requests — including the unknown-SN 403s.
Gated to Django-admin staff via ``staff_member_required``.
"""

from __future__ import annotations

from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.access.models import AdmsRequestLog, BiometricDevice, PunchLogRaw

RECENT_ROW_LIMIT = 50
PREVIEW_CHARS = 200


def _local_day_start() -> datetime:
    """Start of today in the project timezone (gym operators' local days)."""
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


@staff_member_required
def biometrics_debug(request: HttpRequest) -> HttpResponse:
    """Render the live ADMS traffic dashboard (GET only, read-only).

    An optional ``?sn=<serial>`` narrows all three sections to one
    device serial.
    """
    sn = (request.GET.get("sn") or "").strip()

    devices = BiometricDevice.objects.select_related("tenant", "branch").annotate(
        today_request_count=Count(
            "adms_request_logs",
            filter=Q(adms_request_logs__created_at__gte=_local_day_start()),
        )
    )
    punches = PunchLogRaw.objects.select_related("device", "device__tenant").order_by("-received_at", "-pk")
    requests = AdmsRequestLog.objects.select_related("device", "tenant").order_by("-created_at", "-pk")

    if sn:
        devices = devices.filter(serial_number=sn)
        punches = punches.filter(device__serial_number=sn)
        requests = requests.filter(sn=sn)

    context = {
        "sn": sn,
        "devices": devices,
        "punches": punches[:RECENT_ROW_LIMIT],
        "requests": requests[:RECENT_ROW_LIMIT],
        "preview_chars": PREVIEW_CHARS,
        "row_limit": RECENT_ROW_LIMIT,
    }
    return render(request, "access/biometrics_debug.html", context)
