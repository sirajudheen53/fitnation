# Play Release Checklist — FitNation Android (`com.getfitwithus.app`)

**Status:** Runbook (live document — tick items per release)
**Date:** 2026-10-21 · **Last verified end-to-end:** AAB built + verified (appId
`com.getfitwithus.app`, targetSdk 36, versionCode 1), `flutter analyze` clean,
`flutter test` 272/272 green, Play API read-only calls confirmed the app shell
exists with no releases and no store listing yet.
**Applies to:** `mobile/` (Flutter), Play developer account "Crackers Club SSC", service account `~/.play-cred/fb-sa.json` (androidpublisher scope — can upload AABs, manage tracks/listings; **cannot create a new app shell**)
**Tooling:** `mobile/tool/build_release.sh` (build+verify) · `tools/play/publish.py` (upload/track/listing) · `tools/play/verify_release.py` (go/no-go) · `.github/workflows/release-mobile.yml` (manual CI) · `mobile/store/play-listing-content.md` (paste copy) · `mobile/RELEASE.md` (release identity)
**Design context:** `docs/fbos-011-app-access-and-invite.md` (§7 mobile, §9 rollout)

> **This file is the single source of truth for the Play release.** Anything about
> the release that is not here does not exist.

---

## 0. One-time setup (before the first upload ever)

### 0.1 App shell — ALREADY CREATED ✅ (verified 2026-10-21 via the Play API)

The Play app shell for `com.getfitwithus.app` **exists**. Verified read-only:
`GET /androidpublisher/v3/applications/com.getfitwithus.app/edits/{id}/tracks`
returns all four tracks (`internal`, `alpha`, `beta`, `production`), while a
bogus package returns `404 "Package not found"`. Current state:

| Item | State |
|---|---|
| App shell | **exists** (tracks endpoint works; no 404) |
| Releases on any track | **none** — `GET /edits/{id}/bundles` returns an empty list |
| Store listing (en-IN) | **missing** — `GET …/listings/en-IN` → `404 "Listing for language 'en-IN' not found."` |
| Listing images | **missing** (no listing → no image slots) |
| App Signing | **not enrolled yet** — happens on the first AAB upload |

So the remaining shell work is **not** "create the app" — it is:
- [ ] Play Console → **App integrity / App signing**: confirm Play App Signing is
      set to the Google-managed key. The **first AAB upload enrolls** the upload
      key (`upload` alias) automatically — nothing to paste, but verify after the
      first upload that the app-signing certificate exists.
- [ ] Play Console → **Internal testing** track: add the pilot testers' emails
      (Hash Fit owner + 6 members' Google accounts + team) — Console UI only,
      see §10.
- [ ] Accept any outstanding declarations (developers policy, US export laws,
      health-apps acknowledgment — see §5) if the Console still asks for them.

> **Package name is immutable** now that the shell exists: `com.getfitwithus.app`
> is locked for the app's lifetime. A typo here is unfixable — verify before upload.

### 0.2 Signing — DONE ✅ (verified 2026-10-21)

The upload key already exists and the release build is wired to it:

| Item | Value |
|---|---|
| Keystore | `mobile/android/app/upload-keystore.jks` (gitignored via `**/*.jks`) |
| Credentials | `mobile/android/key.properties` (gitignored) — `storeFile=app/upload-keystore.jks` (**relative to `mobile/android/`**), `keyAlias=upload` |
| Cert CN | `CN=FitNation Upload, OU=Mobile, O=FitNation, L=Bengaluru, ST=Karnataka, C=IN` |
| Upload-key SHA-256 | `E2:3A:7B:D7:D8:B2:F8:62:15:4C:49:84:3A:42:11:B8:63:94:5E:D6:83:61:37:1B:E4:59:01:3C:B7:C2:86:72` |

- [ ] **Siju: confirm the keystore + passwords are in the team secret manager.** The
      keystore lives only on this machine and in CI. Losing it with Play App
      Signing disabled is an unrecoverable incident (Play can reset an *upload*
      key via support, but the app-signing key is Google-managed — keep the
      default Google-managed signing key so a reset is possible).
- [x] `android/app/build.gradle.kts` creates the `upload` signing config from
      `key.properties` and **throws `GradleException` on any release build that
      lacks the material** — it never falls back to debug keys. Verified:
      "Release build refused: mobile/android/key.properties (upload-key signing
      material) is missing…" (exit 1).
