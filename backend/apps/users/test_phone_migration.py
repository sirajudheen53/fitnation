"""Data-migration tests for issue #88: existing customer phones → E.164.

The local suite builds tables from models WITHOUT running migrations (CI runs
them on Postgres), so the migration's RunPython callable is executed directly
against the real models via the global app registry — the exact code that
will run on prod. The rule function is pinned COPIED inside the migration
module (utility edits must never retroactively change what ran), so its edge
cases are asserted from the migration module itself: leading 0, ``91``/``091``
prefixes, spaces/dashes, already-E.164, other-country ``+`` numbers, and the
ambiguous values that must be left untouched and reported.
"""

from __future__ import annotations

import importlib
import io
from contextlib import redirect_stdout
from typing import Any

from django.apps import apps as global_apps
from django.test import TestCase

from apps.customers.models import Customer
from apps.tenants.services import provision_tenant
from apps.users.models import User

# Django loads migrations by importlib string (the file starts with a digit),
# so tests do the same to pin the exact deployed code.
migration_module: Any = importlib.import_module("apps.users.migrations.0008_normalize_customer_phones_e164")
normalize_india_e164 = migration_module.normalize_india_e164
normalize_customer_phones = migration_module.normalize_customer_phones

FLAG_ON = {"app_access": True}


def run_migration() -> str:
    """Run the #88 data migration against the real models; return its report."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        normalize_customer_phones(global_apps, None)
    return buffer.getvalue()


class MigrationRuleTests(TestCase):
    """The pinned rule inside the migration module — the exact transforms
    prod rows will undergo."""

    def test_indian_shapes_normalize(self) -> None:
        """Bare / trunk-prefixed / country-coded / separator-padded forms."""
        cases = {
            "8606806956": "+918606806956",
            "08606806956": "+918606806956",
            "918606806956": "+918606806956",
            "0918606806956": "+918606806956",
            "86068 06956": "+918606806956",
            "860-680-6956": "+918606806956",
            "+918606806956": "+918606806956",
            "+91 86068 06956": "+918606806956",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_india_e164(raw), expected)

    def test_ambiguous_values_are_untouched(self) -> None:
        """Wrong length / junk / non-Indian short codes are never guessed."""
        for raw in ["", "12345", "1234567890", "860680695", "not-a-phone", "0"]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_india_e164(raw), raw.strip())

    def test_other_country_plus_numbers_keep_value_drop_separators(self) -> None:
        """A non-Indian +number is never re-cased — only cleaned."""
        self.assertEqual(normalize_india_e164("+1-202-555-0147"), "+12025550147")


class MigrateCustomerPhonesTests(TestCase):
    """The RunPython callable against real models: customers migrate, staff
    rows and ambiguity stay, the report names what it left behind."""

    def setUp(self) -> None:
        """One tenant and the prod-shaped rows from the issue evidence."""
        self.tenant = provision_tenant(name="Mig Gym", contact_email="mig@local.test", features=FLAG_ON)

    def _user(self, phone: str, role: str = User.Role.CUSTOMER, email: str | None = None) -> User:
        """A user whose stored phone is forced back to the raw ``phone``."""
        user = User.objects.create_user(
            email=email or f"mig.{phone.strip('+') or 'none'}.{role}@fitnation.local",
            password="x",
            first_name="Mig",
            last_name="Rant",
            role=role,
            tenant=self.tenant,
            phone=phone,
        )
        if phone != user.phone:  # save() already normalized — force legacy shape
            User.objects.filter(pk=user.pk).update(phone=phone)
            user.refresh_from_db()
        return user

    def _customer(self, phone: str, **extra) -> Customer:
        """A profile row forced back to the raw ``phone``."""
        customer = Customer.objects.create(tenant=self.tenant, name="Mig Rant", phone=phone, **extra)
        if phone != customer.phone:
            Customer.objects.filter(pk=customer.pk).update(phone=phone)
            customer.refresh_from_db()
        return customer

    def test_customer_rows_migrate_to_e164(self) -> None:
        """The login key (users.role=customer) and the profile mirror both
        land on E.164 — the exact shapes seen in the prod evidence."""
        user = self._user("8606806956")  # the Farzeen row from #88
        customer = self._customer("08606806956")
        spaced = self._customer("86068-06957")
        prefixed = self._user("918606806958", email="mig.91prefix@fitnation.local")

        report = run_migration()

        user.refresh_from_db()
        customer.refresh_from_db()
        spaced.refresh_from_db()
        prefixed.refresh_from_db()
        self.assertEqual(user.phone, "+918606806956")
        self.assertEqual(customer.phone, "+918606806956")
        self.assertEqual(spaced.phone, "+918606806957")
        self.assertEqual(prefixed.phone, "+918606806958")
        self.assertIn("4 rows -> E.164", report)

    def test_staff_rows_are_out_of_scope(self) -> None:
        """Trainers don't phone-login: their raw rows are left as-is (the
        prod trainer row from the #88 evidence) and normalize on next write."""
        trainer = self._user("8606806959", role=User.Role.TRAINER)

        run_migration()

        trainer.refresh_from_db()
        self.assertEqual(trainer.phone, "8606806959")

    def test_already_e164_and_other_country_rows_pass_through(self) -> None:
        """Canonical rows are skipped silently — no churn on a re-run."""
        e164 = self._user("+919876543210")
        other = self._customer("+1-202-555-0147")

        report = run_migration()

        e164.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(e164.phone, "+919876543210")
        self.assertEqual(other.phone, "+12025550147")  # separator cleanup is a real write
        self.assertIn("nothing ambiguous left behind", report)

    def test_ambiguous_rows_left_untouched_and_reported(self) -> None:
        """Junk values stay byte-identical and are named in the report."""
        junk_user = self._user("12345", email="mig.junk@fitnation.local")
        junk_customer = self._customer("not-a-phone")

        report = run_migration()

        junk_user.refresh_from_db()
        junk_customer.refresh_from_db()
        self.assertEqual(junk_user.phone, "12345")
        self.assertEqual(junk_customer.phone, "not-a-phone")
        self.assertIn("AMBIGUOUS rows left untouched", report)
        self.assertIn("12345", report)
        self.assertIn("not-a-phone", report)

    def test_blank_phones_are_never_touched(self) -> None:
        """Empty strings are not login keys — excluded from the pass."""
        user = self._user("", email="mig.blank@fitnation.local")
        customer = Customer.objects.create(tenant=self.tenant, name="No Phone")

        report = run_migration()

        user.refresh_from_db()
        customer.refresh_from_db()
        self.assertEqual(user.phone, "")
        self.assertEqual(customer.phone, "")
        self.assertIn("nothing ambiguous left behind", report)

    def test_migration_is_idempotent(self) -> None:
        """A second run rewrites nothing (safe against a retryed deploy)."""
        self._user("8606806956")
        self._customer("08606806956")

        first = run_migration()
        second = run_migration()

        self.assertIn("2 rows -> E.164", first)
        self.assertIn("0 rows -> E.164", second)
