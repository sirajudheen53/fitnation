# #82 — Web Dashboard Latency: Backend Performance Audit

**Scope:** every API endpoint the Next.js ERP web app calls on its hot paths — the six
`/api/v1/dashboard/*` endpoints behind the dashboard page (six parallel fetches, so the
slowest endpoint sets page latency), plus the list/detail endpoints behind the members,
payments, memberships, attendance, invoices, reviews, feedback, notifications and
inventory pages.

**Method:** static audit of view querysets, serializer field access, and service-layer
aggregations, cross-checked against model indexes; every finding below was confirmed by
reading the code path end to end, and every "fixed" item carries a regression test.

**Status after this ticket:** items marked **[FIXED — #82]** are implemented on `develop`
with tests. Items marked **[RECOMMENDED]** are ranked follow-ups that were deliberately
left out (contract changes or product decisions required).

---

## Findings, ranked by impact

### 1. Dashboard endpoints hydrated entire tables into Python — **[FIXED — #82]**

`backend/apps/dashboard/services.py`. The dashboard page fires six requests in parallel;
three of them loaded unbounded row sets into Python on every call:

| Endpoint | Old behavior | Cost as data grows |
|---|---|---|
| `GET /dashboard/revenue/` | iterated **every completed payment of the last 12 months** (`paid.iterator()`) to bucket day/week/month | one hydrated row per payment per dashboard load; the dominant dashboard cost for an active gym |
| `GET /dashboard/attendance/` | weekly trend iterated **every check-in the tenant ever had** (no date filter at all) | O(all attendance history) forever — grows every single day |
| `GET /dashboard/overview/` (cache miss) | MRR looped all active memberships + plans; revenue summed in Python; `pending_payments` = `len(get_pending_payments(tenant))` materialized the whole queue incl. dues | once per day per tenant, but it is the first load of the morning |
| `GET /dashboard/pending-payments/` | `_membership_dues` instantiated every lapsed membership + customer + plan | O(lapsed memberships), a list that only grows |
| `GET /dashboard/memberships/` | three separate `.count()` queries for the status breakdown | minor; fixed while there |

**Fix:** all of it is now SQL — `SUM(price * 30 / duration_days)` for MRR, three
`TruncDate`/`TruncWeek`/`TruncMonth` bucket sums for the revenue series (identical
Monday-start / calendar-month bucketing, timezone-correct), a date-windowed `COUNT`
grouped on the indexed `date` column for the weekly trend, a shared `_dues_queryset()`
for both the dues list and the overview's pending count (they can no longer disagree),
and one aggregate for the membership breakdown. Payload shapes are byte-identical.
Regression tests: `apps/dashboard/tests.py::DashboardAggregationTests` (bucket edges,
window cutoffs, mixed-duration MRR, count/list invariant, constant-query guard).

### 2. Hot list endpoints ran N+1 queries on every page — **[FIXED — #82]**

PAGE_SIZE is 20; the worst offender paid **~85 queries per page**:

| Endpoint | Per-row queries | Fixed by |
|---|---|---|
| `GET /payments/` | `customer.name/.phone/.deleted_at`, `membership.plan.name`, `invoices.first()` ≈ 4–5 per row | `select_related(customer, membership, membership__plan)` + `prefetch_related(invoices)` |
| `GET /customers/` | `app_invite_status` ran one `notification_logs` query per member | shared `app_invite_log_prefetch()` (filtered `Prefetch`, `to_attr`) read by the serializer with per-row fallback |
| `GET /reviews/`, `GET /feedback/` | nested `CustomerSerializer` (→ `app_invite_status`) per row | same prefetch through `customer__notification_logs` |
| `GET /memberships/` | `customer.*`, `plan.name/price` ≈ 3 per row | `select_related(customer, plan)` |
| `GET /attendance/` (+ trainer/staff variants) | person + branch names, 2–3 per row | `select_related(...)` per viewset |
| `GET /invoices/`, `GET /notifications/logs/` | customer name per row | `select_related("customer")` |
| `GET /inventory/inventory-items/`, `/maintenance-logs/` | equipment name per row | `select_related("equipment")` |

Regression tests: `backend/tests/test_list_query_counts.py` — seeds 25 rows per relation
and asserts single-digit query counts per list page (the payments guard fails at 85
queries when the join is reverted), plus
`apps/customers/tests.py::AppInviteStatusPrefetchTests` for the invite semantics.

### 3. Non-dashboard read paths aggregated in Python — **[FIXED — #82]**

- `GET /attendance/stats/` (`apps/attendance/selectors.py`) hydrated today's **and the
  whole week's** rows for all three attendance tables (customer/trainer/staff) to
  Counter them: ~4k+ rows per call at 300 daily check-ins. Now grouped in SQL
  (`ExtractHour` histograms + per-day counts on the indexed `date` column). Counts and
  payload shape unchanged; equal-count hour ties now resolve to the newest hour
  (the old Python tie-break was scan-order-dependent and effectively unspecified).
  Tests: `AttendanceStatsAggregationTests`.
- `GET /payments/revenue-summary/` summed amounts in Python six times — each split is
  now one `SUM()`.
- `GET /inventory/inventory-items/low-stock/` loaded **every** inventory item and
  filtered by the `is_low_stock` Python property — now
  `filter(track_inventory=True, stock_quantity__lte=F("low_stock_threshold"))`.

### 4. Missing composite indexes on the hot query shapes — **[FIXED — #82]**

Every #82 query scans a tenant slice with a predicate no existing index covered.
Added (models + migrations, applied and verified; CI exercises them on Postgres):

| Model | Index | Serves |
|---|---|---|
| `Payment` | `(tenant, status, paid_at)` | revenue series, revenue-summary windows |
| `Payment` | `(tenant, status, created_at)` | pending-payments queue ordering |
| `Membership` | `(tenant, status)` | overview + status-breakdown counts |
| `Membership` | `(tenant, end_date)` | lapsed-dues range scan |
| `AttendanceRecord` | `(tenant, date)` | today's count, weekly trend, stats window |
| `NotificationLog` | `(customer, notification_type, created_at)` | app-invite lookup + prefetch |
| `Customer` | `(tenant, created_at)` | member list default ordering (`-created_at`) |

Guard: `backend/tests/test_perf_indexes.py`.

### 5. Unpaginated list endpoints — **[RECOMMENDED]**

`pagination_class = None` or raw `Response(serializer.data, many=True)` bypasses the
default pagination:

- `GET /trainer-sessions/` — grows one row per PT booking forever; **the one that will
  degrade**. `trainer-assignments`, `trainer-performance`, `trainer-schedules`,
  `trainers` are also unpaginated but naturally small.
- Per-customer sub-lists: `progress-photos` (image payloads), `measurements`,
  `fitness-goals` (`apps/customers/views.py` actions) and `progress_summary`'s full
  `weight_trend`.
- `GET /branches/` (plain APIView) — few rows per tenant, cosmetic.

**Why not fixed here:** adding pagination is an API-contract change — the web pages and
the mobile app consume these lists wholesale today. Needs a coordinated frontend/mobile
change (or a `page_size` cap) behind its own ticket.

### 6. Remaining aggregation-in-Python spots — **[RECOMMENDED]**

- `GET /feedback-analytics/` ships every rating row to Python for the sentiment split
  and uses a deprecated `.extra(select=...)` for the trend
  (`apps/feedback/views.py` ~line 160/180). Replaceable with conditional `Count(filter=Q(...))`
  and `TruncDate`. Feedback volume is currently small — medium priority.
- Dashboard `peak_hours` scans the tenant's **all-time** attendance (already in SQL).
  Fine for years; if ever needed, cap it to a trailing window (product decision).
- Member search (`?search=` on customers) uses `icontains` on name/phone/email —
  unindexable without `pg_trgm` / a trigram index. Only matters once tenants hold
  thousands of members.

### 7. Operational notes

- The daily `DashboardCache` row for `overview` still protects the heaviest endpoint;
  the cache-invalidation markers (`mrr` presence, `pending_dues_semantics`) are preserved
  by the rewrite.
- The new indexes are plain `CREATE INDEX` migrations. At current data volumes this is
  fine; if a table ever grows past ~10⁷ rows before this ships, create it
  `CONCURRENTLY` manually first and no-op the migration.

## Commits (this ticket)

1. `perf(dashboard): aggregate overview/revenue/attendance/dues in SQL (#82)`
2. `perf(api): join relations on the hot list endpoints (#82)`
3. `perf(customers): prefetch app-invite state for list payloads (#82)`
4. `perf(attendance,payments,inventory): aggregate hot read paths in SQL (#82)`
5. `perf(db): composite indexes for the dashboard and list hot paths (#82)`

## Verification

- Full backend suite: **1719 passed, 60 subtests** (was 1698 before #82; +21 new tests:
  bucket-edge/aggregation semantics, list query-count guards, index guards).
- flake8 (the CI-gating linter) clean on all touched files; black/isort applied.
- Migrations verified to apply cleanly from scratch; index names present post-migrate.
