# ADR-002 — Customer Identity: Phone-Keyed Portal Accounts

**Status:** Accepted (Arch ruling, 2026-09-05) — pre-implementation, reversible; one product flag for Siju below
**Date:** 2026-09-05
**Deciders:** Arch (author), Forge (implementation evidence), Lead (relay)
**Scope note:** Deliberately separate from ADR-001 (seeding) — do not fold identity rules into it.

## Context

- Customer app auth is OTP, phone-keyed: `get_or_create_customer_by_phone` provisions Users with synthetic `{phone}@fitnation.local` emails.
- Owner-created customers (blessed contract, 2026-09-05) provision a separate User with a real email, unusable password, OTP login.
- Same human can therefore hold two identities in one tenant → duplicate Customer records fragmenting attendance, memberships, payments, and plans in the system of record.

## Decision

1. **Phone is the canonical identity key for customer portal accounts; email is an attribute, never a second identity key.** OTP-by-phone is the auth root.
2. **Converge at write time, in both directions (primary mechanism), tenant-scoped:**
   - Owner-create with phone P in tenant T:
     - No User with P in T → provision new User (blessed flow unchanged).
     - User with P exists, email is synthetic or empty → LINK: reuse that user; replace synthetic email with the real one.
     - User with P exists, different real email → 400 `phone_already_registered`; manual resolution. Never silently mutate a real identity.
   - OTP login with phone P: reuse an existing User with P in T (owner-created) before provisioning a synthetic one.
3. **Multi-tenant scoping:** all phone/email matching happens within the requesting tenant. Same human at two gyms = two accounts (correct).
4. **Email-only owner-created customers (no phone):** allowed for CRM/demo use but NON-LOGINABLE until a phone is set. Customer UPDATE must accept `phone`; setting it provisions OTP capability on that same user (never a second user).
   **[PRODUCT FLAG — Siju]** Confirm this UX is acceptable, or require phone at creation.
5. **No post-hoc auto-merge in v1.** Remaining duplicates (customer self-registered with a number the owner doesn't have) resolve manually via admin initially; a merge endpoint (reparent memberships/payments/attendance FKs) is a future ticket if incidence justifies it.

## Alternatives rejected

- **Permanently separate accounts:** simplest, but guarantees duplicate-person records in the most common production flow (owner uploads roster + customers self-register via app).
- **Post-hoc merge as primary mechanism:** expensive FK migration across many tables, error-prone, leaves duplicates visible between merges.
- **Email as identity key:** breaks the OTP-by-phone auth root; email changes would fragment history.

## Consequences / tickets

- Ticket: customer-create serializer — phone-collision link/400 rules above. Tests: link-on-synthetic, 400-on-real-email-conflict, tenant-scoped match.
- Ticket: OTP `get_or_create_customer_by_phone` convergence. Test: owner-created user reused, no synthetic account minted.
- Ticket: customer-update accepts phone; provisioning on set. Tests: same user gains OTP, no second user; email-only customer OTP request returns a clean error (not a crash).
- Ticket (future, conditional): admin merge tool.
- Demo impact: none — demo customers are owner-created with emails.

## Open items

- Siju: email-only non-loginable UX confirmation (or phone required at creation).
- Forge: confirm email-only OTP request behavior is a clean 4xx and add the test.