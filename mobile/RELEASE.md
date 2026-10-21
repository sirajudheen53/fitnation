# FitNation mobile — release engineering (Google Play)

Release identity, version policy, build & verification procedure for the
FitNation customer app. Owned by mobile (Swift); the orchestrator uses this
file for the Play upload.

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
cd mobile
PATH=~/development/flutter/bin:$PATH \
JAVA_HOME=~/development/jdk-17.0.17+10 \
ANDROID_SDK_ROOT=~/development/android-sdk \
~/development/flutter/bin/flutter build appbundle --release
```

This uses Flutter's gradle wrapper (gradle 8.7) — that is the path that
works; no fallback invocation was needed. Output:
`build/app/outputs/bundle/release/app-release.aab` (55.6 MB at 1.0.0+1).
Android SDK at `~/development/android-sdk` (platforms 34 & 36 installed).

## Verification record (1.0.0+1, 2026-10-21)

Tools: `bundletool` 1.18.0 (`/tmp` — not committed; re-download from
github.com/google/bundletool releases if absent), JDK keytool, unzip.

1. **Manifest / identity** —
   `java -jar bundletool.jar dump manifest --bundle=build/app/outputs/bundle/release/app-release.aab`
   ```
   versionCode="1"  versionName="1.0.0"  package="com.getfitwithus.app"
   minSdkVersion="24"  targetSdkVersion="36"
   ```
2. **Structure** — `java -jar bundletool.jar validate --bundle=<aab>` → exit 0.
3. **Signing key** —
   `unzip -p <aab> "META-INF/*.RSA" | keytool -printcert`
   ```
   Owner: CN=FitNation Upload, OU=Mobile, O=FitNation, …, C=IN
   Valid until: Sun Mar 08 … 2054
   SHA256: E2:3A:7B:D7:D8:B2:F8:62:15:4C:49:84:3A:42:11:B8:63:94:5E:D6:83:61:37:1B:E4:59:01:3C:B7:C2:86:72
   ```
   The signature block is `META-INF/UPLOAD.RSA` (AGP names it after the
   `upload` config) and the SHA-256 matches the upload keystore exactly —
   NOT the debug key.
4. **Fail-loud gate** — with `key.properties` moved away,
   `flutter build appbundle --release` exits 1 with "Release build refused:
   mobile/android/key.properties (upload-key signing material) is missing…".

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

## Remaining HUMAN / Console-only steps (orchestrator + owner)

1. Play Console: create the app shell for `com.getfitwithus.app`
   (owner: Siju) — choose app name, default language, app/games + free/paid.
2. Play App Signing: use the Google-generated app signing key, enroll the
   upload key (paste §Verification #3 fingerprint as identity proof).
3. Paste listing: icons/feature graphic from `mobile/store/`, marketing
   copy from `store/play-listing-content.md` (title ≤30 / short ≤80 / full
   ≤4000 chars are already checked there), screenshots (needs a device
   pass — shot list in `store/README.md`), category Fitness.
4. App content forms: privacy policy URL + account-deletion URL (owner
   decision — see open items in `play-health-data-disclosure.md`), Data
   safety answers from that same file, target-audience/content rating.
5. Tester list / internal testing track upload, then production review
   submission (the upload itself is orchestrated, not local).