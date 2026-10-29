# FBOS-011: Customer App Access & Invite — Design Spec

**Status:** Approved for implementation (design only — no code in this doc)
**Date:** 2026-10-21
**Author:** Arch
**Depends on:** ADR-002 (phone identity), ADR-003 (app-access entitlement — same commit), `docs/onboarding-design.md` (front-desk wizard), FBOS-009 (roles/permissions), FBOS-010 (multi-tenancy)
**Companion:** `docs/play-release-checklist.md` (release runbook)

---

## Corrections to brief

The task brief was verified against `develop` before writing. These points differ from the brief or need emphasis:

1. **`PermissionChecker` on mobile is dead code.** `mobile/lib/features/auth/services/permission_checker.dart` defines `customerPermissions`, but no file in `mobile/lib` references it, and `mobile/lib/router/app_router.dart` has a static route table with no permission-driven navigation. This workstream *introduces* permission-driven gating; there is nothing to "change".
2. **The `/onboarding` frontend route is already occupied.** `frontend/app/onboarding/page.tsx` is the *vendor signup* wizard (business type → first branch). The front-desk member wizard from `docs/onboarding-design.md` must take a different route — this spec uses **`/onboarding/member`**.
3. **Backend comments cite "ADR-003 P0-1/P0-2"** (`apps/users/otp.py:1`, `apps/users/services.py:217-219`, `apps/users/serializers.py:134,141`) but no such ADR doc exists — those comments refer to the OTP-anchor/real-OTP decisions. The number is now taken by the entitlement ADR; a task below re-points those comments to this spec/ADR set.
4. **There is no Celery in the backend.** `apps/memberships/views.py:82-88` states it explicitly ("this project has no Celery"), and `INSTALLED_APPS` (`config/settings/base.py:34-76`) has no Celery app. All post-commit side effects in this spec are synchronous with injectable transports, mirroring `wati_service.send_notification` and `sync_customer_devices`. (AGENTS.md prescribes Celery; adopting it is a separate platform decision.)
5. **Latent multi-tenant bug in auto-provisioning.** `User.email` is *globally* unique (`apps/users/models.py:86`), but `get_or_create_customer_by_phone` (`apps/users/services.py:280-290`) mints the synthetic email `{phone}@fitnation.local` without the tenant. The same phone at two gyms → `IntegrityError` → 500 on the second gym's OTP verify. ADR-002 rules "two accounts (correct)"; the schema breaks it. Fixed in §3.
6. **The mobile OTP *verify* call omits the gym anchor.** `requestOtp` sends `gym` (`mobile/lib/features/auth/data/data_sources/auth_remote_data_source.dart`), `verifyOtp` does not. A member of two gyms on an anchored build can be auto-pinned to the wrong gym at verify time. Fixed in §7.
7. **`--dart-define=SERVER=…` does not actually switch the API host today.** The Dio client uses `AppConstants.apiBaseUrl` (`mobile/lib/core/constants/app_constants.dart:11-15`), an independent `String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000')`. The `ServerConfig` presets in `app_config.dart` are never consulted by the client. Fixed in §7 (matters for every pilot build).
8. **Production OTP today silently degrades to a log file.** `config/settings/prod.py` defines no `OTP_SENDER`, and `get_otp_sender()` (`apps/users/otp.py:76-84`) defaults to `console` — codes go to server logs only. §4 makes that configuration *impossible to ship silently*.
9. **`Membership` has three statuses** — `active | expired | cancelled` (`apps/memberships/models.py:55-60`). The 7-day grace applies to `expired` only; `cancelled` revokes app access immediately (§1).
10. **WATI endpoint config stores a full session-message URL**, not a base URL (`DEFAULT_WATI_ENDPOINT = "https://api.wati.io/api/v1/sendSessionMessage"`, `apps/notifications/services/wati_service.py:43`). Business-initiated WhatsApp (OTP, invite) requires *template* messages on a different path. §4/§5 define an endpoint-normalization rule so no tenant-facing config migration is needed.
11. **The customer role's permission set is much larger than FBOS-009 documents** — it includes marketplace, reviews, AI-nutrition and health-profile codes (`apps/permissions/permissions.py:105-127`). §2 keeps that set as the RBAC base and layers entitlement on top.
12. **The brief's "server presets" and Play tooling are real:** `~/.play-cred/fb-sa.json` exists with helper scripts (one currently drives a *different* package, `com.lifestyle.tailoring` — same developer account). The runbook reuses the pattern for `com.getfitwithus.app`.

---

## 0. Summary of decisions (locked)

