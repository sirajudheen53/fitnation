# ADR-001 — API-Driven Seeding for QA Demo Data

**Status:** Approved (with corrections to proposal) — ratified by Arch after independent code verification, 2026-09-05
**Date:** 2026-09-05
**Deciders:** Arch (ratifier, code-verified), Forge (proposer + code evidence), Lead (relay), Siju (final call on direction)
**Supersedes:** Direct-ORM seeding in `apps/core/qa_seed/*` for business data

## Context

Seeding QA demo data via direct ORM writes has already produced two silent-drift bugs:
`paid_at NULL` on completed payments and hand-built invoice numbers bypassing the
`INV-YYYYMMDD-NNNN` generator. Siju decided demo data must flow through real validation,
serializers, and relationship logic. Forge proposed a hybrid 3-layer approach with three
architect touchpoints. Code verification (2026-09-05) corrected two of the three claims.

## Decision

Adopt the 3-layer hybrid seeder, with the layer rules and conditions below.

### Layer rules

| Layer | Mechanism | Contents |
|---|---|---|
| 0 — Bootstrap | Direct ORM | Platform admin, tenants, TenantSettings, vendor registrations, base catalogs (food items, exercises, marketplace, permissions — existing seed commands), staff users; tokens via login endpoint |
| 1 — Business data | DRF `APIClient` in-process | Plans, memberships, payments, attendance, assignments, diet/workout plans, feedback, carts, invoice generation |
| 2 — Internal | Direct ORM | Anything with no API; each entry must have a ticket proposing an API |

### Touchpoint rulings (code-verified)

1. **Invoice path — rule CONFIRMED, mechanism claim CORRECTED.**
   `PaymentViewSet.create` has **no** invoice side effects (`backend/apps/payments/views.py:279-289`).
   Canonical invoice creation paths: `RazorpayVerifyView.post` (`views.py:128`), Razorpay
   webhook auto-generate (guarded per payment, `webhook_views.py:47-66,97`), and
   `POST /api/v1/invoices/generate/` (`views.py:332,379`). Rule: the seeder must never
   hand-build invoice numbers; omit the field and let `Invoice.save()` generate
   (`INV-YYYYMMDD-NNNN`, `models.py:128-152`). The API structurally enforces this —
   `invoice_number` is read-only on `InvoiceSerializer`.
   **Seeded invoices go through the `generate` action only.**

2. **Vendor onboarding — OUT of API-mode scope, reason CORRECTED.**
   It does not send SendGrid email at all: `apps/vendors/emails.py` is a log-only stub,
   and signup falsely reports "Verification email sent" (`services.py:19-39`) — drift bug,
   ticket it. Real SendGrid is user-email-verification only, gated on `SENDGRID_API_KEY`
   (`apps/core/services/email.py:33`) with console backends in local/dev/test settings.
   Vendor onboarding stays in Layer 0 because tenant/vendor registration is bootstrap data.
   Condition: QA seed environments must never have a real `SENDGRID_API_KEY`; add a seed-mode
   guard/assertion that no outbound integration (email/SMS/WhatsApp/Razorpay network) fires.

3. **Contract authority — backend serializer/OpenAPI schema, NOT frontend types.**
   The "frontend types as authority" proposal is rejected; the drift evidence supports this:
   `frontend/types/payment.ts` models fields that do not exist on the backend, and
   `lib/api.ts` uses a wrong invoice path (`/invoices/invoices/` vs `/api/v1/invoices/`).
   No OpenAPI schema is served (drf-spectacular exists only in unused `config/settings.py`).
   Backend contract is the single source of truth. Migration path: enable drf-spectacular in
   active settings + serve schema → generate frontend types via codegen (openapi-typescript/orval)
   → CI schema-diff check → replace legacy hand-written types. Until codegen lands,
   hand-written types may exist but carry no authority.

### Constraints on the seeder

- **Never** call `payments/razorpay/create-order/`, refund endpoints, or the webhook from the
  seeder — `PaymentViewSet.create` is pure DB (verified), so use it; Razorpay order/verify
  paths make network calls when tenant config is active.
- **`paid_at`:** API read-only; auto-set to now only when `status=completed`
  (`views.py:312-317`). For realistic revenue timelines, a documented Layer 2 pass may
  backdate `paid_at` (ORM) as a seed-only exception; the completed⇒`paid_at` non-null
  invariant must never be violated.
- **Idempotency:** seed must be re-runnable (upsert by natural keys or flush+reseed).
- **Retire legacy entry points:** root `backend/seed_qa.py` and the ORM-direct
  `--realistic` payment/invoice writes in `qa_seed/*` move into the new structure —
  one source of truth.
- **Tests (house rule):** the seeder ships with a fresh-DB test asserting: completed
  payments have `paid_at`, all seeded invoice numbers match `INV-YYYYMMDD-NNNN`,
  tenant isolation holds on seeded data, and a second seed run is idempotent. ≥80% coverage.

## Consequences / follow-ups

- Ticket: `POST /api/v1/invoices/` and `/generate/` lack a per-payment duplicate guard
  (verify/webhook have one) — API seeding could mint duplicate invoices.
- Ticket: count-based invoice number generator is not concurrency-safe (unique-collision
  risk); acceptable for a sequential in-process seeder, fix for production traffic.
- Ticket: vendor signup false "Verification email sent" response.
- Ticket: enable drf-spectacular in `config/settings/` package, serve schema, adopt
  frontend type codegen + CI drift check.
- Existing seed rows with non-conforming numbers (`INV-2026-0001`, `IH-INV-00001`) must be
  regenerated through the new path on next QA reseed.