- [ ] First AAB upload **enrolls Play App Signing** automatically (Play keeps the
      app-signing key; the `.jks` stays the upload key). Leave the
      "Google-managed signing key" at its default — do NOT switch to
      "Play-managed" upload keys (that would break the CI keystore path).
- [x] Upload-key SHA-1 — store it for App Links `assetlinks.json` + Firebase:
      ```bash
      keytool -list -v -keystore mobile/android/app/upload-keystore.jks -alias upload -storepass "$STORE_PASS" | grep -E 'SHA1|SHA256'
      ```

### 0.3 Package rename — DONE ✅
- [x] `android/app/build.gradle.kts`: `namespace` + `applicationId` = `com.getfitwithus.app`.
- [x] Verified in the built AAB: `package="com.getfitwithus.app"`.
- [ ] **Do not change the package name after the first upload** — it is immutable.

### 0.4 API-level floor — DONE ✅
- [x] `android/app/build.gradle.kts` pins `targetSdk = 36` explicitly (Play's
      floor for new apps), independent of what Flutter's tooling defaults to.
- [x] Verified in the built AAB: `minSdkVersion="24"`, `targetSdkVersion="36"`,
      `compileSdkVersion="36"`.

---

## 1. Version policy

- `mobile/pubspec.yaml` → `version: MAJOR.MINOR.PATCH+BUILD`, e.g. `1.0.0+5`. `BUILD` is the Play `versionCode` and must **strictly increase** forever.
- Bump rules:
  - `PATCH+1` — any release (default increment per release PR).
  - `MINOR` — new user-visible feature block (gate, deep links, FCM).
  - `MAJOR` — reserved; don't expect it soon.
- The release PR bumps `pubspec.yaml`; CI/build script asserts `versionCode` > the last uploaded one (`git log` or Play API check) — a reused versionCode is rejected by Play and wastes a review cycle.

---

## 2. Build the AAB

**One command — `mobile/tool/build_release.sh`** (pinned toolchain, fail-loud
signing gate, post-build verification, no debug-key fallback):

```bash
# from the repo root
mobile/tool/build_release.sh                 # analyze → test → build → verify
mobile/tool/build_release.sh --skip-checks   # skip analyze+test (CI runs them separately)
mobile/tool/build_release.sh --clean         # flutter clean first
```

It pins Flutter 3.47.1 + JDK 17 + the Android SDK, builds with
`--dart-define=SERVER=prod`, and then **verifies the produced AAB** with
`bundletool` (applicationId, versionCode, versionName, minSdk, targetSdk ≥ 36)
and `keytool` (the cert must be the **upload** cert, never a debug one).

Verified output of the 1.0.0+1 build (2026-10-21):

```
════════════ RELEASE AAB READY ════════════
  path        : mobile/build/app/outputs/bundle/release/app-release.aab
  size        : 54M   (55 572 810 bytes)
  versionCode : 1    versionName: 1.0.0
  appId       : com.getfitwithus.app
  minSdk      : 24    targetSdk: 36
  cert CN     : CN=FitNation Upload, OU=Mobile, O=FitNation, L=Bengaluru, ST=Karnataka, C=IN
  cert SHA256 : E2:3A:7B:D7:D8:B2:F8:62:15:4C:49:84:3A:42:11:B8:63:94:5E:D6:83:61:37:1B:E4:59:01:3C:B7:C2:86:72
```

### Independent verification (re-run this before every upload)

```bash
cd mobile
java -jar /tmp/bundletool.jar dump manifest --bundle=build/app/outputs/bundle/release/app-release.aab
java -jar /tmp/bundletool.jar validate --bundle=build/app/outputs/bundle/release/app-release.aab
unzip -p build/app/outputs/bundle/release/app-release.aab "META-INF/*.RSA" | keytool -printcert
```

```
<manifest … android:compileSdkVersion="36" android:versionCode="1"
          android:versionName="1.0.0" package="com.getfitwithus.app" …>
  <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="36"/>
```

