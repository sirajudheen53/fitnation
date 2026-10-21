# QA Verification — Customer App-Access Workflow (FBOS-011)

**QA (Shield) 🛡️** · 2026-10-21 · branch `develop` (head 3269bf0 at time of report)
**Scope:** the member journey from the front desk to the Flutter customer app (`com.getfitwithus.app`),
gated by membership entitlement, invited over WhatsApp (WATI, SMS fallback), identified by phone + OTP.
**Verdict:** **SHIP** — one non-blocking defect (QA-DEF-001, major) with a clearly-labelled follow-up.
Nothing observed blocks Play submission of the QA rehearsal build.

---

## 1. Reproduction commands

Everything below was executed locally on this branch. All test invocations are the project's own
(CI parity: `.github/workflows/ci.yml`).

| Area | Command |
| --- | --- |
| Backend full suite (CI parity: coverage ≥ 80 %) | `cd backend && .venv/bin/python -m pytest --cov=. --cov-report=term` |
| Backend QA journey (recorded log) | `cd backend && .venv/bin/python -m pytest -s tests/test_app_access_rehearsal_log.py` |
| Backend QA suites | `pytest tests/test_app_access_e2e.py tests/test_app_access_qa_rate_limits.py tests/test_app_access_qa_regressions.py` |
| Frontend (CI parity) | `cd frontend && npm run test -- --coverage --coverageThreshold='{"global":{"lines":80}}'` and `npx eslint . --max-warnings 50` |
| Mobile (CI parity) | `cd mobile && flutter test --coverage` and `dart analyze --fatal-warnings` |
| AAB | `cd mobile && flutter build appbundle --release` → `keytool -printcert -jarfile <aab>` → `bundletool dump manifest/validate` |

Determinism: the WATI/SMS transports are faked in-process (`mock` on `requests.post`), the OTP sender is
the DEBUG-stub, and no real WhatsApp/SMS send, FCM delivery, or Play upload happens anywhere in this run.

## 2. Test-run results (the evidence)

| Area | Suite | Result | Coverage | Gate |
| --- | --- | --- | --- | --- |
| Backend | full pytest | **1118 passed, 12 subtests**, 1 expected-xfail (QA-DEF-001) | **83 %** lines (11 317 stmts) | ✔ ≥ 80 % |
| Backend | QA e2e rehearsal (`test_app_access_e2e.py`) | **18 / 18 passed** | — | ✔ |
| Backend | QA rate limits (`test_app_access_qa_rate_limits.py`) | **15 / 15 passed** | — | ✔ |
| Backend | QA regressions (`test_app_access_qa_regressions.py`) | **14 / 14** (1 xfails → QA-DEF-001) | — | ✔ |
| Frontend | jest (CI flags) | **507 / 507 passed** (35 suites), incl. `qa-app-access-contract.test.tsx` | **88.58 %** lines | ✔ ≥ 80 % |
| Frontend | eslint `--max-warnings 50` | exit 0, no findings | — | ✔ |
| Mobile | `flutter test --coverage` | **480 / 480 passed** | **80.87 %** lines (lcov) | ✔ ≥ 80 % |
| Mobile | `dart analyze --fatal-warnings` | *No issues found!* | — | ✔ |
| AAB | `flutter build appbundle --release` | built in 72.9 s, 55.6 MB | — | ✔ |

Key raw output lines (abridged):

```
backend:  1 xfailed, 1119 passed, 2 warnings, 12 subtests passed in ~39s      (pytest, test settings)
backend:  TOTAL                                            11317   1892    83%
frontend: Test Suites: 35 passed, 35 total / Tests: 507 passed, 507 total
frontend: All files | 88.58 | ... (lines)  — coverageThreshold global lines 80 OK
mobile:   01:40 +480: All tests passed!   (flutter test --coverage)
mobile:   lines hit=3987/4930 → 80.87 %  (lcov.info)
mobile:   Analyzing mobile... No issues found!  (dart analyze --fatal-warnings)
aab:      ✓ Built build/app/outputs/bundle/release/app-release.aab (55.6MB) — Gradle bundleRelease 72.9s
```

## 3. Release-build facts (verified against the built artifact, not the docs)

From the actual `app-release.aab` produced by this run:

