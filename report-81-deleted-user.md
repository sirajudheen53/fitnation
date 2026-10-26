# Report — #81: Deleted customers render as "Deleted user" at every reference

Siju (2026-10-25): "If a customer is deleted and if we use that reference anywhere — notate it as
deleted user." Scope: backend + ERP frontend (`backend/`, `frontend/`); `mobile/` untouched; no
workflow changes; no prod deploy.

## TL;DR

The ERP delete (`DELETE /customers/{id}/`) hard-deleted the `Customer` row. Every FK from
payments/attendance/assignments/memberships/… is `on_delete=CASCADE`, so a delete silently destroyed
the member's entire history (~20 tables) — and where the row survived by luck (nullable logs), the
UI kept showing the stale name.

#81 changes the delete to a **soft delete with PII scrub**, converging with the in-app GDPR deletion
(`apps/users/services.delete_customer_account`, §8 B8) that already anonymized-in-place:

- `Customer.deleted_at` (nullable timestamp) is the authoritative marker.
- On delete: `deleted_at` set, every personal field scrubbed to neutral (**name → "Deleted user"**,
  email/phone/dob/emergency/address/notes/photo wiped, status inactive, `is_active` off).
- The linked **customer-role portal user is still deleted** in the same transaction (#72 semantics
  preserved: email + phone freed, re-add works for same AND different phone; orphan adoption
  unchanged). `Customer.user` became nullable `SET_NULL` so removing the identity can't cascade into
  the retained row.
- The GDPR self-deletion path now sets the same `deleted_at` marker and the same "Deleted user"
  label — gym-side delete and self-delete render identically everywhere.
- Every cross-app `Customer` FK that carries business/financial/audit history became `PROTECT`
  (payments, invoices, memberships, attendance, trainer assignments/sessions, workout/diet
  assignments + logs, notification logs, access logs/decision logs, feedback, reviews): even a
  manual `.delete()` now **fails loudly** instead of destroying history. Kept CASCADE: the
  customer's own profile tables (health profile, goals, measurements, progress photos), device
  tokens and biometric credentials (personal/ephemeral, purged explicitly by the GDPR path).
- Soft-deleted customers are excluded from the member list, search, the onboarding-wizard phone
  lookup and every picker/detail endpoint (404) — they can't be re-assigned or re-selected.
- Surface serializers expose `customer_is_deleted` (attendance: `person_is_deleted`) next to the
  existing live `customer.name` read; the stored name IS the label, so every consumer — mapped or
  not — renders "Deleted user", and the flag lets the UI badge it.

## The delete, concretely

`CustomerViewSet.perform_destroy` (`backend/apps/customers/views.py`) in one transaction:

1. `deleted_at = now()`, scrub all PII (label into `name`), `status=inactive`, `is_active=False`.
2. `user = None`, save.
3. If the linked user's role is `customer`, delete it (staff-linked profiles keep their user —
   #72's rule, regression-tested).