- [x] `applicationId` = `com.getfitwithus.app`
- [x] `targetSdkVersion` = 36 (Play's floor for new apps) · `minSdkVersion` = 24
- [x] `versionCode` = 1 = the `+1` in `mobile/pubspec.yaml` (single source of truth)
- [x] Signed with the **upload** key (`META-INF/UPLOAD.RSA`, SHA-256 matches the
      upload keystore) — **not** the debug certificate
- [x] `flutter analyze` → *No issues found* · `flutter test` → *272 tests, all passed*
- [ ] Verify the API host baked in is `https://api.yougetfitwithus.com` (`SERVER=prod`).
- [ ] Smoke the release build on a device before upload (`flutter run --release --dart-define=SERVER=prod`) — OTP request → code arrives (WATI/SMS, not console) → login.

---

## 3. Upload + track + staged rollout

**A. API (scriptable — `tools/play/publish.py`)** — one atomic edit: upload AAB →
set track → listing → images → `:commit`. If anything fails mid-way the edit is
**discarded, so nothing is published** (Play's edit model gives us that for free).

```bash
# read-only: what do the tracks look like right now?
tools/play/publish.py tracks

# dry-run first (no network calls at all) — ALWAYS do this
tools/play/publish.py release \
  --aab mobile/build/app/outputs/bundle/release/app-release.aab \
  --track internal --status completed \
  --listing-content mobile/store/play-listing-content.md \
  --store-dir mobile/store --dry-run

# the real thing (orchestrator/Siju only — never from a side branch)
tools/play/publish.py release \
  --aab mobile/build/app/outputs/bundle/release/app-release.aab \
  --track internal --status completed \
  --listing-content mobile/store/play-listing-content.md \
  --store-dir mobile/store

# go/no-go report (read-only; exits 0 = GO, 1 = NO-GO)
tools/play/verify_release.py --expect-track internal
```

Raw endpoints the tool uses (for reference / debugging):

```
POST https://androidpublisher.googleapis.com/androidpublisher/v3/applications/com.getfitwithus.app/edits
POST …/edits/{editId}/bundles?uploadType=media            (raw AAB bytes, application/octet-stream)
POST …/edits/{editId}/tracks/{internal|alpha|beta|production}
POST …/edits/{editId}/listings/en-IN
POST …/edits/{editId}:commit                              (the COLON syntax — not /commit)
```

- [ ] **Staged rollout** to production: `--track production --status inProgress --rollout 10`
      (then `--rollout 50`, then `--rollout 100` / `--status completed`).
      `--rollout` is only valid with `--status inProgress`.
- [ ] Service-account access: Play Console → Users & permissions → the SA needs
      **App access → "View app information…", "Create and publish…" releases to
      testing tracks**, and after the health declarations: **"Manage testing
      tracks and edit tester lists"**.

**B. Console UI:** Internal testing → Create new release → upload AAB → release
notes (§7 template) → Save → Review release → Start rollout to Internal.

- [ ] Testers opt in via the internal-track link; install; run the **pilot acceptance** (§10).
- [ ] Promote Internal → **Closed testing** (pilot cohort) → review for a week of real use → **Production**, starting with a **staged rollout 10% → 50% → 100%**. Production review for a new health app can take longer (days) — don't promise dates.

---

## 4. Store listing (Pricing & distribution → Main store listing)

**The paste-ready copy lives in `mobile/store/play-listing-content.md`** — the
Console UI stays a human step, but the *text* to paste is version-controlled
and machine-checked. The asset→slot map is in `mobile/store/README.md`.

| Asset | Requirement | Notes |
|---|---|---|
| App name | ≤ 30 chars | `FitNation: Gym, Workouts, Diet` (exactly 30 — the em-dash variants are 31/32 and **rejected**) |
| Short description | ≤ 80 chars | `Workouts, diet plans, check-in QR & progress — your gym in your pocket.` (71) |
| Full description | ≤ 4000 chars | 1843 chars, plain text — mentions OTP login ("your phone number is your login"), no password ever |
| App icon | 512×512 PNG, ≤ 1 MB | `mobile/store/app-icon-512.png` — no alpha for the legacy icon slot |
| Feature graphic | 1024×500 JPG/PNG, no alpha | `mobile/store/feature-graphic-1024x500.png` |
| Phone screenshots | ≥ 2, 16:9 or 9:16, min 320 px | **NOT PRODUCED** — needs a device pass; shot list in `mobile/store/README.md` |
| Categories | App; **Health & Fitness** | triggers §5 |
| Privacy policy URL | **required** | `https://yougetfitwithus.com/privacy` (Siju hosts; blocker for review) |
| Account deletion | **required** (app creates accounts) | URL pointing at the deletion flow (FBOS-011 B8 + in-app entry, M5) |
| Content rating | questionnaire | no user-generated content sharing between users in v1 → likely Everyone/3+; answer photos question honestly (progress photos are private to the user) |
| Ads | contains ads: **No**; purchase content? No (membership is bought at the gym) | |
| Data safety | §6 | |
| Target audience | 18+ (gym members); not child-directed | avoids Families-policy surface |
| News app? Government app? | No / No | |

- [ ] The listing can be uploaded by API instead of pasted — see §3:
      `tools/play/publish.py listing --listing-content mobile/store/play-listing-content.md`
      and `tools/play/publish.py assets --store-dir mobile/store`. The Console
      paste is still available and is the human step the orchestrator owns.

---

## 5. Health apps declaration (mandatory — app stores health profile, body measurements, progress photos)

Play Console → App content → **Health apps**:
- [ ] "Does your app contain Health features?" → **Yes**.
- [ ] Category: **Fitness & wellness** (not medical — nothing in the app diagnoses/treats; BMI display is informational).
- [ ] Declare the health data the app transmits/collects: health profile (height, weight, BMI, injuries, medical info), body measurements, progress photos.
- [ ] Confirm the app does **not** use the data for medical advice, diagnosis, or treatment; add the standard "consult your physician" line to the full description and the in-app consent screen (FBOS-011 §10.5).
- [ ] This declaration puts the app under Play's Health policies review — expect reviewer questions; keep answers consistent with §6.

---

## 6. Data Safety form (App content → Data safety)

Collected (defined as: transmitted off the device), all **encrypted in transit**, deletion offered:

| Data type | Collected | Purpose | Optional? | Deletable |
|---|---|---|---|---|
| Personal info — Name | Yes | App functionality (profile) | No | Yes |
| Personal info — Phone number | Yes | App functionality (**account creation / OTP login**) | No | Yes |
| Personal info — Email address | Optional | Account management | Yes | Yes |
| Health & fitness — Fitness info (height/weight/BMI, measurements, injuries/medical notes) | Yes | App functionality (coaching features) | Yes | Yes |
| Photos — Progress photos | Yes | App functionality (progress tracking) | Yes | Yes |
| App activity — Workout/meal logs | Yes | App functionality | Yes | Yes |
| App info & performance — Crash logs / device ID (FCM token) | Yes | Analytics / messaging | No | Yes |

- [ ] All rows: **collected**, **encrypted in transit = yes**, **users can request deletion = yes** (the B8 endpoint is the mechanism — say so in the privacy policy).
- [ ] "Data is shared with third parties": **No** (Razorpay/payments are gym-desk side; WATI/SMS process phone numbers for delivery — if flagged as service providers, answer per Play's service-provider exemption guidance; keep the privacy policy consistent).

---

## 7. Review notes template (paste into "App access" / notes for the reviewer)

**The review account needs a REAL phone number and an ACTIVE membership** —
there is no bypass. The OTP must actually arrive on a device the team
controls, because the reviewer is a person with a real phone. A number that
nobody answers means a rejected review.

```
FitNation is a gym-membership app. Login is passwordless:
1. Open the app → enter any mobile number → tap "Get OTP".
2. The 6-digit OTP arrives by WhatsApp/SMS at that number within seconds.
3. Enter the OTP → you are signed in.

For review purposes, please use this pre-provisioned demo membership:
  Phone: +91 <DEMO_PHONE>        (a device the team monitors during the review)
  Gym:   Hash Fit (demo tenant)

If OTP delivery is delayed, tap "Resend OTP" after 60 seconds.

Features behind the login: workout/diet plans, attendance check-in (QR),
progress photos, body measurements. A demo account with sample data is
preloaded so features are explorable immediately.

Account deletion: Profile → Delete account (also at <DELETION_URL>).
Contact: <SUPPORT_EMAIL> — we respond within 24 h.
```

**How to get a working test OTP (before submitting for review):**

1. Pick a real Indian mobile number on a SIM the team controls (a WATI
   WhatsApp number works — the OTP is delivered on WhatsApp/SMS).
2. Create/confirm the demo member in the **Hash Fit** tenant backend with
   that number and an **active membership plan** (`includes_app_access`).
   Without the membership the reviewer hits the entitlement wall and cannot
   explore anything.
3. Send a test OTP end-to-end from a device: enter the number → "Get OTP" →
   confirm the code lands → log in → land on a populated dashboard. Screenshot
   it; that is your evidence the review account works.
4. Keep that SIM **active and monitored for the whole review window** — the
   reviewer may ask for a fresh OTP, and a dead number = a rejected review.
5. Record the exact number + gym + the OTP delivery channel in the release PR.

- [ ] Fill the placeholders (`<DEMO_PHONE>`, `<DELETION_URL>`, `<SUPPORT_EMAIL>`).
- [ ] The demo phone is a line the team monitors during the review window.
- [ ] The demo membership is **active** and points at the **Hash Fit** tenant.
- [ ] Do **not** mention internal tracks or staging hosts in the notes.

---

## 8. Rollback path

1. **Feature-level (preferred — no Play latency):** the gate is server-driven. Kill the incident with the tenant flag `tenant.features["app_access"] = false` (revokes `app.access`, invites stop) or `includes_app_access` on the offending plan. Mobile builds keep working in legacy mode — that's the point of the flag design.
2. **Build-level:** Production → Releases → **Halt staged rollout** (stops new %, keeps existing installs). Upload the previous `versionCode` as a new release versionCode (you cannot "un-publish" a versionCode; you ship a revert build with `versionCode+1` and reverted code).
3. **Track-level quarantine:** if a bad AAB is only on internal/closed, just upload the fixed AAB over the track.
4. **Backend API compatibility:** mobile releases must tolerate a backend that lacks the newest fields (protobuf-style tolerance: missing `entitlement` ⇒ treat as legacy). Never deploy a backend breaking the *current* Play build; the rollout ladder is backend → frontend → mobile (FBOS-011 §9.1).
5. Post-incident: the revert AAB follows this checklist from §2 (new versionCode, full test pass).

---

## 9. Per-release quick list (copy into the release PR)

- [ ] `pubspec.yaml` version bumped (`+N` strict increase)
- [ ] `flutter analyze` clean; `flutter test` green; integration test OTP→gate green
- [ ] AAB built with `mobile/tool/build_release.sh` (signed with the **upload** key; the script verifies appId/targetSdk/versionCode and refuses a debug cert)
- [ ] Smoke on device: OTP arrives via WhatsApp/SMS (never console), login, gate states correct
- [ ] Release notes drafted (§7 template, short form)
- [ ] `tools/play/publish.py release --dry-run` output reviewed
- [ ] Uploaded to internal → smoke → promote; production via staged rollout
- [ ] After rollout: watch `NotificationLog` (otp/app_invite failures) and backend error rates for 24 h

---

## 10. Internal testing + pilot plan (Hash Fit cohort)

**Pilot:** tenant **"Hash Fit"** (first tenant, 6 members) as the internal-test
cohort, plus the team accounts.

### 10.1 Tester list — Console UI only (human step, cannot be automated)

The service account **can** manage tracks, but the tester list itself is a
Console-UI action. The Play API's tester-list endpoints require permissions
that the app-scoped SA does not reliably hold — treat it as human-only.

- [ ] Play Console → **Testing → Internal testing → Testers → Manage testers**
- [ ] Add the pilot Google accounts (Hash Fit owner + the 6 members) — one
      `@gmail.com`/`@googlemail.com` address per tester, **not** a Google Group
      (groups expand to every member, including non-pilots).
- [ ] Copy the **"Copy link" / opt-in URL** and send it to each tester on WhatsApp
      — a tester must **accept the invitation and opt in** before the build is
      installable. This is the single most common reason "the Play link 404s".
- [ ] The tester must use the **same Google account** that was added to the list.
- [ ] Keep a copy of the opt-in URL in the runbook — it changes per track.

### 10.2 Per-member walkthrough (the pilot acceptance test)

Each of the 6 Hash Fit members walks this end-to-end. **Every step must be
verified on a real device** — the gym anchor is the whole point of the deep
link, and it is invisible in the Console.

| # | Step | What must happen | Pass criterion |
|---|---|---|---|
| 1 | Install | Opt in via the Play link → install from Play | App launches, no crash, splash ok |
| 2 | Open the invite link | Member taps the WhatsApp invite (gym-anchored deep link) | App opens **already bound to Hash Fit** — the gym code is captured from the link, not typed |
| 3 | OTP | Phone number → "Get OTP" | OTP arrives on WhatsApp/SMS within seconds; wrong codes rejected |
| 4 | Entitlement | Active Hash Fit membership | Gate **passes** → dashboard loads (no "ask your gym" wall) |
| 5 | Dashboard | Home screen | Gym name = "Hash Fit"; plan/next-class/streak widgets render |
| 6 | Negative gate | A member **without** an active plan (or after the gym revokes access) | App shows the locked state with a clear "ask your gym" message — **not** a crash or a blank screen |

- [ ] Record the result per member (pass/fail + device + Android version) in the
      release PR. A failure here is a **release blocker**, not a follow-up.
- [ ] Pay attention to step 2: if the app opens on a blank/tenant-less screen,
      the deep link did not carry the gym anchor — that breaks the WhatsApp
      invite flow for every real member, not just the pilot.

### 10.3 Verification tooling

```bash
# read-only go/no-go summary of the current Play state
tools/play/verify_release.py --expect-track internal
# → versionCode, track, release status, rollout %, listing + image presence,
#   and the public store URL if production is live
```

---

## 11. CI: mobile release workflow

`.github/workflows/release-mobile.yml` — **manual only** (`workflow_dispatch`),
never push-triggered. It runs the same `mobile/tool/build_release.sh` and
`tools/play/publish.py` the local path uses, so CI and local cannot drift.

- [ ] Add the repo secrets (Settings → Secrets and variables → Actions):

  | Secret | Value |
  |---|---|
  | `PLAY_SERVICE_ACCOUNT_JSON` | **full raw content** of the Play SA JSON (`androidpublisher` scope, with app access for `com.getfitwithus.app`) |
  | `KEYSTORE_BASE64` | `base64 -w0 mobile/android/app/upload-keystore.jks` (single line) |
  | `KEYSTORE_PASSWORD` | `storePassword` from `mobile/android/key.properties` |
  | `KEY_ALIAS` | `upload` |
  | `KEY_PASSWORD` | `keyPassword` from `mobile/android/key.properties` |

  The workflow **fails immediately** with `::error title=Missing secret::` if any
  of the five is unset — it never falls back to debug signing and never uploads
  a half-built AAB.
- [ ] The SA JSON is written to a temp file (`/tmp/play-sa.json`) and deleted in
  an `if: always()` cleanup step. It is never committed and never printed.
- [ ] The existing `ci.yml` workflow is **unchanged** — the mobile release is a
      separate, manual workflow.

---

## 12. Known Play constraints (these bit us before — read before you publish)

1. **Target API 36+ for new apps.** Play rejects a new app whose `targetSdkVersion`
   is below 36. We pin `targetSdk = 36` in `android/app/build.gradle.kts` so the
   floor does not drift when Flutter's defaults change.
2. **First-build propagation lag.** After the very first upload to a
   brand-new app, Play can take **hours** (sometimes longer) to make that
   versionCode installable and visible on the internal track. A 404/"not
   available" right after the first upload is usually *propagation*, not a
   broken build. Verify with `tools/play/publish.py tracks` (it shows the
   release even while the installer link is not ready) and wait.
3. **"Item not found" (404) — two different causes, opposite fixes:**
   - `Package not found: <pkg>` → the **app shell does not exist** for that
     package name. Fix: create the app in the Console. (Not our case — our
     shell exists.)
   - `Listing for language 'en-IN' not found` → the **store listing** for that
     locale was never created. Fix: create/paste the listing (§4). This is our
     current state.
   - `Version code X not found` → the versionCode is not on the track yet
     (propagation, or the track was never pointed at it). Fix: re-read the
     tracks; do not re-upload the same versionCode.
4. **Play Console account ≠ browser account.** The Play Console and the
   tester opt-in page use **Google accounts**, and testers routinely sign in
   with a *different* Google account than the one added to the tester list
   (personal vs. work account). The symptom: "you're not a tester" / the
   opt-in page refuses. Fix: add **every** account the testers might use, and
   have them confirm *which* account they are signed in with.
5. **The service account cannot create an app shell.** A 404 on
   `POST /edits` for a never-created package is expected — the shell is a
   Console-only action. (It also cannot manage tester lists reliably — §10.1.)
6. **Play listing text is PLAIN TEXT.** The Console does not render markdown:
   `**bold**` is published with literal asterisks. `tools/play/publish.py`
   refuses to upload a listing containing markdown markers.
7. **versionCode is immutable and strictly increasing.** Play never lets you
   reuse a versionCode, and you cannot un-publish one — a rollback is a *new*
   build with `versionCode+1` (§8).
8. **Screenshots must be real.** Play rejects composited/fabricated
   screenshots, and this project forbids faking them. The pilot devices
   (§10.2) are the opportunity to capture them — see the shot list in
   `mobile/store/README.md`.
9. **Health apps declaration triggers extra review.** Declaring health features
   (§5) puts the app under Play's Health policies review, which can ask
   follow-up questions. Answer consistently with the Data Safety form (§6) —
   contradicting the two is a common rejection cause.
