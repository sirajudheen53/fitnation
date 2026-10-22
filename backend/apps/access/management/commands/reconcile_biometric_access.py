"""Daily drift-only reconciliation of biometric device user state.

Passive safety net for the phase-2 metadata gate: catches members whose
membership lapsed (or was cancelled) without a propagation touchpoint,
and members whose device user was never pushed. Scheduling is EXTERNAL —
the backend has no Celery — so run it from cron / Cloud Scheduler, e.g.
nightly:

    python3 manage.py reconcile_biometric_access --settings=config.settings.prod

Drift-only by construction: the enqueue path shares the deterministic
dedupe with the realtime propagation (skip identical pending, skip
identical delivered <24h), so re-running — or colliding with the
realtime path — never double-queues a command.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.access.models import BiometricCredential
from apps.access.propagation import (
    DELETE_COMMAND,
    UPDATE_COMMAND,
    propagate_customer_biometric_state,
)
from apps.customers.models import Customer
from apps.tenants.models import Tenant


class Command(BaseCommand):
    """Reconcile every tenant's device user state with membership state."""

    help = (
        "Enqueue drift-only biometric device user commands (UPDATE while "
        "membership active-or-in-cool-off, DELETE past cool-off/cancelled). "
        "Safe to re-run; schedule externally (cron/Cloud Scheduler)."
    )

    def add_arguments(self, parser: Any) -> None:
        """Add an optional tenant filter."""
        parser.add_argument(
            "--tenant",
            type=int,
            help="Limit the reconciliation to a single tenant id (default: all tenants).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Walk tenants and reconcile each customer with active credentials."""
        tenants = Tenant.objects.all().order_by("pk")
        if options["tenant"]:
            tenants = tenants.filter(pk=options["tenant"])

        totals = {UPDATE_COMMAND: 0, DELETE_COMMAND: 0, "skipped": 0, "customers": 0}
        for tenant in tenants:
            customer_ids = (
                BiometricCredential.objects.for_tenant(tenant)
                .filter(is_active=True)
                .values_list("customer_id", flat=True)
                .distinct()
            )
            per_tenant = {UPDATE_COMMAND: 0, DELETE_COMMAND: 0, "skipped": 0, "customers": 0}
            for customer in Customer.objects.filter(id__in=list(customer_ids), tenant=tenant).iterator():
                per_tenant["customers"] += 1
                for result in propagate_customer_biometric_state(customer=customer):
                    if not result["enqueued"]:
                        per_tenant["skipped"] += 1
                    elif result["action"] == "update":
                        per_tenant[UPDATE_COMMAND] += 1
                    else:
                        per_tenant[DELETE_COMMAND] += 1

            totals["customers"] += per_tenant["customers"]
            totals[UPDATE_COMMAND] += per_tenant[UPDATE_COMMAND]
            totals[DELETE_COMMAND] += per_tenant[DELETE_COMMAND]
            totals["skipped"] += per_tenant["skipped"]
            self.stdout.write(
                f"[tenant {tenant.pk} '{tenant.name}'] customers={per_tenant['customers']} "
                f"updates_enqueued={per_tenant[UPDATE_COMMAND]} "
                f"deletes_enqueued={per_tenant[DELETE_COMMAND]} "
                f"skipped_no_drift={per_tenant['skipped']}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Reconciled {totals['customers']} customer(s): "
                f"{totals[UPDATE_COMMAND]} update(s) enqueued, "
                f"{totals[DELETE_COMMAND]} delete(s) enqueued, "
                f"{totals['skipped']} already in sync."
            )
        )
