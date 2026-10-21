# Play Release Checklist — FitNation Android (`com.fitnation.app`)

**Status:** Runbook (live document — tick items per release)
**Date:** 2026-10-21
**Applies to:** `mobile/` (Flutter), Play developer account "Crackers Club SSC", service account `~/.play-cred/fb-sa.json` (androidpublisher scope — can upload AABs, manage tracks/listings; **cannot create a new app shell**)
**Design context:** `docs/fbos-011-app-access-and-invite.md` (§7 mobile, §9 rollout)

---

## 0. One-time setup (before the first upload ever)

### 0.1 App shell (Play Console UI — Siju; the service account cannot do this)
- [ ] Play Console → **Create app**: name `FitNation — Gym, Workouts & Diet`, default language en-IN, **App** (not game), **Free**.
- [ ] Accept the declarations (developers policy, US export laws, health-apps acknowledgment — see §5).
- [ ] Note the **package name you're about to commit to**: `com.fitnation.app`. It is **immutable** for the app's lifetime.
- [ ] Create the **Internal testing** track; add the pilot testers' emails (Hash Fit owner + 6 members' Google accounts + team).

### 0.2 Signing (do this BEFORE the shell accepts an AAB — the first upload sets the course)
- [ ] Generate the upload keystore (keep on this machine + one cold backup; **Siju owns the backup** — losing it with Play App Signing disabled is unrecoverable):
  ```bash
  keytool -genkeypair -v -keystore ~/keys/fitnation-upload.jks \
    -alias fitnation_upload -keyalg RSA -keysize 4096 -validity 10000
  ```
- [ ] `mobile/android/key.properties` (gitignored — verify `.gitignore`):
  ```properties
  storePassword=…        # from the team password manager, not plaintext chat
  keyPassword=…
  keyAlias=fitnation_upload
  storeFile=/home/<user>/keys/fitnation-upload.jks
  ```
- [ ] `android/app/build.gradle.kts` — replace the debug-signing placeholder (current release build signs with DEBUG keys, `build.gradle.kts:32-35`):
  ```kotlin
  import java.util.Properties
  val keystoreProps = Properties().apply {
      val f = rootProject.file("key.properties")
      if (f.exists()) f.inputStream().use { load(it) }
  }
  android {
      signingConfigs {
          create("release") {
              if (keystoreProps.isNotEmpty()) {
                  storeFile = file(keystoreProps["storeFile"]!!)
                  storePassword = keystoreProps["storePassword"] as String
                  keyAlias = keystoreProps["keyAlias"] as String
                  keyPassword = keystoreProps["keyPassword"] as String
              }
          }
      }
      buildTypes {
          release {
              signingConfig = if (keystoreProps.isNotEmpty())
                  signingConfigs.getByName("release") else signingConfigs.getByName("debug")
          }
      }
  }
  ```
- [ ] First AAB upload **enrolls Play App Signing** (Play keeps the app signing key; the `.jks` stays the upload key). Leave "Google-managed signing key" at its default.
- [ ] Store the upload-key SHA-1 where the team can find it (needed later for App Links `assetlinks.json` and Firebase):
  ```bash
  keytool -list -v -keystore ~/keys/fitnation-upload.jks -alias fitnation_upload | grep SHA
  ```

### 0.3 Package rename (must land before the shell is created)
- [ ] `android/app/build.gradle.kts`: `namespace` + `applicationId` → `com.fitnation.app` (from `com.fitnation.fitnation_app`).
- [ ] Move `android/app/src/main/kotlin/com/fitnation/fitnation_app/` → `…/com/fitnation/app/`; update the `package` line in `MainActivity.kt`.
- [ ] App unpublished → no migration concerns. After publication this rename becomes impossible; do not merge it after first upload.

### 0.4 API-level floor
- [ ] New Play apps must target **API 36+**. Check what `flutter.targetSdkVersion` resolves to (`flutter --version` → tooling version) and **override explicitly** if lower:
  ```kotlin
  defaultConfig { targetSdk = 36 }   // only if flutter's default < 36
  ```
- [ ] Confirm `flutter build appbundle --release` produces no target-SDK lint warnings.

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

```bash
cd mobile
flutter clean
flutter pub get
flutter test                                  # AGENTS.md: green tests gate the build
flutter build appbundle --release \
  --dart-define=SERVER=prod
# anchor is runtime-resolved (deep link / referrer / gym code) — no GYM_ANCHOR define for store builds
```

