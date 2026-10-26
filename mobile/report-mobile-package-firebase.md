# Mobile: package + Firebase convergence & WhatsApp zero-tap OTP — report

Date: 2026-10-25 (evening IST) · Repo: `sirajudheen53/fitnation-mobile` (`main`) ·
Commits: `be14c8d` (identity convergence) + `d0bd254` (zero-tap receiver).
Per Siju order msg 3088 (22:22 IST): converge the app on the RELEASED package
`com.getfitwithus.app` + the WhatsApp zero-tap OTP receiver in one release.

## 1. google-services.json — config source

`android/app/google-services.json` previously held captured CLI error text
("Failed to get ANDROID app configuration") from an earlier failed fetch; the
last committed version was the pre-convergence config (deleted app
`com.fitnation.fitnation_app` + `com.getfitwithus.biodebug`).

- **Primary path** — `GET /v1beta1/projects/yougetfitwithus/androidApps/1:35318880783:android:aa2ecfa5999e006359a17a/getConfig`
  with bearer `gcloud auth print-access-token` + `X-Goog-User-Project: yougetfitwithus`:
  returned **404 for ~12 minutes** (20 retries / 30 s apart) — the brand-new app
  propagated slowly, as expected.
- **Fallback path (used)** — `firebase apps:sdkconfig ANDROID
  1:35318880783:android:aa2ecfa5999e006359a17a --project yougetfitwithus`
  (signed-in as siraju.ka@gmail.com). First call succeeded; the backend was then
  flaky for a few calls (400 while the `projects/-` index caught up, then 200s).
  The base64 `configFileContents` from the raw API response was decoded and
  written byte-for-byte.
- **Validation before write**: `project_info.project_id == yougetfitwithus` ✓,
  client package set == {`com.getfitwithus.app`, `com.getfitwithus.biodebug`} ✓,
  `mobilesdk_app_id == 1:35318880783:android:aa2ecfa5999e006359a17a` ✓. The
  config is now tracked in git (private repo).
- `lib/firebase_options.dart`: Android `appId` swapped from the deleted
  registration (`…be7078e037bcf7ce59a17a`) to the released one
  (`…aa2ecfa5999e006359a17a`). API key unchanged (same project-level key).

## 2. Package rename — diff summary

| File | Change |
|---|---|
| `android/app/build.gradle.kts` | `namespace` + `applicationId` → `com.getfitwithus.app` |
| `MainActivity.kt` | moved `kotlin/com/fitnation/fitnation_app/` → `kotlin/com/getfitwithus/app/`, package statement updated (git mv, history preserved) |
| `lib/firebase_options.dart` | Android appId swap (see above) |

Verified end-to-end on the built APK (`aapt2 dump badging`):
`package: name='com.getfitwithus.app'`, minSdk 24 / targetSdk 36. No
`com.fitnation` references remain anywhere under `android/`. Deliberately
**unchanged** (branding, not package identity): the launcher label
`android:label="fitnation_app"` and the Dart import root `package:fitnation_app/…`
— renaming those is a product/branding decision, not part of this convergence.

## 3. WhatsApp zero-tap OTP receiver — wiring

Meta's CURRENT flow (the PendingIntent handshake is deprecated; the OTP Android
SDK is the migration path). API verified against the actual SDK sources
(`com.whatsapp.otp:whatsapp-otp-android-sdk:1.0.0`, Maven Central, released
2026-03-26), not just the doc page.

- **Native (Kotlin, `com.getfitwithus.app.otp`)**
  - `WhatsAppOtpCodeReceiver` — manifest-registered, `exported=true`, intent
    filter `com.whatsapp.otp.OTP_RETRIEVED`. Validates the broadcast with
    `WhatsAppOtpIncomingIntentHandler.processOtpCode()` against the stored
    handshake id (`request_id` extra); valid codes go to the bus, mismatches are
    logged and dropped.
  - `WhatsAppOtpBus` — process-wide handshake id + latest-code buffer (late
    subscriber after screen navigation still gets the code). Pure JVM → JUnit
    tested (5 tests, no Robolectric).
  - `WhatsAppOtpChannels` — MethodChannel `com.getfitwithus.app/whatsapp_otp`
    (`startHandshake` → `WhatsAppOtpHandler().sendOtpIntentToWhatsApp()`,
    `isHandshakeSupported`) + EventChannel `…/events` for code broadcasts.
  - Manifest: `<queries>` for `com.whatsapp` / `com.whatsapp.w4b` (package
    visibility for handshake probing).