| # | Decision | Value |
|---|---|---|
| D1 | Entitlement carrier | `MembershipPlan.includes_app_access: bool`, default **True**; no per-membership override in v1 |
| D2 | Grace | **7 days** read-only after `end_date`, computed (never stored); `cancelled` = immediate revoke, no grace |
| D3 | Entitlement permission code | `app.access` injected into the `permissions` list for entitled customers; server enforcement via a new `EntitlementRequired` DRF permission class (RBAC matrix untouched) |
| D4 | Auto-provisioning | Unchanged (phone + resolved tenant auto-creates, non-enumerating); response gains an `entitlement` object; synthetic email becomes tenant-scoped (bug fix #5) |
| D5 | OTP delivery chain | WATI WhatsApp template (tenant config) → MSG91 SMS (platform config) → **503 loud failure**; `console` dev-only; `stub` hard-blocked unless `DEBUG` |
| D6 | Invite | New `app_invite` notification type, sent by the onboarding flow, resend endpoint with a 24 h dedupe window; WhatsApp template + DLT SMS fallback |
| D7 | Join link | `https://app.yougetfitwithus.com/g/{tenant_uuid}` (App Link + custom scheme `fitnation://g/…`), Play referrer `gym%3D{tenant_uuid}`, plus a human **gym code** fallback (`Tenant.gym_code`) |
| D8 | Mobile gate | GoRouter redirect to `/gate` driven by an `entitlement` object on the auth state; per-request server enforcement is the source of truth (opaque tokens carry no claims) |
| D9 | Package rename | Full rename to `com.getfitwithus.app` (applicationId + namespace + Kotlin sources) — app is unpublished, so no migration constraints |
| D10 | Rollout | Per-tenant feature flag `tenant.features["app_access"]`; pilot = "Hash Fit", 6 members |

---

## 1. Entitlement model (see also `docs/adr-003-app-access-entitlement.md`)

### 1.1 Field

```python
# apps/memberships/models.py — MembershipPlan
includes_app_access = models.BooleanField(
    default=True,
    help_text="Memberships sold on this plan include access to the customer mobile app.",
)
```

- **Default `True`**: the migration (`AddField`, `default=True`) backfills every existing plan to `True` in the same statement — no member loses access on day 1. No separate data migration is needed; new plans created through `MembershipPlanViewSet.create` inherit the model default.
- **No per-membership override in v1.** The plan is the commercial contract and plan CRUD is already tenant-managed; a nullable `Membership.app_access_override` is the documented escape hatch if a tenant later sells "app-only" or "gym-only" tiers. Do not build it now.
- **Semantics are live**: entitlement is *derived* from the member's current membership → its plan. Toggling `includes_app_access` off a plan revokes app access for members on that plan at their next request (this is exactly why the launch default is `True`). Serializer: add to `MembershipPlanSerializer.Meta.fields` (`apps/memberships/serializers.py`); frontend type adds the field (`frontend/types/membership.ts:15-25`) with a toggle in `MembershipPlanForm`.

### 1.2 Grace: computed, not stored

The backend has no Celery (correction #4), so a stored `grace_until` column would need a daily job to expire. Grace is a pure function of `end_date` — the same pattern as `Membership.compute_status()` (`apps/memberships/models.py:96-109`):

```
today ≤ end_date                                → active   (full access)
end_date < today ≤ end_date + APP_ACCESS_GRACE_DAYS → grace (read-only)
end_date + APP_ACCESS_GRACE_DAYS < today        → expired  (gated out)
status == cancelled at any point                → none     (immediate revoke)
```

- `APP_ACCESS_GRACE_DAYS = 7` — a platform-level Django setting (`config/settings/base.py`), not per-tenant in v1.
- Grace counts calendar days from `end_date`. `compute_status()` treats the membership as active **on** `end_date` (`timezone.localdate() > self.end_date` → expired), so grace day 1 is the day after the last valid day.
- Selection rule when a customer has several memberships: take the **single non-cancelled membership with the max `end_date`** (renewals extend `end_date` on the same row — `apps/memberships/views.py:135-169` — so in practice there is one live row per customer; the max-rule makes history rows harmless).

### 1.3 The selector (single source of truth)

```python
# apps/memberships/selectors.py (new)

@dataclass(frozen=True)
class AppEntitlement:
    status: str            # "active" | "grace" | "expired" | "none"
    read_only: bool        # True only when status == "grace"
    membership_id: int | None
    plan_name: str | None
    plan_includes_app_access: bool
    end_date: date | None
    grace_end_date: date | None

def get_app_entitlement(customer: Customer, *, tenant: Tenant, on: date | None = None) -> AppEntitlement
```

Rules, in order:
1. `tenant.features.get("app_access")` falsy → `status="none"` (per-tenant rollout flag, D10; the field already exists — `apps/tenants/models.py:50-54`).
2. Latest non-cancelled membership; none → `status="none"`.
3. `not membership.plan.includes_app_access` → `status="none"` (plan says no app).
4. Date rules from §1.2 produce `active` / `grace` / `expired`.

Cost: one indexed query (`idx_membership_tenant_customer`, `apps/memberships/models.py:88-90`) + `select_related("plan")`. No cache in v1; add one only if profiling demands it.

### 1.4 Entitlement vs RBAC — where the check lives

- **RBAC (unchanged)** answers *what may this role do*: the static `ROLE_PERMISSION_MATRIX` (`apps/permissions/permissions.py:32-128`) keeps the customer role's set exactly as-is. No entitlement codes enter the matrix; staff flows are untouched.
- **Entitlement** answers *may this human use the app at all right now*. It is layered on top:
  - **Payload**: `app.access` is appended to the `permissions` list and an `entitlement` object is added to auth responses (§2).
  - **Enforcement**: a new DRF permission class `EntitlementRequired` (§2.4) is attached to the customer-facing content viewsets. It recomputes entitlement per request — the authority for *every* decision is the database, never the client.
- **Why not store it on the token:** `AuthToken` is an opaque 64-char row (`apps/users/models.py:286-338`); there are no JWT claims to embed anything in, and embedding would freeze a revocable fact into a long-lived credential. Opaque token + per-request recompute means revocation is effective on the member's *next request* (§9.4).

---

## 2. Membership-aware permission resolution

### 2.1 Permission code

`app.access` — a synthetic entitlement code. It never enters `ROLE_PERMISSION_MATRIX` or the `permissions` table (FBOS-009 §3); it exists only in two places: the resolved permission list, and `EntitlementRequired`'s logic.

### 2.2 Resolution function

```python
# apps/users/services.py

BASE_CUSTOMER_PERMISSIONS  # = existing ROLE_PERMISSION_MATRIX["customer"]

def get_effective_permissions(user: User, tenant: Tenant | None) -> list[str]:
    """Role permissions + entitlement-derived codes (customers only)."""
```

Behaviour:
- Non-customer roles → exactly `get_user_permissions(user)` (unchanged; wildcard roles still `["*"]` — `apps/users/services.py:172-186`).
- Customer role → role set + `"app.access"` **iff** `get_app_entitlement(customer, tenant=tenant).status in {"active", "grace"}`. Expired/none → role set alone (the role set keeps read codes like `workouts.view_workout`; `EntitlementRequired` still blocks them server-side — the list drives *UI*, the permission class drives *authorization*).

### 2.3 Call sites and payload shapes

`get_effective_permissions` replaces `get_user_permissions` in exactly three places:

**a) `OTPVerifyView.post`** (`apps/users/views.py:209-222`) — response gains `entitlement`:

```json
{
  "token": "…",
  "user": { "…": "…" },
  "permissions": ["memberships.view_membership", "workouts.view_workout", "app.access", "…"],
  "entitlement": {
    "status": "active",
    "read_only": false,
    "plan_name": "Monthly Unlimited",
    "end_date": "2026-11-18",
    "grace_end_date": null,
    "gym": { "uuid": "3f7c…", "name": "Hash Fit" }
  }
}
```

**b) `MeView.get`** (`apps/users/views.py:125-138`) — same two additions (`permissions` becomes effective; `entitlement` object included).

**c) `LoginView`** — unchanged (staff path; keep `get_user_permissions`).

**New endpoint — `GET /api/v1/users/auth/entitlement/`** (`apps/users/urls.py`, next to the existing auth paths at `apps/users/urls.py:15-19`; `IsAuthenticated` + `IsTenantMember`, no role permission):

```json
{
  "status": "grace",
  "read_only": true,
  "plan_name": "Monthly Unlimited",
  "end_date": "2026-10-14",
  "grace_end_date": "2026-10-21",
  "gym": { "uuid": "3f7c…", "name": "Hash Fit" }
}
```

The mobile app calls this on app resume (throttled, §7.3); `/auth/me/` remains the login-time source.

### 2.4 Server enforcement — `EntitlementRequired`

```python
# apps/permissions/entitlements.py (new)

class EntitlementRequired(BasePermission):
    """Customer-content gate layered on top of RolePermission.

    active  → allow all methods
    grace   → allow safe methods; unsafe → 403 {"detail": …, "code": "app_access_read_only"}
    expired/none → 403 {"detail": …, "code": "app_access_required"}
    """
```

- Ordering: `permission_classes = [IsAuthenticated, IsTenantMember, RolePermission, EntitlementRequired]` — entitlement runs *after* role/tenant checks; for staff roles (`"*"`) it short-circuits to allow (staff use the ERP, not the customer app).
- Attach to the mobile-facing content viewsets: **workouts, diet, attendance, body_analysis, ai_coach, ai_nutrition, feedback, marketplace (cart/order/review writes), progress photos**. Read viewsets and write viewsets alike — the method check does the grace split.
- **Not** attached to: `customers` (profile: viewable/editable in every entitlement state, self-scoped already — `apps/customers/views.py:41-44`), `memberships` (a gated-out member must still see "Expired — renew at the front desk"), auth endpoints.
- The 403 body always carries `code` so the mobile Dio interceptor can flip the local entitlement state to `expired`/`grace` and route to `/gate` without a round-trip.

