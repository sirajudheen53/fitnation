# New Member Onboarding — Single-Flow Design (Front Desk Wizard)

Status: Proposed (design only, not implemented)
Date: 2026-09-20
Branch: develop

## 1. Problem & Goal

Onboarding a walk-in member today takes 4+ disjoint API steps across 3+ pages
(create customer → assign membership → capture payment → enroll biometric on the
devices page), and the member never receives an app-invite/welcome message.

**Goal:** front desk onboards a new member in **under 90 seconds**, in one
wizard, ending with door access live and a WhatsApp welcome sent.

Non-goals: health profile, progress photos, workout/diet assignment (stays on
the customer detail page as today); mobile app changes (the customer's phone
already IS their login — phone OTP per ADR-003/ADR-002).

---

## 2. Wizard UX — "New Member Onboarding"

One route: **`/onboarding`** (entry buttons: Customers page "＋ New Member",
Dashboard quick action). Three steps + success screen. Progress stepper on top;
every step is one screen, Enter advances, Back is free until submit.

### Step 1 — Who (target ≤ 25s)

1. **Phone first** (big field, numeric keypad). On blur: lookup
   `GET /api/v1/customers/?search={phone}`.
   - **Returning member found** → yellow banner: *"Returning member — their
     profile will be updated, not duplicated"* with a link to open the existing
     profile. The wizard continues (renewal = same flow).
   - No match → normal new-member path.