| Fact | Verified value | How |
| --- | --- | --- |
| `package` / applicationId | `com.getfitwithus.app` | `bundletool dump manifest` ↔ `build.gradle.kts:32` |
| versionCode / versionName | `1` / `1.0.0` | `bundletool dump manifest` ↔ `pubspec.yaml (1.0.0+1)` |
| minSdk / targetSdk | 24 / **36** (Play floor met) | `bundletool dump manifest` ↔ pinned in `build.gradle.kts:36` |
| Signing | **FitNation Upload** cert (CN=FitNation Upload, O=FitNation, valid → 2054, SHA-256 `E2:3A:7B:D7:…`) | `keytool -printcert -jarfile` |
| Structure | `bundletool validate` exit 0 | |

Play-Console interaction (upload itself) was **not** exercised — ground rule: no Play uploads.

## 4. Backend contract — verified against the code, not only the tests

1. **Entitlement endpoint** — the live endpoint is **`GET /api/v1/users/auth/entitlement/`**
   (`apps/users/urls.py:29`, `EntitlementView`), per FBOS-011 §2.3c. The verification brief calls it
   `app-access`; **no `/auth/app-access/` route exists** and none is needed — the spec doc, backend,
   ERP and Flutter client all agree on `entitlement`. Likewise the payload key is `entitlement`
   (`{"status", "read_only", "plan_name", "end_date", "grace_end_date", "gym": {uuid, name}}`), not
   `app_access`. Recorded as a brief/doc nit below, not a defect.
2. **Entitlement matrix** (`apps/memberships/selectors.py::get_app_entitlement`) — exactly the locked
   decisions, in order: rollout flag off → `none`; no non-cancelled membership → `none`; plan without
   `includes_app_access` → `none`; `today ≤ end_date` → `active`; `end_date < today ≤ end_date + 7` →
   `grace` (read-only, `grace_end_date` set); beyond → `expired`; cancelled → immediate `none`
   (cancellation bypasses grace — a business act, ADR-003). Rehearsal-log lines 4a–4d evidence the flips.
3. **`app.access` permission layering** (`apps/users/services.py::get_effective_permissions`) — added
   **iff** the entitlement status ∈ {`active`, `grace`} for customer-role users, in both the OTP-verify
   and `/auth/me/` responses and nowhere else. Expired/none keep the bare role set.
4. **Non-enumeration** — `resolve_tenant_for_otp` + `get_or_create_customer_by_phone`: an **unknown**
   phone and a **known-but-unentitled** phone both answer 200 with an identical key set, identical
   permission list and `entitlement.status = "none"`; auto-provisioned accounts get no entitlement and
   the API never hints registration state (`apps/users/services.py`). Note: the previous draft of the
   non-enumeration test verified the *same* phone twice (vacuous); fixed in commit 9fa7086 to use a
   never-registered phone — still passes, now meaningfully.
5. **OTP delivery chain** (`apps/users/otp.py::resolve_otp_senders`) — `stub` raises
   `ImproperlyConfigured` outside DEBUG (hard-blocked from echoing codes in prod); `console` is ignored
   in prod with a warning; `auto` = tenant WATI template leg (when `is_wati_enabled` + API key set)
   then MSG91 SMS; an empty/unconfigured chain fails loudly (503), never a silent log drop. Codes are
   6-digit, hashed at rest, single-use, phone-bound, expiry-enforced; the delivered code never reaches
   the audit log.
