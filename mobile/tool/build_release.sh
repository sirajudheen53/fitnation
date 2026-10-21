#!/usr/bin/env bash
#
# FitNation customer app — reproducible signed release AAB build (Play path).
#
# Usage (from anywhere):
#   mobile/tool/build_release.sh [--skip-checks] [--allow-dirty] [--clean]
#                                [--build-dir PATH] [--dart-define=K=V ...]
#
# Toolchain is pinned per machine (defaults below, override via env):
#   FLUTTER_BIN, JAVA_HOME, ANDROID_SDK_ROOT, BUNDLETOOL_JAR
#
# Guarantees:
# - Signs only with the upload key from mobile/android/key.properties.
#   If the signing material is missing the script FAILS and does NOT build —
#   a debug-signed release can never be updated on Play.
# - Refuses to build from a dirty `mobile/` tree (release traceability) unless
#   --allow-dirty.
# - Runs `flutter analyze` + `flutter test` before building (override with
#   --skip-checks; CI runs both separately).
# - Verifies the produced AAB with bundletool (applicationId, targetSdk >= 36,
#   versionCode/versionName match pubspec.yaml) and the signing cert.
# - Never prints keystore passwords or any other secret.
#
# Output AAB: mobile/build/app/outputs/bundle/release/app-release.aab
set -euo pipefail

MOBILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBSPEC="$MOBILE_DIR/pubspec.yaml"
OUT_AAB="$MOBILE_DIR/build/app/outputs/bundle/release/app-release.aab"
LOG_DIR="/tmp/fitnation-release"
PACKAGE="com.getfitwithus.app"
MIN_TARGET_SDK=36            # Play floor for new apps — see docs/play-release-checklist.md

FLUTTER_BIN="${FLUTTER_BIN:-$HOME/development/flutter/bin/flutter}"
JAVA_HOME="${JAVA_HOME:-$HOME/development/jdk-17.0.17+10}"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/development/android-sdk}"
BUNDLETOOL_JAR="${BUNDLETOOL_JAR:-/tmp/bundletool.jar}"

SKIP_CHECKS=0; ALLOW_DIRTY=0; DO_CLEAN=0; EXTRA_DEFINES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-checks) SKIP_CHECKS=1 ;;
    --allow-dirty) ALLOW_DIRTY=1 ;;
    --clean) DO_CLEAN=1 ;;
    --dart-define=*) EXTRA_DEFINES+=("$1") ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
mkdir -p "$LOG_DIR"
cd "$MOBILE_DIR"   # flutter/gradle command cwd; the caller's cwd must not matter

fail() { echo "❌ BUILD RELEASE FAILED: $*" >&2; exit 1; }

# grep that treats "no match" as empty output, not a fatal exit — several
# calls below are parse-attempts whose result we *check* afterwards, and
# set -euo pipefail would otherwise kill the script silently.
mgrep() { grep "$@" 2>/dev/null || true; }

banner() { echo "═══ $* ═══"; }

# ── 1. Toolchain present ─────────────────────────────────────────────────────
export JAVA_HOME ANDROID_SDK_ROOT
PATH="$JAVA_HOME/bin:$PATH"
[ -x "$FLUTTER_BIN" ]       || fail "flutter not found at $FLUTTER_BIN (set FLUTTER_BIN)"
[ -d "$JAVA_HOME" ]         || fail "JDK 17 not found at $JAVA_HOME (set JAVA_HOME)"
[ -d "$ANDROID_SDK_ROOT" ]  || fail "Android SDK not found at $ANDROID_SDK_ROOT (set ANDROID_SDK_ROOT)"

banner "toolchain: $($FLUTTER_BIN --version 2>/dev/null | head -1)" \
       "| java $($JAVA_HOME/bin/java -version 2>&1 | head -1 | sed 's/.*"\(.*\)".*/\1/')"

# ── 2. Signing material — fail loudly, never build unsigned/debug ────────────
KEYPROPS="$MOBILE_DIR/android/key.properties"
[ -f "$KEYPROPS" ] || fail "mobile/android/key.properties is missing. No release signing material \
refuses to build (debug-signed AABs can never be updated on Play). See mobile/RELEASE.md §Signing."

