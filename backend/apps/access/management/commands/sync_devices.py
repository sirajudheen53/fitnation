"""Sync allow-lists to all active biometric devices (issue #24).

Covers passive access changes (notably plan expiry, which no write
touchpoint observes) when scheduled via cron/system timer, e.g. hourly:

    python3 manage.py sync_devices --settings=config.settings.local
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.access.models import BiometricDevice
from apps.access.services import sync_device


class Command(BaseCommand):
    """Push the resolved allow-list to every active device, per tenant."""

    help = "Sync allow-lists to all active biometric devices (run via cron)."

    def add_arguments(self, parser: Any) -> None:
        """Add an optional tenant filter."""
        parser.add_argument(
            "--tenant",
            type=int,
            help="Limit the sync to a single tenant id (default: all tenants).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the sync and report per-device outcomes."""
        devices = BiometricDevice.objects.filter(is_active=True).select_related("tenant")
        if options["tenant"]:
            devices = devices.filter(tenant_id=options["tenant"])

        synced = 0
        failed = 0
        for device in devices:
            result = sync_device(device)
            if result["synced"]:
                synced += 1
                self.stdout.write(
                    f"[tenant {device.tenant_id}] device {device.pk} '{device.name}': "
                    f"pushed {result.get('pushed', 0)} credentials"
                )
            else:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[tenant {device.tenant_id}] device {device.pk} '{device.name}': "
                        f"sync failed — {result['detail']}"
                    )
                )

        summary = f"Synced {synced} device(s); {failed} failed."
        if failed:
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