6. **Rate limits** — resend cooldown (a *sent* invite is `already_sent` + `resend_allowed_after`; forced
   resend goes out again), per-phone daily cap, per-IP daily cap (distinct IPs don't starve each other),
   and the tenant invite cap answering 429. All pinned by `test_app_access_qa_rate_limits.py`.
7. **Invite endpoint** (`apps/notifications/services/invite_service.py`) — real status vocabulary is
   `sent / skipped / failed / not_applicable / already_sent` + machine-readable `reason`
   (`wati_not_configured`, `flag_off`, `plan_excludes_app`, `daily_limit_reached`); the brief's
   "not_configured" is the *reason* on the `skipped` leg, consumed by the ERP (wizard.ts) as a warning.
   The failed invite never rolls back the member (regression-tested); the audit trail records the actor
   but never the delivered code.
8. **Onboarding submit** — one call (`POST /api/v1/onboarding/member/`) creates customer + membership +
   payment + invoice atomically; repeating the same phone reuses the customer (and the same-day
   double-sell guard holds); the invite rides inside the 201 payload with `entitlement_preview`; a
   flag-off tenant gets `not_applicable`/`flag_off` and continues to work ungated.
9. **Device tokens** (`apps/notifications/device_views.py`) — tenant-scoped by construction; the
   queryset only ever returns the caller's own rows; cross-tenant read/delete → 404; registration is
   idempotent **by design but not in behaviour** — see QA-DEF-001 below.

## 5. Frontend verification

- `MembershipPlanForm` — `includes_app_access: z.boolean().default(true)` and create-defaults `true`
  (toggle ON by default, persists with the plan form).
- Onboarding wizard — full flow green: single POST submit incl. biometrics; returning-member banner on
  phone lookup; ₹0 trial plan hides the payment block; missing biometric device skips the biometric
  step; failed invite offers a working Resend; unconfigured invite shows as a warning without a resend.
- `AppAccessCard` / `appAccess.ts` — the **server entitlement block is the source of truth** (a locally
  "active" membership cannot override a server `expired`); entitled/grace/not-entitled render the
  documented states. Pinned by `__tests__/qa-app-access-contract.test.tsx` + `app-access-card.test.tsx`
  + `customers-app-access.test.tsx`.

## 6. Mobile verification (headlessly testable parts)

- **Join-link parsing** (`lib/core/deeplink/join_link.dart`) — https App Links
  (`https://app.yougetfitwithus.com/g/{uuid}`, `https://api…/join?gym={uuid}&t={token}`) and custom
  scheme (`fitnation://g/…`, `fitnation://join?gym=…`) both parse with UUID validation; 14 + 18 tests.
- **Anchor precedence** (`AnchorStore.effectiveAnchor`) — runtime (link/referrer/code) > build-time
  `--dart-define GYM_ANCHOR` > none (backend phone-first); sticky across logout/restart; 11 tests.
- **Gate flow** (`otp_verify_gate_flow_test.dart`, `gate_page_test.dart`) — entitled → dashboard; no
  entitlement / expired → gate with end-date copy; grace → app kept, writes refused; a
  `app_access_required` 403 flips to the gate and a `app_access_read_only` 403 flips to grace
  mid-session; revocation keeps the gym name for the gate copy; the verify call carries the anchor.
- **FCM registration** (`qa_device_token_contract_test.dart`, `device_remote_data_source_test.dart`) —
  POST body `{token, device_id, platform, device_type: "android"}`, upsert documented, delete on logout.
- **Device-only, not verified** — Play install-referrer capture, cold-start app-link handling through an
  installed APK, real FCM delivery, real WATI/SMS deliverability. Requires device/emulator + the real
  providers; deliberately out of this run (deterministic-tests ground rule).

## 7. Recorded end-to-end journey (the deliverable log)

Executed by `backend/tests/test_app_access_rehearsal_log.py` (commit 9fa7086) — run it with
`pytest -s tests/test_app_access_rehearsal_log.py` to reproduce. Verbatim output:

```
[setup] gym A=Hash Fit uuid=b3198c9f-b008-4aad-8286-6b5d2ebcf18e | gym B=Iron Temple
[1 onboarding] 201 completed; invite status=sent channel=whatsapp
[2 invite-resend] non-forced resend → status=already_sent
[3 otp-verify] entitlement=active app.access=YES token granted plan=Monthly
[4a entitlement] today → status=active read_only=False
[4b entitlement] expiry −3d → grace read_only=True write→403 app_access_read_only
[4c entitlement] expiry −8d → status=expired read→403 app_access_required
[4d entitlement] cancelled → status=none (no grace)
[5 isolation] member-2 sees phones=['9876500002'] (only their own row)
[6 multi-tenant] same phone + anchor B → gym=Iron Temple (separate account, separate token)
[6b disambiguation] no anchor → select_gym prompt with ['Hash Fit', 'Iron Temple'] (only tenant-uuid + name exposed)
```

Read: the front desk onboards in one call; the invite goes out as an audit-logged WATI template send
(fake transport) and is deduped on resend; the anchored OTP login yields `app.access` + `active`;
expiry −3 days flips the gate to grace with writes refused on the documented code; −8 days flips to
expired (`app_access_required` on gated reads); cancellation skips grace entirely; a same-gym second
member sees only their own rows; the same phone at another gym is a **different account** resolved by
the anchor, and an anchor-less lookup only ever exposes tenant-uuid + display name.

**Play id, front door:** the invite links target `com.getfitwithus.app` (regression-tested in
`test_app_access_qa_regressions.py`) and the built artifact carries that package — the workflow's
Play target matches the shipped binary.

## 8. Defects found

### QA-DEF-001 — device-token re-registering answers 400 instead of the documented idempotent 200 — **major**

- **Where:** `DeviceTokenSerializer` (plain ModelSerializer) lets DRF's `UniqueValidator` reject an
  already-existing `token` with 400 *“device token with this token already exists.”* before
  `DeviceTokenViewSet.create` reaches its intended `update_or_create` upsert
  (`apps/notifications/device_views.py:60`, docstring: “201 first / 200 re-registered”).
- **Reproduce:** register `{token: "fcm-a-1"}` → 201; POST the same token again → **400** (expected 200,
  per FBOS-011 §7.4 and the mobile client contract `DeviceRemoteDataSource.register`, which the app calls
  on every app start / token event).
- **Impact:** the Flutter service *swallows* the failure (push still works — the first registration's row
  persists), so the user-visible damage is error-log noise and a stale `device_id`/platform if they ever
  change on the same token. Not a blocker; a correctness bug against the documented contract.
- **Handling:** regression test committed **xfail(strict)** in 3269bf0 (`test_registration_is_idempotent_per_token`,
  comment `QA-DEF-001`); product code left untouched. When Forge fixes it, the suite turns red on the
  XPASS until the marker is removed with the fix.
- **Suggested fix shape (for Forge, not done here):** in `DeviceTokenSerializer`, exempt `token` from the
  unique check (e.g. override `validate`/`get_unique_together_validator` behaviour or validate
  uniqueness manually only when `request.method == 'POST'`-and-absent), letting the view's
  `update_or_create` own both paths — plus a test asserting `200` + updated fields on re-register.

### QA-DEF-002 — non-enumeration test was self-comparing (QA-test bug, fixed) — **minor**

`test_step7_unknown_and_known_phone_are_indistinguishable` previously verified the *same* phone in both
legs, so the indistinguishability assertion could never fail. Fixed in 9fa7086: the second leg uses a
never-registered phone; the test still passes, now meaningfully. (No product impact — listing it for
transparency.)

### Brief/doc nits (no code change)

- The endpoint is `GET /auth/entitlement/` and the payload key is `entitlement` — the verification brief's
  `app-access` / `app_access` names don't exist anywhere; FBOS-011 is the authority.
- Invite outcome vocabulary is `sent / skipped / failed / not_applicable / already_sent` + `reason`
  (`wati_not_configured` …) — the brief's "not_configured" status shape is a reason value, not a status.

## 9. Not verified — requires a device / real third-party (explicitly)

- Play install → cold-start deep-link capture (install referrer + App Link through the installed APK).
- Real WATI WhatsApp template send + MSG91 SMS fallback deliverability (faked in all runs).
- Real FCM delivery to the installed app / token rotation on a physical device.
- Play Console acceptance of the AAB (upload itself) — out of bounds per ground rules.

## 10. Release recommendation

**SHIP** — with QA-DEF-001 ticketed, not blocking:

- every automated gate (backend 83 %, frontend 88.58 %, mobile 80.87 % coverage; flake8/eslint/dart
  analyze clean; 1119 + 507 + 480 tests) is green;
- the full member journey, the entitlement matrix, non-enumeration, both gyms' isolation and the AAB
  identity facts are verified on this branch;
- the only open defect degrades gracefully (log noise, no functional loss) and is pinned by a strict-xfail
  regression test so it cannot regress silently.

**Follow-up tickets**

| # | Ticket | Owner | Priority |
| --- | --- | --- | --- |
| 1 | QA-DEF-001: make device-token registration idempotent (serializer `UniqueValidator` vs view upsert); remove the xfail marker in the fix commit | Forge (backend) | High |
| 2 | Device verification pass on a physical device/emulator: install-referrer + cold-start app link, real FCM delivery, token rotation | Swift (mobile) + Deploy | High |
| 3 | Live third-party deliverability rehearsal (WATI template send, MSG91 SMS fallback) against the staging tenant, including the 503 path | Deploy + Forge | High |
| 4 | Update downstream briefs to the real contract names (`/auth/entitlement/`, `entitlement` payload, invite status vocabulary) | Fit (PO) | Low |
| 5 | Thin mobile coverage margin (80.87 % vs the 80 gate): CI only checks lcov non-emptiness — consider a real lcov-parsed gate | Shield | Medium |