2. Fields: Name (single full-name field, maps to `name`), DOB, Gender
   (segmented: M/F/Other), Branch (defaults to the staff member's branch).
   Email **optional** — if blank the backend derives the synthetic identity
   `{phone}@fitnation.local` (see §4.3). Emergency contact optional, collapsed
   under "More".

### Step 2 — Plan & Payment (target ≤ 30s)

1. **Plan cards** from `GET /api/v1/memberships/membership-plans/?is_active=true`
   — grouped by `plan_type` (Monthly / Yearly / PT / Trial). Card shows name,
   price, duration. Trial plans visually distinct ("3-day trial").
2. Summary line auto-computed: *Membership valid 20 Sep → 19 Oct (30 days)* —
   `end_date = today + plan.duration_days`, editable via a small date override.
3. **Payment method** — segmented control:
   - **Cash / UPI-at-desk / Card** → amount field prefilled with plan price
     (editable for discounts), note field optional.
   - **Razorpay (link/checkout)** → checkout happens after submit (two-phase,
     see §4.4).
   - **Trial (₹0)** → payment section hidden entirely when
     `plan.plan_type == "trial"` and price is 0.

### Step 3 — Biometric (target ≤ 25s, skippable)

1. Device dropdown prefilled from `GET /api/v1/access/devices/?branch={id}`
   (active devices only). **No device at this branch** → step renders as
   *"No biometric device at this branch — member will check in via the app/QR"*
   with a Skip button; nothing to do.
2. Instruction panel: *"Ask the member to place their finger on the scanner."*
   The device hardware captures the template locally and shows/dispatches its
   assigned **device user ID**; front desk confirms it (or the adapter-provided
   ID auto-fills). Credential type defaults to fingerprint; face selectable.
3. "Skip for now" always available (member can enroll later from the customer
   detail → Access tab).

### Submit → Success screen (target ≤ 10s)

Single **"Finish onboarding"** button → one `POST /api/v1/onboarding/member/`
(cash/offline) or POST → Razorpay checkout → verify (online, §4.4).

Success screen — the receipt of the whole flow:

- ✅ **Member card**: name, phone, plan, validity dates, branch.
- 🚪 **Door access**: per-device chip — *"Main Door: ACTIVE (synced)"* or
  *"Main Door: credential saved, device offline — Retry sync"* (calls existing
  `POST /api/v1/access/devices/{id}/sync/`).
- 📱 **App invite line**: *"Login ready — member signs into the mobile app with
  +91•••• using OTP."* (the phone IS the login; no password to hand over).
- 💬 **WhatsApp status**: *"Welcome message sent ✅ / not configured / failed —
  Resend"* (calls the notifications test/resend path).
- 🧾 **Payment**: method, amount, invoice number (`INV-YYYYMMDD-NNNN`).
- CTAs: **View member profile** · **Onboard next member** (resets to step 1,
  keeps branch selected — the busy-Saturday loop).

### 90-second budget

| Step | Budget | Dominant cost |
|---|---|---|
| 1 Who | 25s | typing name/DOB |
| 2 Plan & payment | 30s | plan choice, counting cash |
| 3 Biometric | 25s | physical finger scan |
| Submit + success | 10s | one request + device sync |
| **Total** | **90s** | |

---

## 3. Backend Design — `POST /api/v1/onboarding/member/`

New Django app `apps/onboarding` (urls mounted as
`path("api/v1/onboarding/", include("apps.onboarding.urls"))`), layered like the
rest: `serializers.py` (contract), `services.py` (orchestration, writes),
`selectors.py` (session reads), `views.py` (thin).

Auth/tenant: `TenantTokenAuthentication` + `IsTenantMember` + `RolePermission`,
checking the union of what the flow touches: `customers.create_customer`,
`memberships.create_membership`, `payments.record_payment`,
`customers.edit_customer` (the access app already maps enroll/sync to this).

### 3.1 Orchestration service

`apps/onboarding/services.py::create_member_onboarding(*, tenant, user, payload)`

```
validate payload (OnboardingMemberSerializer)

with transaction.atomic():                      # local writes — all-or-nothing
    1. customer  = reuse CustomerSerializer.create()          # ADR-002 convergence (§3.2)
    2. membership = create + refresh_status()                  # mirrors MembershipViewSet.create
    3. payment    = cash/offline → status=completed, paid_at=now, Invoice created
                    trial     → payment may be omitted
                    razorpay  → status=pending (completed later in verify step)
    4. credentials = enroll_credential(...) per biometrics[]   # registry rows only
    5. session     = OnboardingSession(status=..., result=...) # audit + idempotency

# post-commit, best-effort — failures reported, never raised (§3.4):
    6. razorpay_service.create_order(...)  (online only, before responding)
    7. sync_device(device) per enrolled device (or sync_customer_devices)
    8. wati_service.send_notification(... "welcome") (+ "payment_received" if paid)

return composite result dict → response serializer
```

Transaction boundary rule: only local DB writes inside `atomic()`. Razorpay
order creation (network), device sync (adapter network) and Wati HTTP
(network) run after commit inside the same request; each already degrades
gracefully (`sync_device` returns `{"synced": False, ...}`;
`send_notification` logs `failed`/`skipped` and never raises — both verified
behaviors), so a flaky WhatsApp or an offline door can never roll back a
member who has paid.

### 3.2 Reuse of customer creation (ADR-002) — no duplication logic

The phone-linking logic already lives in
`CustomerSerializer.create()` (`apps/customers/serializers.py`): phone match on
a tenant user → link + adopt the OTP-provisioned profile, or 400
`phone_already_registered` when the phone belongs to a *different real* email;
no match → provision a customer-role user with unusable password (OTP login).
The service invokes that serializer with `context={"request": …}` (it needs
`request.tenant`). Recommended cleanup (optional, ~2h): extract
`apps/customers/services.py::create_customer()` from the serializer and have
both the existing `POST /customers/` and onboarding call it — pure refactor,
existing endpoint contract unchanged.

### 3.3 New persistence: `OnboardingSession` (one small model + migration)

```
OnboardingSession(TenantModelMixin):
    uuid (uuid4, unique, db_index)
    created_by FK(users.User)
    status: pending_payment | completed | abandoned
    request_payload JSON     # snapshot for idempotency + resume
    result JSON              # the composite response
    created_at / updated_at
```

Why: (a) the Razorpay verify step needs a resumable handle (§4.4); (b)
double-submit protection — the client sends `Idempotency-Key: <uuid>`; a repeat
POST with the same key returns the stored `result` instead of creating a second
membership; (c) an audit trail of who onboarded whom.

### 3.4 Request / response contract

`POST /api/v1/onboarding/member/` (header `Idempotency-Key` optional)

```json
{
  "customer": {
    "phone": "9876543210",              // required
    "name": "Asha Nair",                // required (or first/last)
    "email": "",                        // optional → {phone}@fitnation.local
    "date_of_birth": "1994-03-12",      // optional
    "gender": "female",                 // optional
    "branch": 2                         // required
  },
  "membership": {
    "plan": 7,                          // required, active plan in tenant
    "start_date": "2026-09-20",         // default today
    "end_date": "2026-10-20"            // default start + plan.duration_days
  },
  "payment": {                          // omit entirely for ₹0 trials
    "method": "cash",                   // cash|card|upi|bank_transfer|other|razorpay
    "amount": 2500.00,                  // default plan.price (discounts allowed)
    "notes": "inaugural offer"
  },
  "biometrics": [                       // omit / empty to skip
    {
      "device": 3,                      // active device, same tenant (branch-checked)
      "credential_type": "fingerprint",
      "device_user_id": "1017"          // id assigned by the device at scan time
    }
  ],
  "send_welcome": true                  // default true
}
```

Response `201` (cash/offline — the 90-second path):

```json
{
  "onboarding_id": "b1c7…",
  "status": "completed",
  "customer": {"id": 512, "name": "Asha Nair", "phone": "9876543210",
                "email": "9876543210@fitnation.local", "branch": 2, "is_active": true},
  "membership": {"id": 318, "plan_name": "Monthly", "start_date": "2026-09-20",
                 "end_date": "2026-10-20", "status": "active"},
  "payment": {"id": 901, "method": "cash", "amount": "2500.00",
              "status": "completed", "paid_at": "2026-09-20T10:41:02Z"},
  "invoice_number": "INV-20260920-0042",
  "biometrics": [
    {"credential_id": 77, "device_id": 3, "device_name": "Main Door",
     "sync": {"synced": true, "pushed": 143, "detail": "Pushed allow-list to 'Main Door'."}}
  ],
  "door_access": [
    {"device_id": 3, "allowed": true, "source": "plan", "reason": "Active membership"}
  ],
  "notifications": [
    {"type": "welcome", "status": "sent", "wati_message_id": "…"},
    {"type": "payment_received", "status": "sent"}
  ]
}
```

`door_access` is computed with the existing selector
`get_customer_access_state(customer, device)` — it reflects what the rule
engine will actually decide at the door, not an optimistic guess.

### 3.5 Notification additions (small, additive)

- `NotificationType.WELCOME = "welcome"` choice on `NotificationLog` (+ the
  choices migration).
- Template in `MESSAGE_TEMPLATES`:

  ```
  "welcome": "Welcome to {gym_name}, {customer_name}! 🎉 Your {plan_name} membership
  is active until {end_date}. Install the FitNation app and sign in with {phone} to
  get your plans. See you at the gym! 💪"
  ```

- Trial/₹0 flows send only `welcome`; paid flows also send the existing
  `payment_received`.

---

## 4. Edge Cases

### 4.1 Phone already exists (returning member)

Handled by the reused ADR-002 convergence in `CustomerSerializer.create()`:

- **Synthetic/OTP identity** (`{phone}@fitnation.local`, from the member having
  logged into the app earlier) → **linked and adopted**: profile updated with
  the payload, `is_active=True`, no duplicate user or customer row. Response
  includes `"returning_member": true` so the success screen can say
  *"Welcome back"*.
- **Phone belongs to a different real email** → the serializer raises 400
  `phone_already_registered`. The wizard catches it and shows: *"This number is
  linked to another account — open that member or use a different number"*
  with a link to the matched customer.
- The frontend lookup in Step 1 is a UX nicety only; correctness is enforced
  server-side by the same rule the plain `POST /customers/` uses today.

### 4.2 Payment: cash vs Razorpay

- **Cash / UPI-at-desk / card / bank-transfer** — single POST completes
  everything atomically; payment `status=completed`, `paid_at=now`, invoice
  created (mirroring what `RazorpayVerifyView` does — note
  `PaymentViewSet.create` today does *not* create the invoice; the onboarding
  service creates one so every onboarding payment has a printable receipt).
- **Razorpay** — two-phase, because an order needs a customer and a signature
  needs a checkout:
  1. `POST /onboarding/member/` with `method: "razorpay"` creates, in one
     transaction, **customer + pending payment + OnboardingSession only**
     (no membership, no biometric write yet), then calls
     `razorpay_service.create_order()`. Responds `201` with
     `status: "pending_payment"` + `razorpay_checkout: {key, order_id, amount,
     currency}` from `GET /payments/razorpay/config/` + the order.
  2. Frontend runs the existing Razorpay checkout (`features/razorpay`).
  3. `POST /api/v1/onboarding/member/{session_uuid}/verify-payment/` with
     `{razorpay_order_id, razorpay_payment_id, razorpay_signature}` →
     `razorpay_service.verify_signature()` (local HMAC, no network), then one
     transaction creates **membership + credentials + invoice**, marks the
     payment completed, syncs devices, sends welcome — same success response
     shape as §3.4.
  - Deferring the membership to verification means door access can never go
    live before money is captured. Verify failure (bad signature) → payment
    `failed`, session stays `pending_payment`, wizard shows "Payment failed —
    retry or take cash" and the same session can be re-ordered.

### 4.3 Branch with no biometric device

Step 3 auto-skips (UI). In the API, `biometrics: []` is fully valid: no
credentials created, `sync`/`door_access` arrays empty, response carries
`"biometrics": {"skipped": "no_device_at_branch"}`. The member still gets
membership + payment + welcome and checks in via the attendance app
(`log_check_in` / app QR paths). Offline device at sync time: credential is
saved, `sync.synced=false` surfaces as a Retry chip on the success screen
(existing `POST /access/devices/{id}/sync/`).

### 4.4 Trial / plan with no expiry

- `MembershipPlan.duration_days` is a required PositiveIntegerField and
  `Membership.end_date` is non-null — **open-ended memberships are not
  representable today**. Design decision: keep it that way. A trial is simply a
  `plan_type="trial"` plan with a short `duration_days` (1–14); the wizard
  computes `end_date = start + duration_days` and displays it. If the product
  later demands truly non-expiring plans, that is a schema change tracked
  separately (nullable `end_date` + rule-engine handling) — out of scope here.
- ₹0 trial → `payment` omitted; no payment row, no invoice, welcome only.

### 4.5 Other failure modes

- **Double-submit** — `Idempotency-Key` + `OnboardingSession` returns the
  stored result (§3.3).
- **Mid-flow crash after commit, before response** — session row exists with
  `result`; a retry with the same key replays the stored result rather than
  duplicating.
- **Wati disabled for tenant** (`is_wati_enabled=False`) — notification logged
  `skipped`; success screen shows "WhatsApp not configured" (owner nudge, not
  a front-desk problem).
- **Front desk lacks a permission** (e.g. can create customers but not record
  payments) — 403 before any write; wizard is gated client-side by the same
  permission checks (`lib/permissions.ts`).

---

## 5. Frontend Design

- **Route:** `app/onboarding/page.tsx` (client component) + feature folder
  `features/onboarding/` following the existing convention:
  `components/` (StepCustomer, StepPlanPayment, StepBiometric,
  SuccessPanel, ReturningMemberBanner), `hooks/` (React Query mutations).
- **State:** local stepper state (Zustand not needed — single page, no
  cross-page UI state); server state via React Query:
  - `useCustomerLookup(phone)` → `GET /customers/?search=`
  - `usePlans()` → `GET /memberships/membership-plans/?is_active=true`
  - `useBranchDevices(branchId)` → `GET /access/devices/?branch=`
  - `useOnboard()` → `POST /onboarding/member/`;
    `useVerifyOnboardingPayment()` → `POST …/{uuid}/verify-payment/`
  - `useRetrySync(deviceId)` → existing `POST /access/devices/{id}/sync/`
- **API client:** typed functions in `lib/api.ts` alongside the existing ones;
  idempotency key generated with `crypto.randomUUID()` per wizard run.
- **Razorpay:** reuse `features/razorpay` checkout lib verbatim for the online
  path; cash path never opens checkout.
- **Entry points:** "＋ New Member" on `/customers` header, Dashboard quick
  action card, and `/customers/new` redirects to `/onboarding` (one canonical
  flow; the old separate `/memberships/assign` page remains for renewals by
  existing members' profiles).
- **Success state:** renders exactly the §2 receipt — door-access chips from
  `door_access[]` + `biometrics[].sync`, WhatsApp status from
  `notifications[]`, invoice number, and the "sign in with phone OTP" invite
  line. "Onboard next member" resets state keeping branch/plan filters.

---

## 6. Effort Estimate

| Area | Item | Hours |
|---|---|---|
| Backend | `apps/onboarding` app: serializers, `services.py`, view, urls | 8–10 |
| Backend | `OnboardingSession` model + migration | 1–2 |
| Backend | Razorpay two-phase (order hook + verify-payment action) | 3–4 |
| Backend | `welcome` notification type, template, migration | 1 |
| Backend | Optional: extract `customers/services.create_customer` refactor | 2 |
| Backend | Tests (see §8) — API integration, tenant isolation, idempotency, all payment/biometric/trial branches | 8–10 |
| **Backend total** | | **23–29 h** |
| Frontend | Wizard page + 3 step components + stepper | 10–12 |
| Frontend | Success panel (door access, WhatsApp, invoice, retry actions) | 4–5 |
| Frontend | API client + hooks + returning-member lookup | 3 |
| Frontend | Razorpay path wiring (reuse checkout lib) | 2 |
| Frontend | Jest/RTL unit tests + one Playwright e2e (cash happy path) | 6–8 |
| **Frontend total** | | **25–28 h** |
| **Total** | | **~48–57 h** (≈ 1.5–2 weeks single full-stack dev) |

---

## 7. What Already Exists and Is Reused (verified on `develop`)

**Services / domain logic**

| Piece | Location | Notes |
|---|---|---|
| Customer create + ADR-002 phone identity convergence | `apps/customers/serializers.py` `CustomerSerializer.create()` | link/adopt/provision; `phone_already_registered` 400 |
| Synthetic OTP email scheme | same, `_synthetic_otp_email()` → `{phone}@fitnation.local` | used when email omitted |
| Membership status machinery | `apps/memberships/models.py` (`refresh_status`, `compute_status`) | reused; service mirrors `MembershipViewSet.create` |
| Biometric enrollment | `apps/access/services.py::enroll_credential()` | tenant + per-device uniqueness validated |
| Device allow-list sync | `apps/access/services.py::sync_device()`, `sync_customer_devices()` | never raises; `{synced, pushed, detail}` |
| Door-access rule engine | `apps/access/selectors.py::get_customer_access_state()` | powers `door_access` in the response |
| Razorpay order + signature verify | `apps/payments/razorpay_service.py::create_order()`, `verify_signature()` | verify is local HMAC |
| Invoice auto-numbering | `apps/payments/models.py` `Invoice._generate_invoice_number()` | `INV-YYYYMMDD-NNNN` |
| WhatsApp send + logging | `apps/notifications/services/wati_service.py::send_notification()` | never raises; sent/failed/skipped log |
| Tenant scoping / auth | `TenantTokenAuthentication`, `IsTenantMember`, `RolePermission`, `for_tenant()` managers | as on every endpoint |

**Existing endpoints (unchanged, still used by other pages / the wizard's read steps)**

- `POST /api/v1/customers/` — plain create (stays; onboarding wraps the same logic)
- `POST /api/v1/memberships/` — plain assign (stays for renewals)
- `POST /api/v1/access/devices/enroll/` — interactive enroll (stays; **note the verified route is `devices/enroll/`, the action lives on `BiometricDeviceViewSet`**)
- `POST /api/v1/access/devices/{id}/sync/` — retry chip on success screen
- `GET /api/v1/access/check/` — door-access verification
- `POST /api/v1/payments/razorpay/create-order/` / `verify/` / `GET …/config/` — reused internally / by checkout
- `GET /api/v1/customers/?search=` , `GET /api/v1/memberships/membership-plans/`, `GET /api/v1/access/devices/?branch=` — wizard lookups
- Frontend: `features/razorpay` (checkout), `lib/api.ts`, `lib/permissions.ts`, customer/membership/device pages for later management

**Genuinely new** (nothing else): `apps/onboarding` (service + view + serializer +
urls), `OnboardingSession` model, `welcome` notification type/template, the
`/onboarding` wizard page, and invoice creation on the cash path (today only
Razorpay verify creates invoices).

---

## 8. Test Plan (same-commit, per AGENTS.md)

Backend (pytest/APITestCase, `apps/onboarding/tests.py`):
happy path cash / happy path trial (no payment) / Razorpay phase-1+verify /
bad signature leaves no membership; ADR-002 branches (synthetic link-adopt,
conflicting email 400); no-device branch; offline-device sync reported not
raised; Wati disabled → `skipped`; idempotency-key replay; tenant isolation
(tenant B cannot see/onboard into tenant A); permission 403s; `end_date`
defaults and overrides.

Frontend: Jest/RTL per step component (lookup banner, plan cards, payment
toggle, skip-biometric, success states incl. retry chips, error states);
one Playwright e2e for the cash happy path with mocked API.
