# ADR-003 — App Access Entitlement: Membership-Plan-Gated Mobile App

**Status:** Accepted (Arch ruling, 2026-10-21) — pre-implementation, reversible
**Date:** 2026-10-21
**Deciders:** Arch (author); product constraints locked by the product owner (plan toggle default-True, 7-day grace, WhatsApp-first invite)
**Supersedes/augments:** ADR-002 (customer identity) where identity meets entitlement — §4 here. ADR-002's identity rules (phone is the key, tenant-scoped convergence, no post-hoc merge) are **unchanged**.
**Implementation spec:** `docs/fbos-011-app-access-and-invite.md` (field names, payloads, task list live there)
**Naming note:** backend comments written 2026-09 cite "ADR-003 P0-1/P0-2" (`apps/users/otp.py:1`, `apps/users/services.py:217-219`, `apps/users/serializers.py:134-146`) — those referred to the OTP-anchor/real-OTP decisions, which were never filed as an ADR. This document takes the ADR-003 number; those comments are re-pointed to the FBOS-011 spec in task B2.

## Context

- The customer Android app (`com.fitnation.app`) is going to Google Play. Access must be gated by gym membership: a paid member gets the app; an expired member gets a 7-day read-only grace; after that the app gates them out.
- Today there is **no gate at all**: OTP verify auto-provisions a customer user + `Customer` for any verified phone with a resolved tenant (`apps/users/services.py:253-299`), and authorization is role-only — every customer gets the same static permission set (`apps/permissions/permissions.py:105-127`). A walk-in who never bought anything and a yearly member are indistinguishable to the API.
- Authorization must stay multi-tenant (FBOS-010) and role-based (FBOS-009); the backend is opaque-token (no JWT claims to embed facts in; `apps/users/models.py:286-338`) and has **no Celery**, so anything requiring background jobs is a non-starter.
- Product-owner constraints (locked, not relitigated here): access is a **toggle on the membership plan** defaulting **True** for all existing plans at launch; **7-day read-only grace** after expiry; front-desk onboarding ends with a WhatsApp invite in ~90 s.

## Decision

1. **App access is an entitlement, not a role permission.** RBAC (FBOS-009 matrix) keeps answering *what may this role do*; entitlement answers *may this human use the app right now, per their commercial membership*. The two stay separate so gym staff are never entangled with member billing state.
2. **The carrier is `MembershipPlan.includes_app_access` (BooleanField, default True).** No per-membership override in v1 — the plan is the commercial contract; a nullable `Membership.app_access_override` is the pre-agreed escape hatch if tenants sell app-only tiers. The default-True migration backfills every existing plan in the same DDL: no member loses access at rollout. Semantics are **live**: entitlement is derived per request from the member's current membership → its plan, so toggling a plan revokes/restores access on the member's next request (which is exactly why day-1 default True matters).
3. **Grace is computed, never stored:** `end_date < today ≤ end_date + APP_ACCESS_GRACE_DAYS (7)` → read-only. A stored flag would need a daily job to expire and there is no Celery. `status="cancelled"` revokes immediately — cancelled members get **no** grace (cancellation is a business act, expiry is a calendar one).
4. **Entitlement surfaces as a permission code the app already consumes, plus one object.** Entitled customers get `app.access` appended to the `permissions` list in the OTP-verify and `/auth/me` responses (the mobile `AuthResponse` model already parses that list), and a structured `entitlement` object `{status, read_only, plan_name, end_date, grace_end_date, gym}` for UI copy. Gated-out members get the role list *without* `app.access`.
5. **Enforcement is server-side and per-request, in one DRF permission class** (`EntitlementRequired`) appended to the customer-facing content viewsets: active → allow; grace → safe methods only (403 `app_access_read_only` on writes); expired/none → 403 `app_access_required`. Opaque tokens carry no entitlement claims, so revocation is effective on the next request — the database, not the credential, is the source of truth. Membership cancellation additionally revokes the customer's auth tokens (logout-everywhere) when no other active membership remains.
6. **The customer role keeps its identity even when it loses the app:** token, `/auth/me`, own profile view/edit, and own membership view survive every entitlement state — a gated member must still be able to see *why* they're gated and renew. Profile and membership viewsets are therefore *not* behind `EntitlementRequired`.
7. **Rollout is per-tenant** via the existing `tenant.features["app_access"]` JSON flag (`apps/tenants/models.py:50-54`): flag off ⇒ the entitlement engine, invites, and `app.access` do not exist for that tenant (legacy behaviour, old app builds unaffected); flag on ⇒ full engine. Pilot: "Hash Fit", 6 members.

## Alternatives rejected

- **Boolean on `Customer` (or `User`) maintained by cron:** needs a scheduler that doesn't exist (no Celery); a stuck job silently over/under-grants; also conflates "who the person is" with "what they bought".
- **Stored `grace_until` column:** same scheduler problem, plus an extra migration and drift risk against `end_date` edits/renewals.
- **Entitlement codes inside `ROLE_PERMISSION_MATRIX`:** makes the role set tenant/billing-dependent, breaks the FBOS-009 mental model, and would force every staff endpoint's permission check to consider membership state.
- **JWT claims carrying entitlement:** there is no JWT — introducing one for this is a platform change; and embedding a revocable fact in a long-lived credential is precisely what we don't want.
- **Blocking auto-provisioning for membership-less phones (reject invite-first OTP):** destroys the non-enumeration property ADR-002 depends on — an attacker could probe which phones are invited before possessing them — and breaks the invite flow (front desk invites before first login). Auto-create stays; entitlement stays `none`.
- **Per-membership override in v1:** no tenant has asked; plan-level covers the pricing model today; adding the column later is additive.

## Consequences / tickets

- `MembershipPlan.includes_app_access` + selector `get_app_entitlement` + `EntitlementRequired` + effective-permissions resolution: tasks **B1/B2** in `docs/fbos-011-app-access-and-invite.md` §8, tests mandated there (all five entitlement states, cancelled-no-grace, tenant isolation, staff unaffected).
- Same-tenant UX dependencies: mobile gate (`M3`), plan-form toggle (`F1`), customer-detail entitlement card (`F3`).
- **Identity fix bundled under this ADR (augmenting ADR-002):** `User.email` is globally unique (`apps/users/models.py:86`) while synthetic emails are `{phone}@fitnation.local` — the same phone at two gyms IntegrityErrors on the second OTP verify. Synthetic emails become `{phone}.{tenant_uuid}@fitnation.local` via one shared helper used by both provisioning paths; no migration for existing rows (phone-match converges first, per ADR-002 rule 2). This *completes* ADR-002's "same human at two gyms = two accounts (correct)" rather than changing it.
- Live revoke means a mid-workout session dies at the next request — acceptable and desired; front desk is told "cancel = they're out within seconds" (runbook copy).
- Trial plans behave like any plan: active until `end_date`, then grace, then gate.

## Open items

- **Siju:** confirm deep-link domain (`app.yougetfitwithus.com` proposed), privacy-policy URL, and the data-retention split between statutory financial records and health data at deletion.
- Per-membership `app_access_override`: revisit only when a tenant prices the app separately.
- Hard-delete job for anonymized health rows: phase 2, needs the retention policy above.