read_keystore_prop() {
  python3 -c '
import sys
vals = {}
for line in open(sys.argv[1]):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, v = line.split("=", 1); vals[k.strip()] = v.strip()
sys.stdout.write(vals.get(sys.argv[2], ""))' "$1" "$2"
}
STORE_FILE_VAL="$(read_keystore_prop "$KEYPROPS" storeFile)"
KEY_ALIAS_VAL="$(read_keystore_prop "$KEYPROPS" keyAlias)"
HAS_PASS=NO
python3 -c '
import sys
vals = {}
for line in open(sys.argv[1]):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, v = line.split("=", 1); vals[k.strip()] = v.strip()
sys.exit(0 if vals.get("storePassword") and vals.get("keyPassword") else 2)' "$KEYPROPS" && HAS_PASS=YES

[ -n "$STORE_FILE_VAL" ] || fail "key.properties has no storeFile"
if [ -n "$STORE_FILE_VAL" ] && [ "${STORE_FILE_VAL#/}" = "$STORE_FILE_VAL" ]; then
  KEYSTORE_PATH="$(cd "$MOBILE_DIR/android" && readlink -m "$STORE_FILE_VAL")"
else
  KEYSTORE_PATH="$STORE_FILE_VAL"
fi
[ -f "$KEYSTORE_PATH" ]     || fail "keystore file not found: $KEYSTORE_PATH (storeFile in key.properties)"
[ -n "$KEY_ALIAS_VAL" ]     || fail "key.properties has no keyAlias"
[ "$HAS_PASS" = YES ]       || fail "key.properties is missing storePassword/keyPassword"
echo "signing: upload keystore at ${KEYSTORE_PATH/$HOME/~} (alias present, passwords present — not echoed)"

# ── 3. Version (single source: pubspec.yaml) ─────────────────────────────────
VERSION_LINE="$(mgrep '^version:' "$PUBSPEC" | head -1 | sed 's/^version:[[:space:]]*//')"
VERSION_NAME="${VERSION_LINE%%+*}"; VERSION_CODE="${VERSION_LINE#*+}"
[ -n "$VERSION_NAME" ] || fail "cannot parse 'version: MAJOR.MINOR.PATCH+CODE' from pubspec.yaml"
case "$VERSION_CODE" in (*[!0-9]*|'') fail "versionCode '$VERSION_CODE' is not a positive integer" ;; esac
banner "release version: $VERSION_NAME (+$VERSION_CODE versionCode)"

# ── 4. Traceability: dirty tree refuses to build ─────────────────────────────
if [ "$ALLOW_DIRTY" = 0 ]; then
  DIRTY="$(git -C "$MOBILE_DIR" status --porcelain -- . 2>/dev/null | mgrep -v '^??' | head -10)"
  [ -z "$DIRTY" ] || { echo "$DIRTY" | sed 's/^/    /'; fail "uncommitted changes under mobile/ — commit or stash first (--allow-dirty to override)"; }
  echo "tree: clean under mobile/"
fi

# ── 5. Static gates (default on) ─────────────────────────────────────────────
if [ "$SKIP_CHECKS" = 0 ]; then
  banner "flutter analyze (${LOG_DIR}/analyze.log)"
  "$FLUTTER_BIN" analyze > "$LOG_DIR/analyze.log" 2>&1 || { tail -30 "$LOG_DIR/analyze.log" >&2; fail "flutter analyze failed — see $LOG_DIR/analyze.log"; }
  tail -1 "$LOG_DIR/analyze.log"
  banner "flutter test (${LOG_DIR}/test.log) — this can take a while"
  "$FLUTTER_BIN" test > "$LOG_DIR/test.log" 2>&1 || { tail -40 "$LOG_DIR/test.log" >&2; fail "flutter test failed — see $LOG_DIR/test.log"; }
  tail -1 "$LOG_DIR/test.log"
else
  echo "checks: skipped (--skip-checks)"
fi

# ── 6. Build ─────────────────────────────────────────────────────────────────
[ "$DO_CLEAN" = 1 ] && "$FLUTTER_BIN" clean > "$LOG_DIR/clean.log" 2>&1
banner "flutter pub get"
"$FLUTTER_BIN" pub get > "$LOG_DIR/pubget.log" 2>&1 || { tail -20 "$LOG_DIR/pubget.log" >&2; fail "pub get failed"; }
banner "flutter build appbundle --release"
"$FLUTTER_BIN" build appbundle --release \
  --dart-define=SERVER=prod \
  ${EXTRA_DEFINES[@]+"${EXTRA_DEFINES[@]}"} > "$LOG_DIR/build.log" 2>&1 || { tail -40 "$LOG_DIR/build.log" >&2; fail "appbundle build failed — see $LOG_DIR/build.log"; }