Re-add after delete (#72 invariants, re-validated under soft delete): the portal user is gone, the
old row's phone/email are blank, so provisioning creates a fresh identity and a **new** Customer
row; the old row stays soft-deleted and its history still renders "Deleted user".

## Sweep checklist — surface by surface

| # | Surface | Backend carrier | Verified by | Frontend |
|---|---------|-----------------|-------------|----------|
| 1 | Member/customer list | list excludes `deleted_at` non-null | `test_deleted_customer_hidden_from_list_search_and_detail` | no ghost rows; `getCustomerDisplayName` forces "Deleted user" for stale cached objects (`__tests__/customers.test.ts`) |
| 2 | Customer search (wizards' pickers, front-desk lookup) | same exclusion via `?search=` | same test (scrubbed phone can't match) | membership-assign / book-session / assignment pickers all read this endpoint |
| 3 | Customer detail + health/measurements/goals/photos/progress/pt actions | detail querysets exclude deleted (5 actions patched to match `get_queryset`) | same test (detail + health-profile 404) | n/a |
| 4 | Payments list + pending-payments queue | `PaymentSerializer.customer_name` (live FK read of scrubbed row) + `customer_is_deleted` | `test_payments_survive_and_render_deleted_user`, `test_readd_creates_fresh_row_and_old_reference_stays_deleted` | `PaymentTable` / `PendingPaymentTable` render label + `DeletedUserBadge` (`__tests__/deletedUserMarker.test.tsx`) |
| 5 | Invoices list/detail | `InvoiceSerializer` gained `customer_name` (was raw id — pre-existing blank on the page) + flag | `test_invoices_survive_and_render_deleted_user` | badge on both invoice pages |
| 6 | Dashboard pending payments | dashboard service/serializer gained the flag; name reads the scrubbed row | backend suite (dashboard tests green) | dashboard `PendingPayments` badge |
| 7 | Attendance punches / views | `AttendanceRecordSerializer.person_name` + `person_is_deleted` | `test_attendance_punches_survive_and_render_deleted_user` | `AttendanceTable` label + badge |
| 8 | Trainer assignments (branch-scoped + users-app direct) | `TrainerAssignmentSerializer` + flag (users-app serializer flagged too) | `test_trainer_assignment_and_session_survive_and_render_deleted_user` | trainer detail assignment table badge |
| 9 | PT sessions (trainer schedule) | `TrainerSessionSerializer.customer_name` + flag | same test | pt-sessions page badge |
| 10 | Workout / diet plan assignments | flags on both serializers | `test_workout_and_diet_assignments_survive_and_render_deleted_user` | both `AssignmentTable`s badge |
| 11 | Memberships list | `MembershipSerializer` + flag | `test_memberships_survive_and_render_deleted_user` | `MembershipTable` badge |
| 12 | Wizards — membership assign, onboarding | customers come from the excluded list endpoint; onboarding creates through `CustomerSerializer` (#72 adoption intact); in-flight session for a mid-flow-deleted member renders the scrubbed name | backend suite (onboarding tests green) | no deleted customer selectable |
| 13 | Chat (AI coach) | conversations link `users.User`, not Customer — no customer references exist in chat payloads | code inspection (explorer sweep) | n/a |
| 14 | Notification logs (WhatsApp refs) | `NotificationLogSerializer` + flag | `test_notification_logs_survive_and_render_deleted_user` | `NotificationLogsTable` badge |
| 15 | Access control (door logs / overrides) | `AccessLogSerializer`/`AccessOverrideSerializer` gained `customer_name` + flag (was raw `Customer #id` fallback) | backend suite (access tests green) | both components prefer the server name; badge for deleted |
| 16 | In-app GDPR self-deletion | `delete_customer_account` sets `deleted_at` + the same label; token revocation unchanged | `test_gdpr_self_deletion_sets_marker_and_surfaces_render_label`, adapted `apps/users/test_delete_account.py` | renders identically to ERP-deleted members |
| 17 | History-survival invariant (hard delete) | 16 cross-app FKs → `PROTECT` | `test_hard_delete_of_customer_with_history_is_protected` (`ProtectedError`) | n/a |

Known pre-existing gaps NOT introduced by #81 (left as-is, no workflow changes): the Razorpay
payments sub-page renders `Customer #{id}` for **every** row (that serializer never carried a name,
live or deleted); the frontend `Invoice` TS shape is stale vs the backend contract (field names
differ) — the new `customer_name`/flag fields land in the payload regardless.

## #72 reconcile (critical context from the brief)

`PostDeleteReAddCustomerTests` (9 tests) **all still pass**; two assertions were adapted to the new
semantics (the Customer row now survives soft-deleted instead of being gone — assertions flipped
from `assertFalse(exists)` to marker + scrub checks). The five re-add tests pass unmodified because
the scrub frees the phone/email exactly as the old hard delete did. `CustomerSerializer.create`'s
orphan adoption is untouched and still covered (`test_readd_adopts_orphaned_*`). New coverage:
`SoftDeleteDeletedUserTests` (14 tests, written alongside the implementation) — marker + scrub,
list/search/detail exclusion, double-delete idempotence, every surface above, PROTECT, re-add with
history, GDPR convergence.

## Verification (exact commands)

- Backend: `python3 -m pytest` → **1542 passed** (1529 pre-existing + new; 0 failed/skipped by this
  change), `--cov-fail-under=80` → **85.12%**.
- `flake8 . --count --show-source --statistics` (CI invocation) → **0 issues**.
- `ruff check .` → 9 findings, **all pre-existing** on the unmodified baseline (firebase/otp test
  files landed by other work); `ruff check` on every file this ticket touches → clean.
- Frontend: `npx tsc --noEmit` clean; `npm run lint` exit 0; `npm run test -- --coverage
  --coverageThreshold='{"global":{"lines":80}}'` → **53 suites / 679 tests passed**, coverage gate
  met.
- Migrations: 13 generated (`deleted_at` + nullable `user` on customers; FK on_delete swaps across
  payments, attendance, users, trainers, workouts, diet, memberships, notifications, access,
  feedback, reviews); `makemigrations --check` clean. The seed command's `_reset` now deletes seeded
  attendance explicitly (PROTECT would otherwise block reseeding).

## Files touched

Backend: `apps/customers/{models,serializers,views,tests}.py` + migration; FK/PROTECT + migrations
in 11 apps; `DeletedCustomerFlagMixin` (`apps/customers/serializers.py`) applied in payments,
attendance, trainers, users, memberships, notifications, workouts, diet, access; GDPR path
(`apps/users/services.py`) + its tests; dashboard pending-payments flag; seed `_reset`.

Frontend: `DeletedUserBadge` (new, `components/ui`), `getCustomerDisplayName` guard, type fields
(`customer_is_deleted` / `person_is_deleted` / `is_deleted`) across 9 type files, badges on
payments (list + pending + dashboard queue + invoices), attendance, memberships, trainer detail +
pt-sessions, workout/diet assignments, notification logs, access log/override viewer.
