# Report — Ticket #83: Biometrics auto-checkout 2h after check-in

**Date:** 2026-10-26 · **Branch:** `develop` · **Scope:** backend only (mobile/ untouched, no workflow changes, no prod deploy)

Owner request (Siju, 2026-10-25): the biometric hardware has **no check-out punch**, so a check-in that never
receives a paired check-out must be **auto-checked-out at check-in + 2h**, while manual correction stays possible.

## Mechanism chosen: stamp-on-trigger + idempotent backfill command + derive-on-read (no scheduled job wired)

Prod runs on **Cloud Run with no Celery beat / persistent worker**, so a classic scheduled job isn't available.
The ticket offered derive-on-read **or** stamp-on-trigger, plus an idempotent backfill command. I implemented the
combination, because each layer alone leaves a real gap:

| Layer | What it does | Gap it closes |
|---|---|---|
| **Stamp-on-trigger** (`apply_auto_checkouts`) | One atomic `UPDATE` closes every open check-in past check-in + 2h. Fired from (a) each ADMS punch batch (`ingest_attlog_rows`) and (b) the manual check-in flow (`log_check_in`) | DB-level truth: reports/aggregations (`attendance_stats`, dropout-hour), duplicate-check-in guard, and any DB consumer see closed visits |
| **Backfill command** (`manage.py auto_checkout_backfill`) | Same sweep across all tenants; `--tenant`, `--dry-run`; safe to re-run | Rows that never see another punch (the common case on this hardware) converge without waiting for a trigger; the externally-scheduled replacement for beat |
| **Derive-on-read** (`AttendanceRecordSerializer`) | A record still open past +2h **renders** `check_out_time = check_in + 2h` and `check_out_is_auto = true` — without writing | The UI/API never shows a zombie open visit in the window between the 2h mark elapsing and the next trigger/backfill run |

A Cloud Scheduler → Cloud Run Job hook (not wired, per brief):

```text
Cloud Scheduler: every 15 min → HTTP POST to Cloud Run Jobs API
  gcloud run jobs execute auto-checkout-backfill --region <region>
Job command: python3 manage.py auto_checkout_backfill --settings=config.settings.prod
Auth: job invoker service account; command is idempotent, so overlaps are harmless
```

## Why not a pairing-time rule alone

A pure derive-on-read (never writing) leaves the DB open forever: `attendance_stats` misses the check-outs, the
manual duplicate guard ("Already checked in — check out first") blocks a member's second visit of the day, and any
non-serializer consumer sees stale rows. A pure pairing-time rule misses rows whose device never sends another
punch. Stamping + derivation together cover both, and the stamp is a single indexed-scope `UPDATE` — cheap on every
trigger.

## Never overwrite a real punch (explicit requirement)

- The sweep only touches rows with `check_out_time IS NULL`; a real punch- or admin-stamped value is never
  eligible. Idempotent by construction: stamped rows stop matching, re-runs are no-ops.
- New `AttendanceRecord.check_out_is_auto` flag distinguishes derived check-outs. `pair_punch` treats an
  auto-closed record specially: **any real punch ≥60s after check-in replaces the derived value** — even one that
  arrives *earlier* than the +2h guess (late history pull) — and clears the flag (new outcome
  `auto_check_out_overridden`). Records closed by real punches keep the existing `stale_punch_ignored` guard.
- Admin correction: `PATCH /api/v1/attendance/attendance/{id}/` with `check_out_time` persists and clears the flag
  (`perform_update`); later sweeps never resurrect the auto value. The check-out action and punch path equally win.
- Reads never write: the serializer derivation disappears the moment a real value exists.

## Semantics kept / chosen

- **Phase-2 pairing rules unchanged** (first punch = check-in, ≥60s closes, double-read ignored, last-of-day
  slides): auto-checkout only adds the close when no punch ever arrives.
- **Scope = customer `AttendanceRecord`, all methods** (biometric/qr/manual/mobile): the lingering-open problem is
  method-agnostic and front desk forgets check-outs too. Trainers/staff keep their manual check-out flow (out of
  ticket scope).
- Stamped records flip `status` to `left` (mirrors the manual check-out action); derived-only display leaves
  `status` untouched.

## Files changed

- `backend/apps/attendance/models.py` — `AUTO_CHECKOUT_AFTER = 2h`, `check_out_is_auto` field,
  `auto_check_out_time` derivation property.
- `backend/apps/attendance/migrations/0005_attendancerecord_check_out_is_auto.py` — new field (verified in sync
  with models via `makemigrations --check`).
- `backend/apps/attendance/services.py` — `apply_auto_checkouts` (atomic, tenant-scoped, dry-run), sweep in
  `log_check_in`, auto-aware `pair_punch`.
- `backend/apps/attendance/serializers.py` — derive-on-read + `check_out_is_auto` in `to_representation`;
  field stays writable (admin path intact).
- `backend/apps/attendance/views.py` — `perform_update` clears the flag on check-out writes.
- `backend/apps/access/services.py` — `ingest_attlog_rows` sweeps after pairing (inside the existing
  best-effort/try-except contract; device always gets its plain-text `OK`).
- `backend/apps/attendance/management/commands/auto_checkout_backfill.py` — idempotent backfill
  (`--tenant`, `--dry-run`), scheduling documented in the docstring.
- Tests: `backend/apps/attendance/test_auto_checkout.py` (33 new tests); updated 3 assertions in
  `apps/access/test_punch_pairing.py` / `test_history_pull.py` whose "old lone punch stays open" expectation is
  now — by design — an auto-checkout (their real subject: raw-row storage, single pairing, IST stamps — unchanged).

## Acceptance evidence

- Unpaired check-in → auto-checkout @ +2h: `ApplyAutoCheckoutsTest::test_stamps_open_record_past_two_hours`
  (DB stamp), `SerializerDerivationTest::test_open_record_past_two_hours_renders_auto_checkout` + API
  `test_list_shows_derived_auto_checkout` (UI-facing serializer), boundary at exactly 2h covered.
- Late real punch wins over auto value: `PairPunchAutoOverrideTest` (punch after *and* before the auto value,
  double-read still ignored, real-closed guard intact, tenant-scoped override).
- Admin correction persists: `AutoCheckoutAPITests::test_admin_correction_persists_and_clears_flag` (also proves a
  later sweep can't resurrect the auto value); `test_check_out_action_wins_over_derivation`.
- Idempotent: sweep re-run (`test_rerun_is_idempotent`), command re-run (`test_backfill_is_idempotent`),
  read-never-writes (`test_open_record_past_two_hours_renders_auto_checkout`).
- Tenant isolated: `test_tenant_isolation`, `test_auto_override_scoped_to_tenant`,
  `test_list_derivation_is_tenant_scoped`.
- Full backend suite: **1587 passed, 18 subtests passed** (baseline 1554+), zero failures.
- flake8 with CI's exact invocation (`flake8 . --count --show-source --statistics` from `backend/`): **0 issues**;
  ruff clean on all touched files; black/isort clean.
