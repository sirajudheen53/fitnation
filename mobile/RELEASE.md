# FitNation mobile — release engineering (Google Play)

Release identity, version policy, build & verification procedure for the
FitNation customer app. Owned by mobile (Swift); the orchestrator uses this
file for the Play upload.

> **The full release runbook lives in `docs/play-release-checklist.md`** — it is
> the single source of truth (pre-flight, upload, listing, Data Safety, health
> declaration, review notes, pilot, rollback, known Play constraints). This file
> holds the *release identity* and the build/verify mechanics only.

## Release identity

| Fact | Value |
|---|---|
| Application ID | `com.getfitwithus.app` (renamed from `com.fitnation.fitnation_app` before first upload; immutable after first Play upload) |
| First release version | `1.0.0+1` |
| minSdk / targetSdk / compileSdk | 24 / 36 (pinned, Play floor for new apps) / 36 |
| Kotlin/Java toolchain | JDK 17 (`~/development/jdk-17.0.17+10`), JVM target 17 |
| Flutter toolchain | `~/development/flutter` (3.47.1 stable at 1.0.0) |

## Version policy (pubspec.yaml `version:`)

Format `MAJOR.MINOR.PATCH+CODE`:

- **MAJOR.MINOR.PATCH** = semantic version of the customer app; bump PATCH
  for fixes, MINOR for features, MAJOR for breaking UX/backend-version cuts.
- **versionCode (+CODE)** is what Play treats as ordering. It is used by
  Flutter directly (see `android/app/build.gradle.kts defaultConfig`). Rule:
  **strictly monotonic integers, +1 per Play upload**. Never reuse a code,
  never skip publishing order. `1.0.1+2`, `1.1.0+3`, …
- Bump BOTH parts in `mobile/pubspec.yaml` in the release commit; the AAB
  build derives everything from that single line (verify step below).
- A Play release requires: green `flutter test`, `flutter analyze` clean,
  AAB built from a clean tree WITHOUT uncommitted changes, verification of
  §Verification below, and the store assets under `mobile/store/`.

## Signing (upload key)

- Keystore: `mobile/android/app/upload-keystore.jks`
- Credentials: `mobile/android/key.properties` (gitignored — format:
  `storeFile=app/upload-keystore.jks`, `storePassword`, `keyAlias=upload`,
  `keyPassword`). **Never commit, echo, print, or paste these values.**
- Key alias: `upload`; RSA 2048; valid 10 000 days (until 2054-03-08);
  generated specifically for this app — **do not reuse any other project's
  keystore** (the lifestyle-tailoring one is off-limits).
- Upload-key certificate SHA-256 (needed for Play App Signing enrollment
  and app-link `assetlinks.json`):
  `E2:3A:7B:D7:D8:B2:F8:62:15:4C:49:84:3A:42:11:B8:63:94:5E:D6:83:61:37:1B:E4:59:01:3C:B7:C2:86:72`
- Behavior: `android/app/build.gradle.kts` reads `key.properties` and creates
  the `upload` signing config. **A `--release` build without the material
  fails loudly** (GradleException: "Release build refused…") — it never
  falls back to debug keys. Dev machines without the keystore can still run
  debug builds normally.
- Backup: the keystore and its password must live in the team's secret
  manager (Google owns re-set of the upload key through Play Console
  support, but treat loss as an incident).

## Build the release AAB (the one-liner)

```bash
# from the repo root — pinned toolchain, fail-loud signing gate, post-build verify
mobile/tool/build_release.sh
```

`mobile/tool/build_release.sh` pins Flutter 3.47.1 + JDK 17 + the Android SDK,
runs `flutter analyze` and `flutter test`, builds with
`--dart-define=SERVER=prod`, then verifies the AAB with `bundletool`
(applicationId, versionCode, versionName, minSdk, targetSdk ≥ 36) and `keytool`
(the cert must be the upload cert, never a debug one). It **fails loudly** when
the signing material is missing — it never falls back to debug keys. Options:
`--skip-checks` (skip analyze+test), `--clean` (flutter clean first),
`--allow-dirty` (build from an uncommitted tree).

The raw equivalent (what the script runs) is:

```bash
cd mobile
PATH=~/development/flutter/bin:$PATH \
JAVA_HOME=~/development/jdk-17.0.17+10 \
ANDROID_SDK_ROOT=~/development/android-sdk \
~/development/flutter/bin/flutter build appbundle --release --dart-define=SERVER=prod
```

This uses Flutter's gradle wrapper (gradle 9.3.1 per
`android/gradle/wrapper/gradle-wrapper.properties`). Output:
`build/app/outputs/bundle/release/app-release.aab` (55.6 MB at 1.0.0+1).
Android SDK at `~/development/android-sdk` (platforms 34 & 36 installed).

