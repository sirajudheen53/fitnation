# Report — #84: Pending payments shows zero despite expired memberships

Owner report (Siju, 2026-10-25): *"Why pending payment is zero even if we have expired membership?"*

## Root cause

The pending-payments computation only looked at explicit `Payment` rows:

- **Count** — `apps/dashboard/services.py::get_overview` counted
  `Payment(status="pending")`.
- **List** — `apps/dashboard/services.py::get_pending_payments` listed the same rows
  (`GET /dashboard/pending-payments/`).

A lapsed member (membership `end_date` in the past) generally has **no** pending
`Payment` record — their charge was completed when they joined, and nothing
re-creates a payment when the plan simply runs out. So the metric read 0 while the
gym was in fact owed a renewal from every expired member.

## Semantics rubric (the definition this fix implements)

**A pending due is money the gym is owed right now.** Two sources:

1. **Explicit pending payments** — `Payment` rows with `status="pending"`
   (unchanged; this is the issue #72 send-link queue).
2. **Membership dues (new)** — for each customer whose latest lapsed membership
   has no covering charge, one derived due:

   | Aspect | Rule |
   |---|---|
   | Lapsed | `end_date < today` **and** not `cancelled`. Judged by `end_date`, not the stored `status`, which can be stale until the next save (`compute_status()` semantics). |
   | Amount | The plan's `price` — matches the renewal contract: `POST /memberships/memberships/{id}/renewal/` extends the SAME membership, so the expected renewal due is exactly the plan price. |
   | Due date | The membership's `end_date`. |
   | Coverage | One due per customer — their most recently lapsed membership. |
   | Excluded | Active memberships (`end_date >= today`); cancelled memberships (deliberate exit, nothing owed). |
   | Soft-deleted members | **Included**, flagged `customer_is_deleted` — money is owed regardless, and the #81 contract keeps financial visibility for deleted members (the dashboard widget already renders the `Deleted user` badge). |

**Double-counting guards (brief point 3):**

- A customer with an explicit **pending, membership-kind** `Payment` has their
  charge tracked → the derived due is **suppressed** for that customer.
- A pending **admission-kind** payment does *not* cover a renewal (different
  money) → the due still appears.
- A **completed** payment paid for the past period → the renewal due still
  appears once the membership lapses.

## What changed

No model changes, no migrations, no API shape change, no frontend changes required.

**`backend/apps/dashboard/services.py`**

- `get_pending_payments(tenant)` now returns the unified queue: explicit pending
  payments first (newest first, exactly as before), then derived dues
  (most-lapsed first). Dues carry a **negative id** (`abs(id)` = membership id) so
  they stay unique next to real payment ids in the same list — the row shape
  (`id`, `customer_name`, `customer_is_deleted`, `amount`, `due_date`) is
  untouched, so `PendingPaymentSerializer` and the frontend
  `PendingPayment`/widget code work as-is.
- `get_overview` computes `pending_payments` from the same unified list
  (`len(get_pending_payments(tenant))`) → **count and list can never disagree**.
- Overview cache rows are stamped with `pending_dues_semantics: "issue-84"`
  (stripped by `OverviewSerializer`, never leaves the backend). `_read` rejects
  same-day cache rows lacking the marker, so a pre-#84 cache row can't serve the
  old zero for the rest of the deploy day — same pattern as the existing `"mrr"`
  shape check.

**`backend/apps/dashboard/tests.py`** — new `PendingPaymentsDuesTests` (12 tests):
expired→due (count + list + row shape), active/cancelled excluded, stale stored
status still lapses by date, renewal clears the due, pending membership payment
suppresses (no duplicate), admission-kind and completed payments don't cover,
one due per customer (latest membership, its plan price), deleted-member flag,
tenant isolation, and pre-#84 cache recompute.

## Scope boundary (deliberate)

The **payments page "Pending" tab** (issue #72 queue) is client-filtered from
`GET /payments/` and powers the per-payment "Send payment link" action, which
requires a real `Payment` id. Injecting derived dues there would either pollute
the payment ledger or produce rows whose send-link action 404s — so the tab keeps
showing explicit pending payments only. The **dashboard** (overview count +
pending list) now carries the complete picture and no longer shows
zero-while-expired, which is what the owner reported. Membership dues are
collected via Memberships → Renewal (or record-payment).

Recommended FE follow-up (not in this ticket): render
`GET /dashboard/pending-payments/` dues on the payments page as a separate
"renewal dues" section, or branch on `id < 0` to offer "Record payment"/renewal
instead of "Send link".

## Evidence

- `python3 -m pytest` (full backend suite): **exit 0**, 1554 tests collected
  (baseline 1542 + 12 new) — CI-parity command
  `pytest --cov=. --cov-fail-under=80` passed.
- Coverage: **85.23%** (gate 80%).
- `flake8 . --count --show-source --statistics` (CI's exact invocation): **0 issues**.
- `ruff check` on touched files: **clean**.
- Local tests run on SQLite; no Postgres-only constructs used (`DISTINCT ON`
  avoided — per-customer dedupe done in Python, consistent with the file's
  existing aggregation style).

## Deployment

Backend-only. Same-day overview cache rows computed before this deploy are
recomputed once (marker check) — the owner sees corrected numbers on the first
dashboard load after deploy. No frontend, mobile, or workflow changes; no prod
deploy performed here.