### 2.5 What the customer role keeps vs loses

| State | Keeps (RBAC + no entitlement gate) | Loses (`EntitlementRequired` blocks) |
|---|---|---|
| `active` | everything | nothing |
| `grace` (read-only) | token, `/auth/me`, profile view **and edit**, own membership view, entitlement endpoint | all writes in gated apps (workout log, meal log, QR check-in, feedback POST, cart/order, AI coach chat, photo upload) → 403 `app_access_read_only` |
| `expired` / `none` | token, `/auth/me`, profile view/edit, own membership view, entitlement endpoint | all gated reads *and* writes → 403 `app_access_required` |

Rationale: QR check-in is a write — a grace-period member cannot badge into the gym through the app (door biometrics are a separate system, `apps/access/`). A member who never had the app (`none`, e.g. auto-provisioned walk-in before onboarding finishes) sees the same gate as an expired one, just with different copy (§3.4) — the response shape does not distinguish "no membership" from "no entitlement", preserving non-enumeration.

---

## 3. Auto-provisioning hole — closed behaviour

Today `get_or_create_customer_by_phone` (`apps/users/services.py:253-299`) auto-creates a customer User + `Customer` for any verified phone with a resolved tenant — no membership, no invite check. The behaviour below keeps the non-enumeration property (the codebase never reveals registration state — `apps/users/services.py:249-250`) while making entitlement explicit.

### 3.1 (a) Phone unknown + gym anchor known

OTP request/verify both resolve the anchor to a tenant (`resolve_tenant_for_otp`, `apps/users/services.py:232-237`) and proceed. **Auto-create stays.** Killing it would let an attacker distinguish "invited phone" (OTP arrives) from "unknown phone" (rejected) *before* possessing the phone — worse than the status quo. The invite flow also depends on it: the front desk sends the invite before the member's first login, so the phone is legitimately unknown at first OTP.

Change: after verify, the created user gets **no permissions beyond the role set minus `app.access`** (entitlement `none`), and the response tells the app to gate:

```json
{ "token": "…", "user": {"role": "customer", "…": "…"},
  "permissions": ["memberships.view_membership", "payments.view_payment", "…"],   // no app.access
  "entitlement": {"status": "none", "read_only": false, "plan_name": null,
                   "end_date": null, "grace_end_date": null,
                   "gym": {"uuid": "3f7c…", "name": "Hash Fit"}} }
```

**Bulk-abuse guardrail:** per-tenant daily cap on *OTP-created* users (cache counter, `app-autocreate:{tenant}:{date}`, default 50/day → 429). Auto-create is for walk-ins, not for farming rows.

### 3.2 (b) Phone unknown + no anchor

