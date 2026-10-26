# Mobile release prep: rewrite sync → mobile/ + signing merge + 1.0.3+4

Date: 2026-10-26 · Branch: `develop` · Commits: `d93d51d` (sync + merge + bump), `ac85d2d` (legacy test-straggler removal)
Source of truth synced: `/home/sirajudheen/development/fitnation-mobile` @ `ba310c0` ("docs: package+firebase convergence & zero-tap OTP report")

**Result: the tree is ready for the `release-mobile.yml` dispatch. A signed release AAB was built and verified locally — no Play upload was attempted host-side (per plan; publishing material lives only in GitHub secrets).**

---

## 1. Sync summary (STEP 1)

```
rsync -a --delete
  --exclude=.git --exclude=.zcode --exclude=build --exclude=.dart_tool
  --exclude=android/key.properties --exclude=android/app/upload-keystore.jks
  --exclude=tool --exclude=store
  --exclude=/RELEASE.md            # + addition 1: release doc, referenced by gradle signing comment
  --exclude=firebase-debug.log     # + addition 2: firebase CLI debug log (junk; no secrets in it, verified)
  fitnation-mobile/  mobile/
```

Survival check after sync (all present): `mobile/android/key.properties`, `mobile/android/app/upload-keystore.jks`, `mobile/tool/build_release.sh`, `mobile/store/` (Play assets), `mobile/RELEASE.md`.

- Sync commit stat: 249 files changed, +5,025 / −24,105 (33 added, 185 deleted, 31 modified under `mobile/`).
- Deletions confined to `lib/`, `test/`, `android/app/src/main/res/`, `ios/` — release tooling and signing material untouched.
- Incoming new files: Firebase phone-auth client/notifier, WhatsApp zero-tap OTP service + Kotlin receiver (`com/getfitwithus/app/otp/`), `lib/firebase_options.dart`, `android/app/google-services.json`, `assets/images/.gitkeep`, `firebase.json`, `AGENTS.md`, the two rewrite reports (`report-mobile-ci.md`, `report-mobile-package-firebase.md`), `mobile/.github/workflows/ci.yml` (inert inside the monorepo — GitHub only reads the root `.github/`; the root `release-mobile.yml` is untouched and remains the release path).

### Follow-up commit `ac85d2d` — legacy `test/store/` straggler

The `store` exclude (needed to protect `mobile/store/` Play assets) also protected the **old app's** `mobile/test/store/screenshot_capture_test.dart` from `--delete`. That suite tests deleted 1.0.2+3 screens (`AppEntitlementStatus` etc.) and produced all 156 `flutter analyze` errors on the first build attempt (verified: zero issues outside that file). Removed via `git rm -r mobile/test/store` in `ac85d2d`. Side benefit: `flutter test` can no longer regenerate `store/screenshots/*.png` (the old suite was the only thing that did that). `mobile/store/` itself is untouched — note its screenshots still show the old app's screens and are now stale for listing purposes.

## 2. Gradle merge (STEP 2)

`mobile/android/app/build.gradle.kts` = incoming rewrite file as base + signing spliced from the pre-sync backup (`/tmp/old-bgradle.kts`):

| Section | Origin | Content |
|---|---|---|
| `import java.io.FileInputStream / Properties` | old | keystore-properties preamble |
| key.properties loading block | old | `rootProject.file("key.properties")`, fails-safe when absent |
| `plugins` incl. `com.google.gms.google-services` | incoming | FlutterFire wiring |
| `namespace` / `applicationId` = `com.getfitwithus.app` | incoming | released Play identity |
| `targetSdk = 36` (explicit pin + Play-floor comment) | old | incoming had `flutter.targetSdkVersion`; pinned to 36 per the old release-grade file so the floor can't drift |
| `ndkVersion` commented out | incoming | rewrite-proven config (no native code; AGP pulls no NDK) |
| `signingConfigs.create("upload")` (conditional on key.properties + keystore existing) | old | reads storeFile/storePassword/keyAlias/keyPassword |
| `buildTypes.release.signingConfig = when { upload → upload; release task → GradleException; else → debug+warn }` | old | hard-fails unsigned release builds, tolerates debug config on dev machines |
| `dependencies`: whatsapp-otp-android-sdk 1.0.0 + junit | incoming | zero-tap OTP runtime dep |

Post-merge verification greps (all pass):

- (a) `signingConfigs` + `storeFile = uploadStoreFile` from key.properties — `build.gradle.kts:60-62`
- (b) `buildTypes.release` → `signingConfig = when { findByName("upload") … }` — `build.gradle.kts:72-74`
- (c) `com.google.gms.google-services` — app module `build.gradle.kts:7` + version `4.4.4` declared in `settings.gradle.kts:24`
- (d) `namespace` (line 25) and `applicationId` (line 39) both `com.getfitwithus.app`
- (e) `targetSdk = 36` (line 43)

`mobile/android/app/google-services.json` freshness: `project_info.project_id = yougetfitwithus`; client packages = `com.getfitwithus.app` + `com.getfitwithus.biodebug` (debug identity, harmless); API key present. This is the fresh post-convergence config from the rewrite repo (the monorepo had none before the sync — it is newly tracked in git, which the CI build needs).

## 3. Manifest patches (deliberate, on top of the sync)

The rewrite's template `AndroidManifest.xml` had two release blockers:

1. **`android.permission.INTERNET` was missing** — Flutter templates only add it implicitly via the debug/profile manifests, so a release AAB would ship with no network permission. Re-added explicitly (release builds must not depend on transitive manifest merges from Play-services AARs).
2. **`android:label` was `fitnation_app`** (template default; the rewrite's convergence report explicitly deferred it as "a product/branding decision"). Set to the shipped label `FitNation`.

Left as-is (consistent with the rewrite's descoped deps): FCM service entry, App-Link/`fitnation://` intent filters, `POST_NOTIFICATIONS` — all belong to the dropped `firebase_messaging` / `app_links` features.

## 4. Version bump (STEP 3)

`mobile/pubspec.yaml`: `version: 1.0.2+3` (monorepo) / `0.1.0+1` (rewrite) → **`1.0.3+4`** (versionCode 4; Play rejects a repeat of versionCode 3 currently on the internal track).

## 5. Build proof (STEP 5)

`mobile/tool/build_release.sh` — full run, **no `--allow-dirty` needed** (tree was clean; nothing to excuse):

```
toolchain : Flutter 3.47.1 (stable) · java 17.0.17
signing   : upload keystore mobile/android/app/upload-keystore.jks (alias present)
version   : 1.0.3 (+4 versionCode)
tree      : clean under mobile/
analyze   : No issues found! (ran in 8.1s)
test      : 00:15 +133: All tests passed!
build     : ✓ Built build/app/outputs/bundle/release/app-release.aab (52 MiB), bundleRelease 174.4s
```

Note: the script's bundletool step was **skipped on its own run** — its auto-download URL (`.../download/1.18.0/bundletool.jar`) returns 404; the current release asset is `bundletool-all-1.18.3.jar`. I downloaded 1.18.3 to `/tmp/bundletool.jar` manually and ran the verification explicitly. (Script left untouched per "keep tooling intact"; fix the URL before relying on auto-download, e.g. on CI.)

Explicit verification of the AAB:

```
$ bundletool validate  → OK (base module + 3 ABIs: arm64-v8a, armeabi-v7a, x86_64)
$ bundletool dump manifest:
    package            = "com.getfitwithus.app"   ✓ required
    android:versionCode  = "4"                    ✓ required (≠ 3 on internal track)
    android:versionName  = "1.0.3"
    minSdkVersion        = "24"
    targetSdkVersion     = "36"                   ✓ Play floor
```

Signing cert (extracted `META-INF/*.RSA` → keytool) vs upload keystore — exact match, and not a debug cert:

```
Owner : CN=FitNation Upload, OU=Mobile, O=FitNation, L=Bengaluru, ST=Karnataka, C=IN
SHA256: E2:3A:7B:D7:D8:B2:F8:62:15:4C:49:84:3A:42:11:B8:63:94:5E:D6:83:61:37:1B:E4:59:01:3C:B7:C2:86:72
```

Output artifact: `mobile/build/app/outputs/bundle/release/app-release.aab` (52 MiB, git-ignored).

## 6. Release content delta vs shipped 1.0.2+3 (be aware before dispatch)

The rewrite is a much smaller app — this internal release is a **functional descope** vs what is currently on the internal track:

- **Added**: Firebase phone-OTP login (with backend-OTP rollback path), WhatsApp zero-tap OTP receiver (Meta OTP Android SDK), gym-selection panel in auth.
- **Dropped** (code removed from the release): workouts, diet plans, progress/body-analysis, attendance + QR check-in, AI coach, AI nutrition, feedback, profile screens, **push notifications (FCM)**, deep links (`app_links` + intent filters), Play install-referrer attribution, QR display (`qr_flutter`), charts (`fl_chart`).
- **Launcher icon regressed to the Flutter template icon** — the rewrite never carried the brand adaptive-icon set (`mipmap-anydpi-v26/ic_launcher.xml` + foreground/background PNGs, deleted in the sync). If the brand icon is wanted on this release, restore from git history (`git checkout d93d51d^ -- mobile/android/app/src/main/res`) and re-run the build; flagged rather than silently reverted because the sync was specified to take the rewrite verbatim.
- `mobile/store/screenshots/*.png` still show the old app's screens (stale, but untouched per the exclude list).

## 7. Play publishing (STEP 6)

No host-side upload attempted — no service-account JSON exists locally by design. Publishing happens in the **`release-mobile.yml` CI workflow after the orchestrator dispatches it**; upload material lives in GitHub repo secrets (`PLAY_SERVICE_ACCOUNT_JSON`, `KEYSTORE_*`). **The `develop` tree at `ac85d2d` is ready for that dispatch.**

## 8. Leftovers / notes

- Old gradle backup kept at `/tmp/old-bgradle.kts` (machine-local).
- First build attempt failed on the legacy `test/store/` analyzer errors — fixed in `ac85d2d`; second run green end-to-end.
- `mobile/local.properties` (git-ignored) now carries the rewrite's SDK paths — same machine, no impact.
- Rewrite's `gradle.properties` ships `-Xmx2G` (fits this 7.3 GB host; the old 8 GB heap problem is gone).
- Android unit tests for the OTP receiver (`android/app/src/test/…/WhatsAppOtpBusTest.kt`) exist but are not wired into `build_release.sh` (gradle `testReleaseUnitTest` isn't invoked); they were green in the rewrite repo's CI.
- `.zcode` logs of other agents untouched.