- **Dart**
  - `WhatsAppOtpService` — Android-only, error-degrading (unsupported platform /
    missing plugin / channel errors never throw; manual entry keeps working).
  - Handshake fires in the **backend-OTP branch only**, immediately before each
    `/api/v1/auth/otp/request/` call (phone-input submit + resend), because
    WhatsApp honours zero-tap only within the handshake window. The Firebase
    branch is untouched.
  - `OtpVerifyScreen` listens for broadcasts: digits are spread across the 6
    boxes and verified through the **existing** backend verify call
    (`/api/v1/auth/otp/verify/`) — identical to manual submission. Payloads
    without exactly 6 digits are ignored (manual entry remains the fallback).
  - The backend HTTP OTP chain (template `fitnation_otp`,
    `GUPSHUP_OTP_PARAM_MODE=code_once`, refs #86) is not modified; the
    zero-tap template side (button + package `com.getfitwithus.app` + signature
    hash `csMKq3/km+M`) lives server-side as agreed.
- **Incidental but necessary fix** (`lib/router/app_router.dart`): the router
  provider watched the whole auth state, so the loading toggles of every backend
  OTP request re-created the GoRouter and bounced the app back to the phone
  screen before the OTP screen could open. It now only re-creates on an
  authentication flip. Pre-existing backend-mode bug, surfaced by the new
  handshake-ordering tests; firebase-mode behaviour unchanged.

## 4. Verification

| Check | Result |
|---|---|
| `dart analyze` | clean (0 issues) |
| `flutter test --coverage` | 133 passed, 0 failed · 90.3% line coverage (floor 80%) |
| `flutter build apk --debug` | ✓ 113 s; APK badging confirms package + receiver + queries |
| `./gradlew :app:testDebugUnitTest` | 5/5 bus tests pass |
| CI-parity fresh clone (`~/.local/opt/flutter` 3.47.8 = CI stable) | analyze clean, 133/133 pass |
| New tests | service channel mocks (12), zero-tap auto-fill widget tests (2), backend-mode handshake-ordering tests (2), Kotlin bus tests (5) |

Pushed `main` (`dd5b838..d0bd254`) — direct push per repo convention.

## 5. Ticket attempt outcome

`gh issue create -R sirajudheen53/fitnation --body-file
.zcode/ticket-firebase-convergence.md` **failed again with HTTP 401** — the
gh keychain token for sirajudheen53 is invalid and no `GH_TOKEN`/`GITHUB_TOKEN`
exists on this host (memory: 2026-10-25). Unauthenticated curl cannot create
issues. **Manual step:** re-run `gh auth login -h github.com`, then create the
issue from the staged body file. (Push itself worked over SSH.)

## 6. Leftover manual steps

1. **SHA-256 attach in Firebase console** (optional App Check nicety): register
   the app's signing cert SHA-256 against app
   `1:35318880783:android:aa2ecfa5999e006359a17a` if/when App Check is adopted.
   Not required for Auth phone sign-in (which works on package + API key).
2. **Future AAB uploads** to the existing `com.getfitwithus.app` Play listing
   must be signed with that app's registered upload key — signing identity
   unchanged by this work, but the constraint now applies to every upload.
3. **Firebase console spot-check** (owner): confirm the `com.fitnation.fitnation_app`
   deletion is what shows in the console and Phone sign-in is enabled for the
   `com.getfitwithus.app` app.
4. **GitHub issue**: create from `.zcode/ticket-firebase-convergence.md` once gh
   auth is repaired (§5).
5. **Server/WABA side** (already handled outside this repo, listed for the
   release checklist): zero-tap template approved with
   `zero_tap_terms_accepted`, package `com.getfitwithus.app`, signature hash
   `csMKq3/km+M`. If that hash ever proves wrong (it derives from the owner's
   pasted Play App-Signing cert fingerprint), only the template value changes —
   receiver code is unaffected; zero-tap then degrades to WhatsApp's one-tap /
   copy-code fallback.
