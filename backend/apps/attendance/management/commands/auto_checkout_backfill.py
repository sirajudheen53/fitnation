"""Backfill auto-checkouts for every tenant's lingering open check-ins.

Issue #83: the biometric hardware has no check-out punch, so unpaired
check-ins would stay open in the DB forever. This command stamps every
open check-in past check-in + 2h with the derived check-out (safe to
re-run — only rows with a NULL check-out are touched, and a real punch
or admin edit always wins because those rows are never eligible).

Scheduling is EXTERNAL — prod runs on Cloud Run with no Celery beat or
persistent worker — so run it from Cloud Scheduler → Cloud Run Job
(or cron), e.g. every 15 minutes:

    python3 manage.py auto_checkout_backfill --settings=config.settings.prod
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.attendance.services import apply_auto_checkouts
from apps.tenants.models import Tenant


class Command(BaseCommand):
    """Auto-close every tenant's open check-ins past check-in + 2h."""

    help = (
        "Stamp auto-checkouts (check-in + 2h) on open customer attendance "
        "records. Idempotent; never touches rows with a real check-out. "
        "Schedule externally (cron/Cloud Scheduler) — no Celery beat."
    )

    def add_arguments(self, parser: Any) -> None:
        """Add the tenant filter and dry-run flag."""
        parser.add_argument(
            "--tenant",
            type=int,
            help="Limit the backfill to a single tenant id (default: all tenants).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many records would be stamped without writing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Walk tenants and apply the auto-checkout sweep to each."""
        tenants = Tenant.objects.all().order_by("pk")
        if options["tenant"]:
            tenants = tenants.filter(pk=options["tenant"])

        dry_run: bool = options["dry_run"]
        total = 0
        for tenant in tenants:
            count = apply_auto_checkouts(tenant=tenant, dry_run=dry_run)
            total += count
            label = "would stamp" if dry_run else "stamped"
            self.stdout.write(f"[tenant {tenant.pk} '{tenant.name}'] {label} {count} record(s)")

        verb = "eligible" if dry_run else "auto-checked-out"
        self.stdout.write(self.style.SUCCESS(f"Done: {total} record(s) {verb}."))