- [ ] Output: `build/app/outputs/bundle/release/app-release.aab`.
- [ ] Verify signing: `jarsigner -verify build/app/outputs/bundle/release/app-release.aab` → "jar verified" with the **upload** alias (not debug).
- [ ] Verify the API host baked in is `https://api.yougetfitwithus.com` (`SERVER=prod` — after the FBOS-011 fix that actually wires `SERVER` into the Dio client).
- [ ] Smoke the release build on a device before upload (`flutter run --release --dart-define=SERVER=prod`) — OTP request → code arrives (WATI/SMS, not console) → login.

---

## 3. Upload + track + staged rollout

Two equivalent paths; the service account covers both.

**A. API (scriptable — same pattern as the existing helpers in `~/.play-cred/`, which currently drive a different package):**
- [ ] Point the edit at package `com.fitnation.app`; upload the AAB to the **internal** track:
  ```
  POST https://androidpublisher.googleapis.com/androidpublisher/v3/applications/com.fitnation.app/edits/{editId}/bundles
  POST …/edits/{editId}/tracks/internal   (versionCodes: [<new>], stagedRollout off)
  POST …/edits/{editId}:commit
  ```
- [ ] Service-account access: Play Console → Users & permissions → the SA needs **App access → "View app information…", "Create and publish…" releases to testing tracks**, and after the health declarations: **"Manage testing tracks and edit tester lists"**.

**B. Console UI:** Internal testing → Create new release → upload AAB → release notes (§7 template) → Save → Review release → Start rollout to Internal.

- [ ] Testers opt in via the internal-track link; install; run the **pilot acceptance** (FBOS-011 §9.3): invite → install via link (anchor captured) → OTP login → entitlement gate states.
- [ ] Promote Internal → **Closed testing** (pilot cohort) → review for a week of real use → **Production**, starting with a **staged rollout 10% → 50% → 100%**. Production review for a new health app can take longer (days) — don't promise dates.

---

## 4. Store listing (Pricing & distribution → Main store listing)

| Asset | Requirement | Notes |
|---|---|---|
| App name | ≤ 30 chars | `FitNation — Gym, Workouts & Diet` |
| Short description | ≤ 80 chars | e.g. `Workouts, diet plans, check-in QR & progress — your gym in your pocket.` |
| Full description | ≤ 4000 chars | Mention OTP login ("your phone number is your login"), no password ever |
| App icon | 512×512 PNG, ≤ 1 MB | no alpha for the legacy icon slot |
| Feature graphic | 1024×500 JPG/PNG, no alpha | |
| Phone screenshots | ≥ 2, 16:9 or 9:16, min 320 px | dashboard, workout detail, QR check-in, progress |
| Categories | App; **Health & Fitness** | triggers §5 |
| Privacy policy URL | **required** | `https://yougetfitwithus.com/privacy` (Siju hosts; blocker for review) |
| Account deletion | **required** (app creates accounts) | URL pointing at the deletion flow (FBOS-011 B8 + in-app entry, M5) |
| Content rating | questionnaire | no user-generated content sharing between users in v1 → likely Everyone/3+; answer photos question honestly (progress photos are private to the user) |
| Ads | contains ads: **No**; purchase content? No (membership is bought at the gym) | |
| Data safety | §6 | |
| Target audience | 18+ (gym members); not child-directed | avoids Families-policy surface |
| News app? Government app? | No / No | |

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

```
FitNation is a gym-membership app. Login is passwordless:
1. Open the app → enter any mobile number → tap "Get OTP".
2. The 6-digit OTP arrives by WhatsApp/SMS at that number within seconds.
3. Enter the OTP → you are signed in.

For review purposes, please use this pre-provisioned demo membership:
  Phone: +91 XXXXXXXXXX        (a device you control receives the OTP)
  Gym:   Hash Fit (demo tenant)

If OTP delivery is delayed, tap "Resend OTP" after 60 seconds.

Features behind the login: workout/diet plans, attendance check-in (QR),
progress photos, body measurements. A demo account with sample data is
preloaded so features are explorable immediately.

Account deletion: Profile → Delete account (also at <deletion URL>).
Contact: <support email> — we respond within 24 h.
```

- [ ] Fill the placeholders; the demo phone must be a line the team monitors during the review window.
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
- [ ] `flutter test` green; integration test OTP→gate green
- [ ] AAB built with `--dart-define=SERVER=prod`, signed with the **upload** key (verify with `jarsigner -verify`)
- [ ] Smoke on device: OTP arrives via WhatsApp/SMS (never console), login, gate states correct
- [ ] Release notes drafted (§7 template, short form)
- [ ] Uploaded to internal → smoke → promote; production via staged rollout
- [ ] After rollout: watch `NotificationLog` (otp/app_invite failures) and backend error rates for 24 h
