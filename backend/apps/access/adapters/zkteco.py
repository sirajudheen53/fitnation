"""ZKTeco ADMS adapter (Sprint 9, issue #28)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.utils import timezone

from apps.access.adapters.base import BiometricAdapter

if TYPE_CHECKING:
    from datetime import datetime

    from apps.access.models import BiometricDevice

logger = logging.getLogger(__name__)


class ZKTecoADMSAdapter(BiometricAdapter):
    """ZKTeco ADMS protocol adapter (issue #28).

    ADMS: devices poll our HTTP endpoint for commands; they push
    attendance events to us. No inbound connectivity needed.
    """

    vendor_label = "ZKTeco"
    protocol = "adms"

    def sync_allow_list(
        self,
        device: BiometricDevice,
        credentials: Any,
    ) -> dict:
        """Push the allow-list via ADMS command queue (device polls us)."""
        from apps.access.models import DeviceCommandQueue

        queued = 0
        for cred in credentials:
            DeviceCommandQueue.objects.create(
                tenant=device.tenant,
                device=device,
                command="DATA UPDATE USER",
                payload={
                    "pin": cred.device_user_id,
                    "name": cred.customer.name,
                    "privilege": 0,
                    "cardno": cred.device_user_id if cred.credential_type == "card" else "",
                },
            )
            queued += 1

        return {
            "ok": True,
            "pushed": queued,
            "detail": f"Queued {queued} user updates for next ADMS poll",
            "protocol": self.protocol,
        }

    def fetch_events(
        self,
        device: BiometricDevice,
        since: datetime | None = None,
    ) -> list[dict]:
        """Fetch events already stored by ADMS (device pushes to us)."""
        from apps.access.selectors import list_access_logs

        qs = list_access_logs(tenant=device.tenant, device=device)
        if since is not None:
            qs = qs.filter(event_timestamp__gte=since)
        return [
            {
                "device_user_id": log.device_user_id,
                "event_type": log.event_type,
                "timestamp": log.event_timestamp.isoformat(),
                "credential_type": log.credential_type,
            }
            for log in qs[:100]
        ]

    def test_connection(self, device: BiometricDevice) -> dict:
        """ADMS is passive — check last_seen freshness instead of probing."""
        if device.last_seen_at is None:
            return {
                "online": False,
                "detail": "Device has never connected to ADMS endpoint.",
                "protocol": self.protocol,
            }
        age = timezone.now() - device.last_seen_at
        if age.total_seconds() > 600:
            return {
                "online": False,
                "detail": f"Last seen {int(age.total_seconds() // 60)}min ago (stale).",
                "last_seen": device.last_seen_at.isoformat(),
                "protocol": self.protocol,
            }
        return {
            "online": True,
            "detail": f"Connected {int(age.total_seconds())}s ago.",
            "last_seen": device.last_seen_at.isoformat(),
            "protocol": self.protocol,
        }

    def handle_adms_request(self, request_data: dict, device: BiometricDevice) -> str:
        """Process an inbound ADMS poll from a device."""
        if "table" in request_data and "ATTLOG" in str(request_data.get("table", "")):
            self._ingest_attlog(request_data, device)

        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at"])

        pending = self._pop_pending_commands(device)
        if pending:
            return "\n".join(pending)
        return "OK"

    def _ingest_attlog(self, data: dict, device: BiometricDevice) -> None:
        """Store attendance/access log entries pushed by the device."""
        from apps.access.services import record_event

        records = data.get("records", [])
        for rec in records:
            record_event(
                device=device,
                customer=None,
                device_user_id=str(rec.get("pin", "")),
                credential_type="fingerprint",
                event_type="entry",
                event_timestamp=rec.get("time", ""),
                raw_payload=rec,
            )

    def _pop_pending_commands(self, device: BiometricDevice) -> list[str]:
        """Pop and mark-executed all pending commands for a device."""
        from apps.access.models import DeviceCommandQueue

        queued = DeviceCommandQueue.objects.filter(device=device, executed_at__isnull=True)
        commands = []
        for cmd in queued:
            payload = cmd.payload
            pin = payload.get("pin", "")
            name = payload.get("name", "")
            cardno = payload.get("cardno", "")
            commands.append(
                f"DATA UPDATE USER\tPIN={pin}\tName={name}\tPri=0\tPasswd=\tCard={cardno}\tGrp=1"
            )
            cmd.executed_at = timezone.now()
            cmd.save(update_fields=["executed_at"])
        return commands


class EsslADMSAdapter(ZKTecoADMSAdapter):
    """eSSL adapter — same ZKTeco firmware, different branding (issue #30)."""

    vendor_label = "eSSL"
