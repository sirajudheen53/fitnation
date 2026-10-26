# Report — #72 (P0): Add-customer returns 400 after a customer was deleted

Reported by Siju (2026-10-25 19:48 IST). Scope: backend only (`backend/apps/customers`); mobile/ untouched.

## TL;DR

`DELETE /api/v1/customers/customers/{id}/` (DRF destroy) hard-deleted the `Customer` row but left the
linked portal `User` behind. Every later add-customer with the SAME phone then failed with 400. Fixed
by making the delete path remove the linked customer-role user, and by making add-customer adopt
orphaned identities left behind by deletes that already happened (production data).

## Root cause (reproduced, not assumed)

`Customer.user` is a OneToOne to `User` (`on_delete=CASCADE` protects the customer when a *user* is
deleted — the reverse deletes nothing). The ERP delete goes through DRF's default `destroy`, so after
deleting a customer the tenant kept an **orphaned user**: role `customer`, phone still set, and a
`User.email` that is **globally unique**.

Re-adding a customer with the same phone hits `CustomerSerializer.create`'s ADR-002 rule-1 phone match,
which failed in two different ways depending on the deleted customer's identity (both reproduced in
tests before the fix):

1. **Customer had a real email** → the orphan is non-synthetic → the guard fired:
   `400 {"phone": ["This phone is already registered to a different account. Resolve manually."]}`.
2. **Customer was phone-only** (synthetic `{phone}.{tenant_uuid}@fitnation.local` user) → the match
   linked the orphan but a latent bug re-provisioned a second user anyway (the local `user` variable
   stayed `None` after `validated_data["user"] = match`), hitting the deterministic synthetic email
   collision: `400 {"email": ["A user with this email already exists."]}`.

Control case: add-customer with a DIFFERENT phone after a delete always worked (201), which pins the
failure to delete-path state, not general validation. The mobile self-service delete
(`delete_customer_account`, `POST /users/auth/delete-account/`) never had this bug — it anonymizes the
user in place and frees the phone; only the ERP destroy path leaked state.

## Fix

Two changes, both in `backend/apps/customers/`:

1. **`views.py` — `CustomerViewSet.perform_destroy`** (root cause): the destroy now deletes the linked
   portal user in the same transaction, **only when its role is `customer`** — a profile deliberately
   linked to a staff account never destroys that account. Cascades take care of the identity plumbing
   (auth tokens, device tokens); memberships/payments already cascaded with the customer row.
   Deleting a customer therefore also ends the member's app identity — same semantic as before for
   OTP login (a deleted member could always be re-created by owner re-add or gym-anchored OTP
   auto-create).

2. **`serializers.py` — `CustomerSerializer.create`** (remediation + latent bug): a phone match against
   a user with **no customer row** (an orphan) is now linked instead of rejected/re-provisioned:

   | Phone-match state | Behaviour |
   | --- | --- |
   | Synthetic user (with or without profile) | link + adopt payload email (unchanged for profiles; orphans now actually reuse the user) |
   | Real email, has customer profile (live account) | 400 `phone_already_registered` (unchanged) |
   | Real email, no profile, role `customer` (orphan) | adopt **unless the payload email contradicts** the orphan's email (still 400 then — the real email is never silently replaced) |
   | Real email, no profile, staff role | 400 (unchanged — staff account owns the phone) |

   The contradiction rule keeps `ADR002CustomerIdentityTests::test_create_phone_conflict_returns_400`
   green — that fixture (real-email user, no profile, different payload email) is deliberately treated
   as a live account, not an orphan.

No migrations needed. No contract changes for frontend/mobile: the same endpoints, same 400 codes for
genuinely-live conflicts.

## Regression tests (TDD — written first, all failed pre-fix)

`backend/apps/customers/tests.py::PostDeleteReAddCustomerTests` (9 tests), driving the real API paths:

- delete removes the linked customer-role user and frees the phone;
- re-add same phone after delete: with email → 201; phone-only → 201 (the exact Siju repro);
- different phone after delete → 201 (control);
- delete never cascades a staff user linked to a profile;
- pre-fix orphans (synthetic / real-email) are adopted — no second user, no synthetic collision;
- orphan + contradicting email still 400s without mutation; staff phone still 400s.

## Evidence

- Pre-fix run: 5 of the new tests failed with exactly the two 400 bodies above (plus the orphan
  survival assert); different-phone control and the two guards passed as expected.
- Post-fix: full backend suite **1529 passed, 18 subtests passed** (0 failed) —
  `pytest` with `DJANGO_SETTINGS_MODULE=config.settings.test`.
- Lint: `flake8 . --count` from `backend/` (CI's exact invocation, `ci.yml` step "Lint with flake8")
  → **0 issues**; `black --check` and `isort --check-only` clean on the touched files.

## Ops notes

- Production may already hold orphaned users from pre-fix deletes. Fix 2 remediates them on re-add
  (same email or phone-only adopts; contradicting email needs a one-off data fix — none known).
- Deploying fix 1 changes ERP delete semantics slightly: the deleted member's outstanding auth tokens
  die immediately (previously they lingered on the orphaned user).