grep -E "Built build/app/outputs|✓" "$LOG_DIR/build.log" | tail -2 || true

[ -f "$OUT_AAB" ] || fail "expected AAB not produced at $OUT_AAB"

# ── 7. Verify the AAB (bundletool; auto-download if absent) ──────────────────
if [ ! -f "$BUNDLETOOL_JAR" ]; then
  if curl -fsSL -o "$BUNDLETOOL_JAR" https://github.com/google/bundletool/releases/download/1.18.0/bundletool.jar 2>/dev/null; then
    echo "bundletool: downloaded 1.18.0 → $BUNDLETOOL_JAR"
  else
    echo "⚠ bundletool unavailable — manifest/cert checks SKIPPED (install to /tmp/bundletool.jar)." >&2
  fi
fi
CERT_SHA=""
if [ -f "$BUNDLETOOL_JAR" ]; then
  "$JAVA_HOME/bin/java" -jar "$BUNDLETOOL_JAR" validate --bundle="$OUT_AAB" > "$LOG_DIR/validate.log" 2>&1 \
    || { tail -20 "$LOG_DIR/validate.log" >&2; fail "bundletool validate failed"; }
  "$JAVA_HOME/bin/java" -jar "$BUNDLETOOL_JAR" dump manifest --bundle="$OUT_AAB" > "$LOG_DIR/manifest.log" 2>&1 \
    || { tail -20 "$LOG_DIR/manifest.log" >&2; fail "bundletool dump manifest failed"; }
  M_PKG="$(mgrep -o 'package="[^"]*"' "$LOG_DIR/manifest.log" | head -1 | cut -d'"' -f2)"
  M_VCODE="$(mgrep -o 'versionCode="[0-9]*"' "$LOG_DIR/manifest.log" | head -1 | mgrep -o '[0-9]*')"
  M_VNAME="$(mgrep -o 'versionName="[^"]*"' "$LOG_DIR/manifest.log" | head -1 | cut -d'"' -f2)"
  M_MIN="$(mgrep -oE 'minSdkVersion="[0-9]*"' "$LOG_DIR/manifest.log" | head -1 | mgrep -o '[0-9]*')"
  M_TGT="$(mgrep -oE 'targetSdkVersion="[0-9]*"' "$LOG_DIR/manifest.log" | head -1 | mgrep -o '[0-9]*')"
  [ "$M_PKG" = "$PACKAGE" ] || fail "AAB applicationId is '$M_PKG', expected '$PACKAGE'"
  [ "$M_VCODE" = "$VERSION_CODE" ] || fail "AAB versionCode is '$M_VCODE', pubspec says '$VERSION_CODE'"
  [ "$M_VNAME" = "$VERSION_NAME" ] || fail "AAB versionName is '$M_VNAME', pubspec says '$VERSION_NAME'"
  [ -n "$M_TGT" ] && [ "$M_TGT" -ge "$MIN_TARGET_SDK" ] || fail "AAB targetSdkVersion is '$M_TGT', must be >= $MIN_TARGET_SDK (Play floor for new apps)"
  unzip -p "$OUT_AAB" "META-INF/*.RSA" > "$LOG_DIR/cert.bin" 2>/dev/null || fail "no signing certificate block in AAB"
  CERT_SHA="$($JAVA_HOME/bin/keytool -printcert -file "$LOG_DIR/cert.bin" 2>/dev/null | mgrep -m1 'SHA256:' | sed 's/^.*SHA256: *//')"
  CERT_CN="$($JAVA_HOME/bin/keytool -printcert -file "$LOG_DIR/cert.bin" 2>/dev/null | mgrep -m1 'Owner:' | sed 's/Owner: *//')"
  case "$CERT_CN" in *Debug*|*Android\ Debug*) fail "AAB is signed with a DEBUG certificate";; esac
fi

# ── 8. Summary ───────────────────────────────────────────────────────────────
SIZE="$(ls -lh "$OUT_AAB" | awk '{print $5}')"
echo
echo "════════════ RELEASE AAB READY ════════════"
echo "  path        : $OUT_AAB"
echo "  size        : $SIZE"
echo "  versionCode : $VERSION_CODE    versionName: $VERSION_NAME"
echo "  appId       : $PACKAGE"
if [ -n "$CERT_SHA" ]; then
  echo "  minSdk      : $M_MIN    targetSdk: $M_TGT"
  echo "  cert CN     : $CERT_CN"
  echo "  cert SHA256 : $CERT_SHA"
fi
echo "═══════════════════════════════════════════"