**Which gradle path worked:** the Flutter-bundled gradle **wrapper**
(`gradle-9.3.1-all.zip`, via `android/gradle/wrapper/gradle-wrapper.properties`)
is fully usable on this machine — the release AAB was built through it. The
standalone `~/gradle-8.7/bin/gradle` fallback was **not** needed and is not
required (8.7 is also older than what the Android Gradle Plugin in this
project expects). Keep using the wrapper.

## Verification record (1.0.0+1, 2026-10-21 — re-verified)

Tools: `bundletool` 1.18.0 (`/tmp` — not committed; re-download from
github.com/google/bundletool releases if absent), JDK keytool, unzip.

1. **Manifest / identity** —
   `java -jar bundletool.jar dump manifest --bundle=build/app/outputs/bundle/release/app-release.aab`
   ```
   <manifest … android:compileSdkVersion="36"
             android:versionCode="1" android:versionName="1.0.0"
             package="com.getfitwithus.app" …>
     <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="36"/>
   ```
2. **Structure** — `java -jar bundletool.jar validate --bundle=<aab>` → exit 0.
3. **Signing key** —
   `unzip -p <aab> "META-INF/*.RSA" | keytool -printcert`
   ```
   Owner: CN=FitNation Upload, OU=Mobile, O=FitNation, L=Bengaluru, ST=Karnataka, C=IN
   Valid until: Sun Mar 08 … 2054
   SHA256: E2:3A:7B:D7:D8:B2:F8:62:15:4C:49:84:3A:42:11:B8:63:94:5E:D6:83:61:37:1B:E4:59:01:3C:B7:C2:86:72
   ```
   The signature block is `META-INF/UPLOAD.RSA` (AGP names it after the
   `upload` config) and the SHA-256 matches the upload keystore exactly —
   NOT the debug key.
4. **Fail-loud gate** — with `key.properties` moved away,
   `flutter build appbundle --release` exits 1 with "Release build refused:
   mobile/android/key.properties (upload-key signing material) is missing…".
5. **Gates green** — `flutter analyze` → *No issues found*;
   `flutter test` → *480 tests, all passed* (re-run at the final 1.0.0+1
   rebuild; the record above originally measured 309 before the last test
   suites landed — the count only grows, the gate is "all passed").
6. **Prod host baked in** —
   `unzip -p build/app/outputs/bundle/release/app-release.aab base/lib/arm64-v8a/libapp.so | strings | grep -oE "https?://[a-z.]*yougetfitwithus\.com[^ \"]*"`
   → `https://api.yougetfitwithus.com` (the only app host in the binary;
   the remaining URLs are framework strings — pub.dev, fonts.gstatic,
   github — and there are no dev/localhost hosts).

Repeat steps 1 and 3 for every release build before upload.

## Store assets

`mobile/store/README.md` maps assets → Play Console slots
(`app-icon-512.png`, `feature-graphic-1024x500.png`, launcher icon sets).
`mobile/store/play-health-data-disclosure.md` holds the Draft answers for
Data safety + the Health apps declaration (health profile, body
measurements, progress photos — collected, not shared, TLS in transit,
in-app deletion path). Real screenshots were NOT produced (no
device/emulator on this machine) — see the shot list in
`store/README.md`; do not fabricate them.

## Play state (verified 2026-10-21, read-only)

| Item | State |
|---|---|
| App shell (`com.getfitwithus.app`) | **exists** — `GET /edits/{id}/tracks` returns internal/alpha/beta/production (a bogus package returns `404 "Package not found"`) |
| Releases on any track | **none** — `GET /edits/{id}/bundles` → empty |
| Store listing (en-IN) | **missing** — `GET …/listings/en-IN` → `404 "Listing for language 'en-IN' not found."` |
| App Signing | not enrolled yet (enrolls on the first AAB upload) |

## Remaining HUMAN / Console-only steps (orchestrator + owner)

1. ~~Create the app shell~~ — **already done**; confirm App Signing is on the
   Google-managed key (it enrolls on the first upload).
2. Paste listing: icons/feature graphic from `mobile/store/`, marketing
   copy from `store/play-listing-content.md` (title ≤30 / short ≤80 / full
   ≤4000 chars are already checked there), screenshots (needs a device
   pass — shot list in `store/README.md`), category Fitness.
   *Or* upload it with the API: `tools/play/publish.py listing …` / `assets …`.
3. App content forms: privacy policy URL + account-deletion URL (owner
   decision — see open items in `play-health-data-disclosure.md`), Data
   safety answers from that same file, health-apps declaration, target
   audience/content rating.
4. Tester list (Console UI only) + internal testing opt-in link, then the
   pilot walkthrough, then production review submission. The upload itself
   is orchestrated, not local.