Unchanged: `resolve_tenant_for_otp` raises the generic, non-enumerating 400 `{"detail": "Specify your gym to continue."}` (`apps/users/services.py:249-250`). The app responds by offering the gym-code entry (§5.4) or the invite link. With the gym code the client re-requests with `gym: <uuid>` — converging to case (a). (#87: the anchor also accepts the gym code itself, canonicalized like the lookup endpoint, so the app's free-text panel can re-exchange directly without a lookup round-trip.)

### 3.3 (c) Phone known, no active membership

Identical response shape to (a): token issued, no `app.access`, `entitlement.status = "none"` (or `"grace"` if within the window). The member can log in, see their profile and "Membership expired — renew at the front desk" (they can read their own membership rows), and nothing else.

### 3.4 What the member sees in the app when not entitled

The **gate screen** (`/gate`, §7.2), three variants driven by `entitlement`:

- `none` (never a member / plan without app access): *"Welcome to {gym_name}! Your membership doesn't include the FitNation app yet. Ask the front desk to set you up — it takes a minute."* + gym phone CTA.
- `grace`: no full-screen gate; persistent amber banner on every screen: *"Your membership expired on {end_date}. Access is read-only until {grace_end_date}."* Writes disabled with a snackbar pointing at the banner.
- `expired`: *"Your membership expired on {end_date}. Renew at {gym_name} to get back in."* + gym phone CTA + "Refresh" (re-pulls `/auth/entitlement/` after renewing at the desk).

### 3.5 Bug fix bundled here: tenant-scoped synthetic email

`User.email` is globally unique (correction #5). New synthetic identities are minted as **`{phone}.{tenant_uuid}@fitnation.local`** via one shared helper:

```python
# apps/users/services.py
def synthetic_otp_email(phone: str, tenant: Tenant) -> str:
    return f"{phone}.{tenant.uuid}@fitnation.local"
```

- `get_or_create_customer_by_phone` switches to it; `CustomerSerializer`'s synthetic path (`apps/customers/serializers.py:32-36,131-…`) imports the same helper (one behaviour, one definition).
- **No data migration** for existing `{phone}@fitnation.local` users: phone-match converges before email ever matters (ADR-002 rule 2), and both formats remain recognizable as synthetic (suffix checks for "reset email" logic should match on `@fitnation.local`).
- This unblocks ADR-002's "same human at two gyms = two accounts" without an IntegrityError.

---

## 4. Real OTP delivery (production sender chain)

### 4.1 Interface (unchanged shape, new resolution)

```python
# apps/users/otp.py
class OtpSender(ABC):
    name: str
    def send_otp(self, phone: str, code: str) -> None: ...   # raises OtpDeliveryError on failure

def resolve_otp_senders(tenant: Tenant) -> list[OtpSender]
```

`issue_otp` (signature unchanged, `apps/users/otp.py:87-124`) iterates the chain: first sender that doesn't raise wins; all raising → `OtpDeliveryError` → the view returns **503** `{"detail": "OTP delivery is temporarily unavailable — please contact the gym."}` and logs CRITICAL. Every attempt is logged to `NotificationLog` with the new `NotificationType.OTP = "otp"` (§5.3), so delivery has the same audit trail as invites.

### 4.2 The chain in production (`DEBUG=False`)

1. **`WatiOtpSender(tenant)`** — WhatsApp via the tenant's existing WATI config (`apps/tenants/models.py:46-48`), only when `tenant.is_wati_enabled and tenant.wati_api_key`.
   - Uses a WATI **template** message, not `sendSessionMessage`: business-initiated messages outside a 24 h customer-service window must use approved templates. Endpoint derived from the tenant's stored URL by normalization (correction #10): strip a trailing `/sendSessionMessage` if present → base; then `POST {base}/api/v1/sendTemplateMessage/fitnation_otp?whatsappNumber={phone_with_country_code}` with header `Authorization: {tenant.wati_api_key}` and body `{"templateParams": ["123456", "{gym_name}", "10"]}`.
   - WATI template to approve in the tenant's WATI console (one-time, Siju/tenant task): name **`fitnation_otp`**, body: `{{1}} is your {{2}} login code. Valid for {{3}} minutes. Never share this code.`
2. **`Msg91OtpSender`** — SMS fallback, platform-level (one account serves all tenants):
   - Env: `SMS_PROVIDER=msg91`, `MSG91_AUTH_KEY`, `MSG91_SENDER_ID` (6-char DLT header, e.g. `FITNAT`), `MSG91_TEMPLATE_ID` (DLT-approved template id), `MSG91_OTP_FLOW_ID` if using the flow API variant.
   - Contract: `POST https://control.msg91.com/api/v5/flow/`, headers `authkey: {MSG91_AUTH_KEY}`, body:
     ```json
     {"template_id": "{MSG91_TEMPLATE_ID}", "short_url": "0",
      "recipients": [{"mobiles": "91{phone}", "OTP": "{code}", "GYM": "{gym_name}"}]}
     ```
   - DLT-registered template text (registered once, variables locked to DLT rules): `{#var#} is your {gym} FitNation app login code. Valid for 10 minutes. Do not share. - FITNAT`
   - **Why MSG91 over Interakt**: WhatsApp is already per-tenant via WATI; the fallback needs a *carrier-grade SMS* pipe with DLT registration for India. MSG91's flow API is OTP-shaped and cheap. Picking a second WhatsApp BSP (Interakt) would duplicate WATI, not replace it.
3. **No third leg.** If neither is configured/working → the 503 above. Production never falls back to `console`.

### 4.3 Dev/test

- `DEBUG=True` (local/qa): `OTP_SENDER=console` (default) or `OTP_SENDER=stub` — both retained as today (`apps/users/otp.py:57-74`, `config/settings/test.py:5-6`).
- **`stub` hard-block:** `get_otp_sender()` raises `ImproperlyConfigured` when `OTP_SENDER == "stub"` and `not settings.DEBUG`. Belt-and-braces: `OTPRequestView` keeps returning the code only when `sender.name == "stub"` (`apps/users/views.py:177-178`) — unchanged.
- **`console` prod-guard:** `resolve_otp_senders` never returns `ConsoleOtpSender` when `DEBUG=False`, even if `OTP_SENDER=console` is mistakenly set — it resolves the real chain and logs a warning that the setting was ignored. Shipping with codes going to logs (correction #8) becomes structurally impossible.

### 4.4 Settings/env names (summary)

| Setting | Where | Purpose |
|---|---|---|
| `OTP_SENDER` | dev settings / `.env` | `console` \| `stub` (dev/test only) |
| `APP_ACCESS_GRACE_DAYS` | `base.py` | 7 |
| `SMS_PROVIDER` | prod env | `msg91` |
| `MSG91_AUTH_KEY` / `MSG91_SENDER_ID` / `MSG91_TEMPLATE_ID` | prod env (Secret Manager) | SMS credentials |
| `TENANT_WATI_OTP_DAILY_CAP` | `base.py` | per-tenant WhatsApp OTP budget, default 200/day |

### 4.4b Firebase phone-auth login (customer app, 2026-10)

The Flutter app signs members in with Firebase phone OTP inside the mobile
app's own Firebase project (`yougetfitwithus`) and exchanges the resulting
ID token at `POST /api/v1/auth/firebase/` for the identical OTP-verify
session payload (same anchor ladder, same convergence — one shared helper in
`apps/users/views.py`). Backend contract:

| Setting | Where | Purpose |
|---|---|---|
| `FIREBASE_CREDENTIALS` | prod env (Secret Manager) — **JSON CONTENT**, not a path | the mobile project's service-account JSON. Verification only reads Google's public certs, so the service account needs no extra IAM roles. Locally a file PATH is also accepted. |
| `GOOGLE_APPLICATION_CREDENTIALS` | local/dev only | ADC fallback file path when `FIREBASE_CREDENTIALS` is unset |
| `FIREBASE_PROJECT_ID` | `base.py` env override | defaults to `yougetfitwithus` — the ID-token aud/iss check target |
| `FIREBASE_VERIFY_DAILY_LIMIT_PER_IP` | `base.py` | per-IP daily cap on FAILED verifications (successes never count), default 50 |

Ops wiring (same SECRET-style pattern as `META_SYSTEM_TOKEN` / `DATABASE_URL`):
1. In the `yougetfitwithus` Firebase console → Project settings → Service
   accounts → *Generate new private key* (this is the JSON; it IS a secret —
   never commit it).
2. `gcloud secrets create firebase-service-account --data-file=sa.json`
   (project: the FBOS host project, same as the other provider secrets).
3. Attach to the Cloud Run dev/prod services as an env var source:
   `FIREBASE_CREDENTIALS` ← secret `firebase-service-account` (the env var
   receives the JSON content itself; the code sniffs `{` vs path).
4. Until steps 1–3 land, the endpoint answers **503
   `firebase_auth_misconfigured`** (fail closed + CRITICAL log) — correct by
   design, mobile login stays on the OTP fallback path.

### 4.5 Rate limits and failure modes

- Existing per-flow limits unchanged: 60 s resend cooldown, 10/phone/day, 50/IP/day (`apps/users/otp.py:98-112`); anchor-lookup throttle 10/10 min (`apps/users/services.py:198-213`).
- **New per-tenant WATI budget:** cache counter `wati-otp:{tenant}:{date}`; when the tenant's cap is hit, skip WATI and go straight to SMS (protects the gym's WATI wallet from OTP floods without blocking members).
- **Tenant with no WhatsApp config:** `WatiOtpSender` is simply not in the chain (a `skipped` NotificationLog row is *not* even written for OTP — noise); SMS carries delivery. SMS unconfigured too → 503 (loud), never a silent console drop.
- Front-desk impact of a 503: the onboarding wizard's OTP test is not part of onboarding; members just fail to log in — the CRITICAL log + sentry-style alert is the operator signal. Runbook item: check `NotificationLog` type `otp` for the day.

---

## 5. Invite flow + API contracts

### 5.1 Contracts

**(a) Front-desk onboarding submit** — `POST /api/v1/onboarding/member/` (the `apps/onboarding` service from `docs/onboarding-design.md` §3; this spec *adds* the invite ride-along, it does not re-spec the wizard):

Request — unchanged from onboarding-design §3.4, plus one flag:

```json
{ "customer": { "phone": "9876543210", "name": "Asha Nair", "branch": 2, "…": "…" },
  "membership": { "plan": 7, "start_date": "2026-10-21", "end_date": "2026-11-20" },
  "payment": { "method": "cash", "amount": 2500.00 },
  "biometrics": [],
  "send_welcome": true,
  "send_app_invite": true }
```

Response — the §3.4 shape plus an `app_invite` block (and `entitlement_preview`, so the success screen can show what the member will get):

```json
{
  "onboarding_id": "b1c7…", "status": "completed",
  "customer": {"id": 512, "name": "Asha Nair", "phone": "9876543210", "…": "…"},
  "membership": {"id": 318, "plan_name": "Monthly", "status": "active", "…": "…"},
  "payment": {"…": "…"}, "invoice_number": "INV-20261021-0042",
  "biometrics": [], "door_access": [],
  "notifications": [{"type": "welcome", "status": "sent"}],
  "app_invite": {
    "status": "sent",            // sent | skipped | failed | not_applicable
    "reason": null,              // "wati_not_configured" | "plan_excludes_app" | "flag_off" | …
    "channel": "whatsapp",       // whatsapp | sms
    "sent_at": "2026-10-21T10:41:05Z",
    "resend_allowed_after": null // ISO ts when the 24 h dedupe window frees up
  }
}
```

`not_applicable` when `plan.includes_app_access=false` or the tenant flag is off; `skipped` when WATI is unconfigured *and* SMS is unconfigured (per-tenant WhatsApp config gap → owner nudge, same philosophy as onboarding-design §4.5). Sends **after commit**, never raises into the response — same boundary rule as the wizard.

**(b) Send / resend invite** — new endpoint for members onboarded before this feature or whose invite failed:

```
POST /api/v1/memberships/app-invite/
Authorization: Token …      permission: customers.edit_customer
{ "customer_id": 512, "resend": false }
```

- **Idempotency / dedupe:** a *sent* `app_invite` log for the customer within `APP_INVITE_RESEND_WINDOW = 24 h` short-circuits the call:
  ```json
  200 { "status": "already_sent", "sent_at": "…", "resend_allowed_after": "2026-10-22T10:41:05Z" }
  ```
  `resend: true` forces a new send (front-desk override; still capped by §10 rate limits). A fresh send returns `201` with the §5.1(a) `app_invite` shape.
- **Retry semantics:** the wizard/success screen calls this same endpoint for `failed` invites. No `Idempotency-Key` header needed — customer + type + window is the idempotency key (unlike onboarding, a duplicate invite is merely spammy, never financially wrong).
- **Invite status surface:** `CustomerSerializer` gains a read-only `app_invite_status` (last `app_invite` NotificationLog for the customer: `{status, sent_at, channel, error_message}` or `null`), consumed by the customer-detail card and the wizard's returning-member path.

**(c) Entitlement check** — `GET /api/v1/users/auth/entitlement/` — contract in §2.3(c).

**(d) Deep-link / join contract** — §5.4.

### 5.2 The `app_invite` message templates

`NotificationType.APP_INVITE = "app_invite"` on `NotificationLog` (`apps/notifications/models.py:13-20`; `max_length=30` is fine).

**WhatsApp (WATI approved template `fitnation_app_invite`, 4 variables):**

> Hi {{1}}! Welcome to {{2}} 🎉 Your {{3}} membership is active.
> Get your workout & diet plans, check-in QR and progress tracking in the FitNation app: {{4}}

`templateParams: [member_name, gym_name, plan_name, invite_link]`.

**SMS fallback (DLT-registered):**

> Hi {name}, welcome to {gym}! Install the FitNation app: {link} — login with your mobile no. {phone}. - FITNAT

Per-tenant customization is limited to the *variable values* (gym name comes from `tenant.name` automatically — `wati_service.py:95-96`). Template *names* are fixed platform-wide because WATI templates are approved per WATI account; a tenant wanting custom copy approves the template in their own WATI console under the same name. The `MESSAGE_TEMPLATES` dict gains `app_invite` + `welcome` entries (the latter already specified in onboarding-design §3.5) so logged `content` is human-readable.

### 5.3 `send_app_invite` service

```python
# apps/notifications/services/invite_service.py
def send_app_invite(tenant, customer, *, invited_by: User | None = None,
                    force: bool = False, sender: Callable | None = None) -> NotificationLog
```

- Channel order: WATI template (tenant enabled) → MSG91 SMS (platform env) → log `failed`.
- Reuses `NotificationLog` for the audit trail. Add a nullable `actor = FK(users.User, …)` column to `NotificationLog` (migration) so invites record *who* sent them — the audit trail requirement in §10.
- The short link stored in `content` is the tenant-scoped URL of §5.4.

### 5.4 The link that survives Play install→open

Three-pronged (each prong degrades to the next):

| Prong | Mechanism | Captures anchor when |
|---|---|---|
| 1. App Link | `https://app.yougetfitwithus.com/g/{tenant_uuid}` (also `fitnation://g/{tenant_uuid}`) | app **already installed** → Android opens the app directly |
| 2. Play referrer | `https://play.google.com/store/apps/details?id=com.getfitwithus.app&referrer=gym%3D{tenant_uuid}` | fresh install via that exact Play link → Install Referrer API hands the app `gym={uuid}` on first open |
| 3. Gym code | human-readable `Tenant.gym_code` (§5.5) entered on the app's "Find your gym" screen | everything else (link shared as text, referrer lost, sideloaded APK) |

- The WhatsApp/SMS invite carries prong 1 as the tappable link. The redirect page (a tiny Next.js route in the ERP frontend, `/g/[uuid]/page.tsx`) renders "Get the FitNation app" with the Play badge wired to prong 2 and an `intent://` fallback: `intent://g/{uuid}#Intent;scheme=fitnation;package=com.getfitwithus.app;S.browser_fallback_url=<play+referrer>;end`.
- Domain **`app.yougetfitwithus.com`** is proposed (sibling of `api.yougetfitwithus.com`, `mobile/lib/core/config/app_config.dart:31`) — **Siju confirms the domain**; it must own the `assetlinks.json` App-Links verification file.
- **`fitnation_app` is not yet published, so referrer loss has a guaranteed floor:** the pilot uses the gym-code entry as the universal fallback, and single-gym deployments are the overwhelming case (phone-first auto-pin handles them without any anchor — `apps/users/services.py:240-243`).

### 5.5 `Tenant.gym_code` (new field)

```python
gym_code = models.CharField(max_length=8, unique=True, blank=True)  # e.g. "HX7K2QMA"
```

- Generated on save (uppercase, ambiguity-excluded alphabet `ABCDEFGHJKMNPQRSTUVWXYZ23456789`), collision-retry; migration backfills all existing tenants.
- Public lookup (non-sensitive: returns uuid + display name only):

```
GET /api/v1/tenants/lookup/?code=HX7K2QMA      → 200 {"uuid": "3f7c…", "name": "Hash Fit"}
                                               → 404 {"detail": "No gym found for that code."}
```

`AllowAny`, throttled (10/min/IP — same spirit as the anchor throttle). This is the screen behind case §3.2(b).

---

## 6. Front-desk UX (ERP)

Base design: `docs/onboarding-design.md` (wizard steps, 90-second budget, success screen). **What changes vs that proposal:**

| Area | onboarding-design (proposal) | FBOS-011 (this spec) |
|---|---|---|
| Route | `/onboarding` | **`/onboarding/member`** (route occupied by the vendor wizard — correction #2); entry points unchanged ("＋ New Member" on `/customers`, dashboard quick action, `/customers/new` redirect) |
| Step 2 plan cards | price/duration only | card badge **"📱 App included"** from `includes_app_access`; no badge when false |
| Success screen app line | static "Login ready — member signs into the mobile app with +91•••• using OTP." | live **invite chip** rendered from the response `app_invite` block: `sent` (green, "WhatsApp invite sent ✅"), `skipped` (amber, reason text), `failed` (red + **Resend** button) |
| Resend | "calls the notifications test/resend path" | **`POST /api/v1/memberships/app-invite/`** `{customer_id, resend: true}`; button shows cooldown from `resend_allowed_after` |
| Trial branch | unchanged | unchanged (invite still sent — trial members get the app; entitlement = active until trial `end_date`, then grace/gate as usual) |
| No-biometric-device branch | unchanged | unchanged (`biometrics: []`) |

New screens beyond the wizard:

- **Customer detail → App access card:** invite status chip + resend, entitlement summary (plan, `end_date`, grace date) fetched from the customer's memberships — the "why can't they log in?" debug surface for the front desk.
- **Tenant WhatsApp configuration — `app/settings/whatsapp/page.tsx`** (settings nav already exists):
  - Fields: `is_wati_enabled` (toggle), `wati_endpoint` (hint: paste the WATI API base, e.g. `https://api.wati.io` — the normalization rule in §4.2 tolerates the full session URL too), `wati_api_key` (write-only: displayed as `••••` after save).
  - **"Send test message"** button → new `POST /api/v1/tenants/whatsapp/test/` `{phone}` → sends the `welcome` template to the given number, returns the NotificationLog status. This is the moment the owner sees WhatsApp work.
  - **Usage line:** today's OTP+invite counts (`GET /api/v1/tenants/whatsapp/status/` → `{otp_sent_today, invites_sent_today, daily_cap}`) so wallet burn is visible.
  - Permissions: gym_owner only (`tenants.edit_tenant`). Backend: `PATCH /api/v1/tenants/me/` extended (`TenantSerializer` currently exposes neither WATI field nor PATCH — `apps/tenants/serializers.py:27-51`, `apps/tenants/urls.py`) with `wati_api_key` write-only.
  - This is the **prerequisite nudge loop**: without tenant WATI config, invites/OTP fall to SMS, and the settings page is where the "you're burning SMS money" story is told.

---

## 7. Mobile app changes (Flutter, `com.getfitwithus.app`)

### 7.1 Build identity & config fixes

- **Rename (D9):** `android/app/build.gradle.kts` — `namespace` and `applicationId` → **`com.getfitwithus.app`**; move `android/app/src/main/kotlin/com/fitnation/fitnation_app/` → `…/com/getfitwithus/app/` and update the `MainActivity.kt` package line. The app has never been published: no Play constraint, no installed base, no Deep Link namespace legacy. (Counterfactual for the checklist: after publication `applicationId` is immutable — this is the last cheap moment.)
- **API host fix (correction #7):** `AppConstants.apiBaseUrl` delegates to `AppEnvironment.apiBaseUrl` (the `SERVER` presets) instead of its own `String.fromEnvironment` default. One-line change, unblocks every pilot build.
- **Anchor precedence:** new `AnchorStore` (Hive): `effectiveAnchor = runtimeAnchor (from link/gym code) ?? AppEnvironment.gymAnchor (build-time)`. `AuthRemoteDataSource.requestOtp` keeps sending `gym`; **`verifyOtp` now sends it too** (correction #6).
- **Signing:** upload keystore + `key.properties` (gitignored), release `signingConfig` reads it (today release is signed with debug keys — `android/app/build.gradle.kts:32-35`). Full steps: `docs/play-release-checklist.md`.

### 7.2 Entitlement gate in GoRouter

- `AuthState` (`mobile/lib/features/auth/presentation/providers/auth_notifier.dart:13-35`) gains `entitlement: Entitlement?` (model parsed from the `entitlement` payload of §2.3; `AuthResponse.fromJson` extended).
- New routes: `/gate` (blocked screen) — the existing static route table (`mobile/lib/router/app_router.dart:54-198`) is untouched otherwise; the gate is a **redirect, not route removal**:

```dart
redirect: (context, state) {
  // existing auth redirects …
  final ent = authState.entitlement;
  final onGate = state.matchedLocation == '/gate';
  if (isAuthenticated && ent != null && ent.status != EntitlementStatus.active && !onGate) {
    return '/gate';       // status none | expired
  }
  if (isAuthenticated && onGate && ent?.status == EntitlementStatus.active) return '/dashboard';
  return null;
}
```

- Grace is **not** a redirect: a persistent banner widget (hosted in the dashboard shell) when `read_only == true`; writes show the disabled state (§3.4).
- **Re-validation triggers:** (1) login/verify response; (2) `/auth/me` on app start; (3) `GET /auth/entitlement/` on app resume (lifecycle event, throttled ≥ 15 min); (4) any 403 with `code: app_access_*` — the Dio interceptor sets the local entitlement accordingly and the router reacts. Server data always wins over the cached value.
- **Permission-driven navigation (minimal):** `PermissionChecker.customerPermissions` is replaced by checks against the server-returned `AuthState.permissions` (`app.access`, `ai_nutrition.view`, …). v1 scope: the gate + hiding nav destinations whose codes are absent. Do not build a full RBAC-driven route factory.

### 7.3 Deep-link + gym code capture

- AndroidManifest: `intent-filter` with `autoVerify` for `https://app.yougetfitwithus.com/g` + `fitnation://g`; `go_router` parses `/g/{uuid}` → persist to `AnchorStore` → if unauthenticated, continue to phone input (anchor now pinned); if authenticated under a *different* tenant, show a confirm sheet ("Switch to {gym}?") before overwriting — multi-gym members exist.
- Install Referrer: `install_referrer` plugin; on first launch, if `referrer` contains `gym={uuid}` and no runtime anchor is stored, persist it. Read once, then dispose the connection.
- **"Find your gym" screen** (reached from the phone-input screen's "Your gym isn't preselected?" affordance and from gate dead-ends): text field for the gym code → `GET /api/v1/tenants/lookup/?code=` → confirm card (name) → persist anchor.

### 7.4 FCM (push plumbing, notifications content later)

- Packages: **`firebase_core`** + **`firebase_messaging`** (Android only for now). One Firebase project for the app (not per gym); `google-services.json` checked into the repo (it is not a secret), Gradle plugin applied.
- Token registration: new backend model + endpoint (§8, B7) — `POST /api/v1/notifications/device-tokens/` `{token, device_id, platform, device_type}` (upsert), `DELETE` on logout. Request on login success and on token rotation (`onTokenRefresh`).
- Foreground/background message handling: v1 registers tokens and displays nothing custom (default system tray). Membership-expiry nudges and "workout assigned" pushes are a follow-up story — the endpoint and plumbing land now so the Play release isn't blocked later.
- Play side-effect: adding `firebase_messaging` pulls in the Play Services marker; no additional Play Console config beyond the Firebase project link.

### 7.5 Play/release, listing, health disclosures

Full runbook: `docs/play-release-checklist.md`. Highlights that touch app code:
- `applicationId`/`namespace` rename (§7.1) **before** the app shell is created in Play Console (Siju, one-time UI step — the service account cannot create app shells).
- Health apps declaration: the app stores health profile, body measurements and progress photos → the Play **Health apps** declaration and the **Data Safety** form are mandatory (contents tabulated in the runbook §5-§6).
- Account deletion: Play requires a deletion path for apps that create accounts → backend endpoint (§8, B8) + a "Delete my account" entry in the mobile profile screen (v1: web-form link is acceptable to Play; in-app is better).
- Tests mandated by AGENTS.md: widget tests for the three gate states; unit test for `AnchorStore` precedence; integration test **OTP → verify → gate** with mocked Dio; golden test for the grace banner.

---

## 8. Task breakdown (ordered, dependency-correct)

Every task ships tests in the same commit (AGENTS.md). "Contract" = the API shape each task depends on.

### Backend

| # | Task | Depends on | Acceptance criteria |
|---|---|---|---|
| **B1** | `MembershipPlan.includes_app_access` + migration (default True backfill); serializer/type field; `apps/memberships/selectors.py::get_app_entitlement` + `AppEntitlement`; `APP_ACCESS_GRACE_DAYS` | — | Plan CRUD round-trips the flag; selector unit tests for all 5 states (active/grace/expired/none/flag-off) incl. cancelled-no-grace and max-end_date selection |
| **B2** | `get_effective_permissions`; `EntitlementRequired`; wire into OTPVerifyView + MeView + entitlement endpoint; re-point stale "ADR-003 P0-x" comments to the docs | B1 | Verify response carries `app.access` + `entitlement` exactly per §2.3; grace write → 403 `app_access_read_only`; expired read → 403 `app_access_required`; staff unaffected; tenant-isolation tests |
| **B3** | Auto-provision fixes: `synthetic_otp_email` shared helper (both `users/services.py` + `customers/serializers.py`); verify-call anchor acceptance is frontend (M2) but backend already supports it; per-tenant auto-create daily cap | — | Cross-tenant regression test: same phone, two tenants, no IntegrityError; cap → 429; non-enumeration tests (§3.1/3.2 shapes byte-identical modulo entitlement) |
| **B4** | OTP sender chain: `resolve_otp_senders`, `WatiOtpSender` (template endpoint + normalization), `Msg91OtpSender`, stub hard-block, console prod-guard, 503 loud failure, `NotificationType.OTP`, per-tenant WATI cap | — | Fake-transport tests: happy WATI → no SMS; WATI down → SMS; both down → 503 + CRITICAL log; stub raises when `DEBUG=False`; cap skip-to-SMS |
| **B5** | Invites: `NotificationType.APP_INVITE`, `NotificationLog.actor` migration, `invite_service.send_app_invite`, `POST /memberships/app-invite/` (dedupe/resend), `app_invite_status` on CustomerSerializer, `MESSAGE_TEMPLATES` entries | B4 (channel reuse), B1 (not_applicable reason) | 24 h dedupe; forced resend; failed → retry; flag/plan skip reasons; tenant isolation; actor recorded |
| **B6** | `apps/onboarding` per `docs/onboarding-design.md` (wizard service, `OnboardingSession`, Razorpay two-phase, welcome type) **+ `app_invite` ride-along + `entitlement_preview`** | B5, B1 | All onboarding-design §8 tests, plus: invite block per §5.1(a); `send_app_invite=false` honored; invite failure never rolls back the member |
| **B7** | Device tokens: `DeviceToken` model (tenant-scoped), `POST/DELETE /api/v1/notifications/device-tokens/` | — | Upsert idempotent per token; logout deletes; other-user tokens invisible |
| **B8** | Account deletion: `POST /api/v1/users/auth/delete-account/` (anonymize user, deactivate customer, revoke tokens, purge OTP/device rows) | — | Data gone / anonymized per §10.5; business records retained; token dead immediately |
| **B9** | Tenant WhatsApp config: `PATCH /api/v1/tenants/me/` (WATI fields, key write-only), `POST /api/v1/tenants/whatsapp/test/`, `GET /api/v1/tenants/whatsapp/status/`; `Tenant.gym_code` + `GET /api/v1/tenants/lookup/` | — | Owner-only 403s; key never serialized out; test-send logs a NotificationLog; gym code backfill + lookup throttle tests |

### Frontend (Next.js ERP)

| # | Task | Depends on | Acceptance criteria |
|---|---|---|---|
| **F1** | Plan form toggle + type field (`MembershipPlanForm`, `types/membership.ts`) + "App included" badge in plan lists | B1 contract | Toggle round-trips; Jest tests for form + list badge |
| **F2** | Onboarding wizard at `/onboarding/member` (per onboarding-design §5, route changed) + success-screen invite chip + resend; entry points rewired | B6 contract | Playwright e2e cash-path asserts invite chip states; Jest per-state tests |
| **F3** | Customer detail: App access card (invite status, resend, entitlement summary) | B5 contract | Chip reflects `app_invite_status`; cooldown disables resend |
| **F4** | `/settings/whatsapp` config page (owner-only nav) | B9 contract | Save/toggle/test-send flows; key masked after save; Jest tests |

### Mobile (Flutter)

| # | Task | Depends on | Acceptance criteria |
|---|---|---|---|
| **M1** | Package rename `com.getfitwithus.app` (gradle + Kotlin sources), upload keystore + signing config, version policy doc, **API host fix (SERVER presets wired)** | — | `flutter build appbundle --release` succeeds signed with the upload key; `--dart-define=SERVER=prod` hits `api.yougetfitwithus.com` |
| **M2** | Anchor capture: deep links (App Link + custom scheme), Install Referrer, gym-code screen, `AnchorStore` precedence; `verifyOtp` sends anchor | B9 (lookup) | Widget tests: link parse, code lookup, precedence; deep-link intent test |
| **M3** | Entitlement: model + interceptor (403 codes), gate screen (3 variants), GoRouter redirect, grace banner, permission-driven nav v1 | B2 contract | Widget tests per §7.2; integration test OTP→verify→gate with mocked Dio; resume re-validation throttled |
| **M4** | FCM: firebase_core/messaging, token registration + logout deletion, `onTokenRefresh` | B7 contract | Token upsert called on login; deleted on logout; no crash without google-services.json in dev (guarded) |
| **M5** | Release prep: app icon/splash final assets, "Delete my account" entry, privacy-policy + terms links in-app | B8 (link target) | Profile screen shows deletion; links open; version bumped per policy |

### External / product-owner (blocking items for Siju) — see §9.3

---

## 9. Rollout + migration

### 9.1 Migration steps (deploy order: backend → frontend → mobile)

1. `memberships.00XX` — `AddField includes_app_access BooleanField(default=True)` → all existing plans `True` in the same DDL (no member loses access at rollout, per the locked decision).
2. `notifications.00XX` — `NotificationType` gains `otp`, `app_invite`, `welcome`; `NotificationLog.actor` nullable FK.
3. `tenants.00XX` — `Tenant.gym_code` + data backfill (unique codes).
4. No data migration for existing synthetic emails (§3.5).
5. Ops/env: set `MSG91_*` in Secret Manager; deploy; run `manage migrate`; smoke: `curl /api/v1/tenants/lookup/?code=…`, request a real OTP to a test phone.
6. Per-tenant enable: `tenant.features["app_access"] = true` (admin_ops/shell — the field exists, no migration), plus WATI config via the new settings page.

### 9.2 Flag semantics

- Flag **off** (default for existing tenants until onboarded): no `app.access` ever granted, invites `not_applicable` (reason `flag_off`), `EntitlementRequired` short-circuits allow (ERP/staff unaffected; old app versions keep working). Effectively: the feature doesn't exist for that tenant.
- Flag **on**: entitlement engine live for that tenant only. Multi-tenant isolation of the flag is tested like any tenant-scoped behaviour.

### 9.3 Pilot — "Hash Fit", 6 members

1. Siju: create the Play app shell (Console UI; service account can't), approve WATI templates `fitnation_otp` + `fitnation_app_invite` (+`welcome`) in Hash Fit's WATI account, confirm MSG91 account + DLT header/template, confirm deep-link domain, hand over the upload keystore custody plan (§9.5 checklist items 1-4).
2. Engineer: flag on for Hash Fit; WATI configured via settings page; internal-testing AAB uploaded (runbook §4); 6 members onboarded through `/onboarding/member` at the desk.
3. Acceptance: 6/6 invites `sent` (WhatsApp); 6/6 OTPs received; 5 install via invite link (anchor captured — verify gym shows in the app); 1 installs from raw Play search → gym-code path; one membership manually expired → grace banner visible, write attempt blocked; one cancelled → gated out; `NotificationLog` shows the full trail.
4. Roll forward to remaining tenants after the pilot retro (flag flip + WATI config per tenant; plans already `True`).

### 9.4 Mid-session revocation

- **Grace expiry / plan toggle-off:** entitlement is recomputed per request — the member's next API call gets `403 app_access_required` (or read-only 403s) and the interceptor routes to `/gate`. No push needed in v1.
- **Cancellation (front desk cancels a membership):** besides the above, `MembershipViewSet.cancel` triggers token revocation — `AuthToken.objects.filter(user=customer.user, is_active=True).update(is_active=False)` — when the customer has no other active membership. The device is logged out at the next request; re-login puts them on the `none` gate. This is cheap (indexed user filter), synchronous (no Celery), and matches the door-access propagation pattern (`_propagate_access_change`, `apps/memberships/views.py:82-98`).
- **An active workout mid-set:** local in-flight writes fail with the 403 code → snackbar + gate. Nothing is half-saved server-side (the 403 fires before the view body runs).

---

## 10. Security & privacy

1. **Rate limits** (all cache-based, fail-closed except where noted): OTP 60 s cooldown / 10-phone-day / 50-IP-day (existing); anchor+lookup throttle 10/10 min (existing); **new:** tenant auto-create cap 50/day (§3.1), tenant WATI OTP budget 200/day (§4.5), invite resend 24 h dedupe + 20 invites/tenant/day hard cap, `tenants/lookup/` 10/min/IP. Entitlement endpoint: standard auth only (single indexed query; abuse = self-harm).
2. **Audit trail:** every invite/OTP/welcome attempt is a `NotificationLog` row (type, status, channel-specific id, error, **actor**); onboarding records `OnboardingSession` (who onboarded whom); token revocations are visible via `AuthToken.is_active` + the cancel action's own audit. No new audit infrastructure needed.
3. **OTP leakage prevention:** `stub` impossible in prod (`ImproperlyConfigured` when `DEBUG=False`); `console` ignored in prod; codes only ever in the response under `stub`; hashed+phone-bound at rest, 5 attempts, single-use, 10-min TTL (all existing — `apps/users/otp.py`); delivery failures 503 with generic copy; no OTP values in `NotificationLog.content` (log channel metadata only).
4. **Non-enumeration preserved:** §3 response shapes; the anchor-less zero-match 400 is unchanged; the gym-code lookup returns only uuid+name and is throttled. Entitlement differences are observable only *after* possessing the phone (OTP) — that's the possession factor, not enumeration.
5. **DPDP / GDPR — health data:**
   - **Consent:** first-run consent screen after OTP verify (v1, mobile): plain-language notice that health profile, body measurements and progress photos are processed to deliver coaching features, with who (the gym, FitNation as processor) and a link to the privacy policy. Recorded server-side: `UserConsent(user, consent_type="health_data_v1", accepted_at, policy_version)` — new small model (B8 bundle). Writes to health features return `403 consent_required` until accepted (add to `EntitlementRequired`'s checks for body_analysis/health endpoints only).
   - **Deletion:** B8 endpoint anonymizes identity (email/phone/name → tombstones), keeps financial/business records (invoices are statutory), purges OTP/device tokens, deactivates the Customer. Progress photos/health rows: soft-deleted with the customer, hard-delete job is a phase-2 policy decision (**Siju**: retention window for financial vs health data).
   - **Minimization invites:** the invite message carries name/gym/plan/link only; OTP messages carry the code + gym name.
6. **Play disclosures** (full text in the runbook §5-§6): Health apps declaration — fitness & wellness data (health profile, body measurements, progress photos), user-generated, not for medical advice; Data Safety — collected: personal info (name, phone, email), health & fitness, photos; all encrypted in transit; deletion via in-app path; privacy policy URL is **mandatory before review** (**Siju**: host at `yougetfitwithus.com/privacy`).
7. **Revocation semantics:** §9.4 — cancel = tokens dead + gate; plan toggle = live revoke on next request; grace expiry = passive. Nothing trusts client-side state; the entitlement is re-derived from the DB for every request.

---

## Appendix A — Endpoint inventory (new/changed)

| Method & path | New/Changed | Auth | Purpose |
|---|---|---|---|
| `POST /api/v1/users/auth/otp/request/` | changed | AllowAny | sender chain (§4); response shape unchanged except 503 path |
| `POST /api/v1/users/auth/otp/verify/` | changed | AllowAny | + `entitlement`, effective `permissions` (§2.3) |
| `GET /api/v1/users/auth/me/` | changed | Token | + `entitlement` (§2.3) |
| `GET /api/v1/users/auth/entitlement/` | **new** | Token | app-resume entitlement check (§2.3c) |
| `POST /api/v1/users/auth/delete-account/` | **new** | Token | DPDP/Play deletion (§10.5) |
| `POST /api/v1/memberships/app-invite/` | **new** | `customers.edit_customer` | invite send/resend (§5.1b) |
| `POST /api/v1/onboarding/member/` (+`/verify-payment/`) | **new** (onboarding-design) | staff perms | wizard submit + invite ride-along (§5.1a) |
| `PATCH /api/v1/tenants/me/` | changed | `tenants.edit_tenant` | WATI config (§6) |
| `POST /api/v1/tenants/whatsapp/test/` | **new** | `tenants.edit_tenant` | test message (§6) |
| `GET /api/v1/tenants/whatsapp/status/` | **new** | `tenants.edit_tenant` | usage counters (§6) |
| `GET /api/v1/tenants/lookup/?code=` | **new** | AllowAny (throttled) | gym-code → uuid (§5.5) |
| `POST/DELETE /api/v1/notifications/device-tokens/` | **new** | Token | FCM registration (§7.4) |
| customer-facing content viewsets | changed | Token | `EntitlementRequired` appended (§2.4) |
