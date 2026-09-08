"""Unified QA seeding command.

Seeds everything QA needs, in dependency order, against whatever database the
active settings point at (local SQLite, QA Postgres, Cloud Run — no settings
manipulation here):

1. Platform admin + default tenant/branch + base catalogs
   (admin@fitnation.test, "FitNation Test Gym", food items, permissions,
   tenant-1 exercises + marketplace products)
2. FitGym A / FitGym B regression tenants (port of backend/seed_qa.py)
3. Tenant-1 staff (owner@fitnation.test / manager / dietitian / 4 trainers)
4. IronHouse Fitness (tenant 2): tenant, branches, catalogs, staff
5. With --realistic: full realistic data for tenants 1 and 2
   (customers, memberships, payments/invoices, diet, workouts, operations)

Idempotent — safe to re-run. Existing accounts get their password aligned with
the documented QA values (see QA workspace qa-test-users.md) unless
--no-reset-passwords is passed.

Usage:
    python manage.py seed_qa [--skip-catalogs] [--realistic] [--no-reset-passwords]

On the QA VM (docker-compose stack):
    docker compose -f deploy/qa/docker-compose.qa.yml exec backend \
        python manage.py seed_qa --realistic
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.qa_seed import base_setup, realistic_t1, tenant2, tenant_ab


class Command(BaseCommand):
    """Seed the full QA user inventory + catalogs (+ optional realistic data)."""

    help = (
        "Seed the QA database: platform admin, default tenant/branch, base "
        "catalogs, FitGym A/B regression tenants, tenant-1 staff and IronHouse "
        "(tenant 2). --realistic adds full realistic data."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--skip-catalogs",
            action="store_true",
            help="Skip food item / permission / exercise / marketplace catalogs.",
        )
        parser.add_argument(
            "--realistic",
            action="store_true",
            help="Also seed realistic customers, memberships, diet, workouts, "
            "attendance and marketplace carts for tenants 1 and 2.",
        )
        parser.add_argument(
            "--no-reset-passwords",
            action="store_true",
            help="Do not align existing account passwords with the documented " "QA values (default: align).",
        )

    def handle(self, *args, **options) -> None:
        skip_catalogs: bool = options["skip_catalogs"]
        realistic: bool = options["realistic"]
        reset_passwords: bool = not options["no_reset_passwords"]
        echo = self.stdout.write

        echo("=== Seeding QA database ===")
        with transaction.atomic():
            tenant1, branch1 = base_setup.seed_base(
                skip_catalogs=skip_catalogs,
                reset_passwords=reset_passwords,
                echo=echo,
            )
            tenant_ab.seed(reset_passwords=reset_passwords, echo=echo)
            trainers_t1 = realistic_t1.seed_staff(tenant1, reset_passwords=reset_passwords, echo=echo)
            tenant2.seed_base(reset_passwords=reset_passwords, echo=echo)
            if realistic:
                realistic_t1.seed_realistic(tenant1, branch1, trainers_t1, echo=echo)
                tenant2.seed_realistic(reset_passwords=reset_passwords, echo=echo)

        self._print_summary(realistic)

    def _print_summary(self, realistic: bool) -> None:
        from apps.core.qa_seed.common import PASSWORDS

        self.stdout.write("\n=== Seed complete ===")
        self.stdout.write("Key QA logins:")
        rows = [
            ("admin@fitnation.test", PASSWORDS["admin"], "platform_admin / FitNation Test Gym"),
            ("owner_a@fitgyma.qa", PASSWORDS["tenant_ab"], "owner / FitGym A"),
            ("customer_a@fitgyma.qa", PASSWORDS["tenant_ab"], "customer / FitGym A"),
            ("owner_b@fitgymb.qa", PASSWORDS["tenant_ab"], "owner / FitGym B"),
            ("customer_b@fitgymb.qa", PASSWORDS["tenant_ab"], "customer / FitGym B"),
            ("owner@fitnation.test", PASSWORDS["tenant1_staff"], "gym_owner / FitNation Test Gym"),
            ("owner.iron@fitnation.test", PASSWORDS["tenant2_staff"], "gym_owner / IronHouse Fitness"),
        ]
        for email, password, note in rows:
            self.stdout.write(f"  {email:<28} {password:<12} {note}")
        if realistic:
            self.stdout.write("  (customers use Test@1234 in tenant 1, F1tNati0n! in IronHouse)")
        self.stdout.write(
            "\nRegression reminders:\n"
            "  BUG-2026-08-27-01: owner_a sees only FitGym A memberships/payments\n"
            "  BUG-2026-08-27-02: customer_a self-access works\n"
            "  FBOS-026: registered users start is_email_verified=False"
        )
