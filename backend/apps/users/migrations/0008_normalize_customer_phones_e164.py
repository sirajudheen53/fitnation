"""Normalize existing customer phone numbers to E.164 (issue #88).

The Firebase phone-auth login matches ``User.phone`` EXACTLY against the
token's E.164 ``phone_number`` claim, while every write path so far stored
whatever the desk typed — 8 of 9 prod phone rows had no leading ``+``, which
is how a real member got a generic 400 at login (issue #88, 2026-10-26).

One-off data migration over BOTH customer phone surfaces:

* ``users.phone`` for customer-role rows — the login key;
* ``customers.phone`` — the profile mirror the ERP converges on.

Rule (mirrors ``apps/users/phone.normalize_e164``, deliberately COPIED here
so future edits to the utility can never retroactively change what this
migration did): Indian national numbers ``^[2-9]\\d{9}$``, including the
``0``/``91``/``091``-prefixed and separator-padded entry forms, become
``+91XXXXXXXXXX``. Ambiguous values (wrong length, non-Indian ``+`` numbers,
junk) are left UNTOUCHED and reported — the tolerant lookup ladder
(``phone_lookup_candidates``) keeps them reachable, and write-path
normalization leaves them stable.

Scoped to customer rows per the ticket; staff phones (e.g. the trainer row
in the prod evidence) are not login keys and normalize on their next write.
Idempotent — already-E.164 values are detected unchanged and skipped.
Irreversible (originals are not preserved); reverse is a documented no-op.
"""

from __future__ import annotations

import re

from django.db import migrations

DEFAULT_COUNTRY_CODE = "91"

_NATIONAL_RE = re.compile(r"[2-9]\d{9}\Z")
_SEPARATORS_RE = re.compile(r"[\s().\-]")
_PREFIXES = ("0", "91", "091")
# Already-canonical international storage (any +country code) — skipped
# silently, distinct from the ambiguous rows the report names.
_INTERNATIONAL_RE = re.compile(r"\+\d+\Z")

CUSTOMER_ROLE = "customer"


def _national_number(digits: str) -> str | None:
    """The 10-digit Indian national number inside ``digits``, else ``None``."""
    if _NATIONAL_RE.fullmatch(digits):
        return digits
    for prefix in _PREFIXES:
        if digits.startswith(prefix) and _NATIONAL_RE.fullmatch(digits[len(prefix) :]):
            return digits[len(prefix) :]
    return None


def normalize_india_e164(value: str) -> str:
    """The storage rule of ``apps/users/phone.normalize_e164``, pinned here."""
    text = str(value or "").strip()
    if not text:
        return ""
    cleaned = _SEPARATORS_RE.sub("", text)
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if not digits:
            return text
        rest = digits[len(DEFAULT_COUNTRY_CODE) :] if digits.startswith(DEFAULT_COUNTRY_CODE) else ""
        national = _national_number(rest) if rest else None
        if national is not None:
            return f"+{DEFAULT_COUNTRY_CODE}{national}"
        return cleaned
    national = _national_number("".join(ch for ch in cleaned if ch.isdigit()))
    if national is not None:
        return f"+{DEFAULT_COUNTRY_CODE}{national}"
    return text


def normalize_customer_phones(apps, schema_editor) -> None:
    """Rewrite customer phone rows to E.164; report anything left untouched."""
    User = apps.get_model("users", "User")
    Customer = apps.get_model("customers", "Customer")

    migrated = 0
    skipped: list[str] = []
    for queryset, label in (
        (
            User.objects.filter(role=CUSTOMER_ROLE).exclude(phone=""),
            f"users.{CUSTOMER_ROLE}",
        ),
        (Customer.objects.exclude(phone=""), "customers"),
    ):
        for row in queryset.iterator():
            normalized = normalize_india_e164(row.phone)
            if normalized != row.phone:
                # A real normalization (Indian shape -> E.164, or separator
                # cleanup on an international + number) — write it.
                row.phone = normalized
                row.save(update_fields=["phone"])
                migrated += 1
            elif not _INTERNATIONAL_RE.fullmatch(row.phone):
                # Unchanged and not already canonical international — ambiguous
                # (wrong length, junk). Left as-is, reported for ops.
                skipped.append(f"{label}#{row.pk}={row.phone!r}")

    # The report the ticket asks for: every row left untouched, by value —
    # ops re-checks these against the tenant before hand-editing.
    if skipped:
        print(  # migration-runner stdout, visible in deploy logs
            f"[#88] phone normalization: {migrated} rows -> E.164; "
            f"{len(skipped)} AMBIGUOUS rows left untouched:\n  " + "\n  ".join(skipped)
        )
    else:
        print(
            f"[#88] phone normalization: {migrated} rows -> E.164; nothing ambiguous left behind."
        )  # migration-runner stdout


class Migration(migrations.Migration):
    """Data backfill for issue #88 (see module docstring)."""

    dependencies = [
        ("users", "0007_alter_trainercustomerassignment_customer"),
        ("customers", "0007_customer_deleted_at_alter_customer_user"),
    ]

    operations = [
        migrations.RunPython(normalize_customer_phones, migrations.RunPython.noop),
    ]
