# Sprint 6 — Analytics & Gym Operations

## Context

Sprints 1–5 built the **core ERP loop**: vendor onboarding → branches → customers → memberships → attendance → workouts/diet → payments (Razorpay) → notifications (Wati) → AI features (coach, nutrition, body analysis).

**What's missing for a functional gym ERP:**
- No analytics/reporting for gym owners
- No inventory/equipment tracking
- Mobile app lacks profile, progress tracking, and AI feature wiring
- No review/rating system for gyms
- Razorpay checkout UI still needs frontend work

## Sprint 6 Theme: **"Owner's Desk"**
Give gym owners visibility into their business and fill critical operational gaps.

---

## Stories

---

### FBOS-030 — Analytics Dashboard (13 pts)
**Priority:** P0 — the most visible gap in the ERP

**Backend** (`apps/analytics/`)
- `RevenueReport` — daily/weekly/monthly revenue per branch, grouped by payment type (membership, pack, etc.)
- `AttendanceHeatmap` — check-in counts per branch per day/week/month
- `MembershipFunnel` — new signups, renewals, cancellations per period
- `TopCustomers` — by visit frequency, revenue, goal progress
- Endpoints:
  - `GET /api/v1/analytics/revenue/`
  - `GET /api/v1/analytics/attendance/heatmap/`
  - `GET /api/v1/analytics/memberships/funnel/`
  - `GET /api/v1/analytics/top-customers/`
- All queries tenant-scoped via `TenantModelMixin`

**Frontend** (`app/analytics/`)
- Dashboard page with revenue chart (line/bar), attendance heatmap grid, membership funnel, top customers table
- Filters: date range (today/week/month/custom), branch selector
- Export to CSV button
- Role-gated: gym_owner, manager only

**Tests:** 80%+ coverage on models/serializers/viewsets

---

### FBOS-031 — Razorpay Checkout UI (8 pts)
**Priority:** P0 — revenue flow incomplete without this

**Frontend** (`app/payments/`)
- Checkout flow: plan selection → Razorpay payment modal → success/failure handling
- Payment history page: table with status badges, date, amount, plan
- Admin config page: set Razorpay key ID (masked input), toggle test/live mode
- Integrate `rzp-certified` CDN script + `@/lib/razorpay` utility

**Backend:** already complete (FBOS-020)

**Tests:** Jest tests for checkout flow, success/failure states, payment history

---

### FBOS-032 — Mobile: Profile & Progress Screens (13 pts)
**Priority:** P1 — mobile app is incomplete without these

**Mobile** (`lib/features/profile/`, `lib/features/progress/`)
- `ProfileScreen` — name, phone, email (verified badge), membership status card, edit profile
- `ProgressScreen` — weight/measurements chart (fl_chart), goal progress cards, body photos grid
- `AttendanceHistoryScreen` — calendar view with attended days marked
- Wire existing AI features into bottom nav (AI Coach, Nutrition, Body Analysis tabs already on dashboard)

**Backend:** existing endpoints already serve this data (customers, attendance, measurements)

**Tests:** Widget tests for all 3 screens

---

### FBOS-033 — Equipment & Inventory Management (8 pts)
**Priority:** P1 — operational gap

**Backend** (`apps/inventory/`)
- `Equipment` — name, branch FK, category (weights/cardio/accessories), quantity, condition (good/fair/needs_repair), last_maintained, next_maintenance
- `InventoryItem` — name, branch FK, category, quantity_in_stock, min_threshold, unit
- `MaintenanceLog` — equipment FK, date, notes, performed_by FK → User
- Endpoints: CRUD for all three + `GET /api/v1/inventory/low-stock/` (items below threshold)
- Signal: notify (log) when inventory item drops below min_threshold

**Frontend** (`app/inventory/`, `app/equipment/`)
- Equipment list with condition badges + filter by branch
- Inventory list with stock level bars (red when below threshold)
- Maintenance log table per equipment
- Add/edit forms

**Tests:** 80%+ coverage

---

### FBOS-034 — Customer Reviews & Ratings (5 pts)
**Priority:** P2 — nice to have, quick win

**Backend** (`apps/reviews/`)
- `Review` — customer FK, branch FK, rating (1–5), text, created_at — unique per customer per branch
- `ReviewResponse` — review FK, trainer/admin FK, text, created_at
- Endpoints:
  - `POST /api/v1/reviews/` (authenticated customer, can only review branches they have attended)
  - `GET /api/v1/reviews/?branch_id=` — list with rating aggregates
  - `POST /api/v1/reviews/{id}/respond/` (trainer/manager only)

**Frontend** (`app/reviews/`)
- Star rating input (1–5) + text area on customer dashboard
- Branch reviews page with average rating + breakdown bar chart

**Tests:** 80%+ coverage

---

## Story Summary

| ID | Title | Points | Priority | Backend | Frontend | Mobile |
|---|---|---|---|---|---|---|
| FBOS-030 | Analytics Dashboard | 13 | P0 | ✅ new app | ✅ new page | — |
| FBOS-031 | Razorpay Checkout UI | 8 | P0 | done | ✅ new flow | — |
| FBOS-032 | Mobile Profile & Progress | 13 | P1 | done | — | ✅ new screens |
| FBOS-033 | Equipment & Inventory | 8 | P1 | ✅ new app | ✅ new page | — |
| FBOS-034 | Reviews & Ratings | 5 | P2 | ✅ new app | ✅ new page | — |
| **Total** | | **47** | | | | |

---

## Definition of Done (All Stories)

- [ ] Backend: models, serializers, viewsets, URLs, permissions, tests ≥80% coverage
- [ ] Frontend: page/component, role guards, loading/error/empty states, tests
- [ ] Mobile: all 3 screens, riverpod providers, tests
- [ ] Multi-tenant isolation verified (tenant_id on all new models)
- [ ] Lint clean (flake8, eslint, dart analyze)
- [ ] All tests green in CI

---

## Dependencies

- FBOS-031 (Razorpay UI) needs FBOS-020 backend — **already done**, unblocked
- FBOS-032 (Mobile profile) needs existing customer endpoints — **unblocked**
- FBOS-030 (Analytics) builds on membership, attendance, payments — **all done**, unblocked

## Out of Scope (Future Sprints)

- Google Calendar / staff scheduling
- Supplier management (ordering stock)
- Marketing campaigns / referrals
- Wearable device sync
- Multi-language / i18n
- White-label / custom domain
- App store publication

---

## CI Impact

- New Django app (`analytics`, `inventory`, `reviews`) → add to `INSTALLED_APPS` + `MIGRATION_MODULES` in test settings
- New Flutter feature → `flutter test` coverage gate
- New Next.js page → Jest coverage gate
