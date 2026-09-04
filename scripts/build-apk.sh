#!/usr/bin/env bash
#
# Build the Android app.
#
# The APK carries the dashboard inside it, so the web build has to happen first
# and be copied into the app's assets. Doing that by hand is the reliable way to
# ship an APK whose viewer is a version older than its sync code, so it is one
# command here.
#
#   ./scripts/build-apk.sh              # debug build, installable immediately
#   ./scripts/build-apk.sh release      # release build, needs signing (see below)
#
# Signing a release needs four environment variables. Without them the release
# build is unsigned and Android will refuse to install it:
#
#   ANDROID_KEYSTORE_PATH      absolute path to a .jks
#   ANDROID_KEYSTORE_PASSWORD
#   ANDROID_KEY_ALIAS
#   ANDROID_KEY_PASSWORD
#
# The SDK is found through ANDROID_HOME, ANDROID_SDK_ROOT, or local.properties.
set -euo pipefail

VARIANT="${1:-debug}"
case "$VARIANT" in
  debug|release) ;;
  *) echo "Usage: $0 [debug|release]" >&2; exit 2 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID="$ROOT/android-companion"
ASSETS="$ANDROID/app/src/main/assets/www"

if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ] \
   && [ ! -f "$ANDROID/local.properties" ]; then
  echo "No Android SDK found." >&2
  echo "Set ANDROID_HOME, or write sdk.dir=/path/to/sdk into" >&2
  echo "  $ANDROID/local.properties" >&2
  exit 1
fi

echo "==> Building the dashboard"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm ci 2>/dev/null || npm install
fi
npm run build

echo "==> Bundling it into the app"
# Removed rather than overwritten: a stale asset from a previous build would
# otherwise survive and be served in preference to nothing.
rm -rf "$ASSETS"
cp -r "$ROOT/frontend/dist" "$ASSETS"

echo "==> Building the APK ($VARIANT)"
cd "$ANDROID"
if [ "$VARIANT" = "release" ]; then
  ./gradlew --no-daemon assembleRelease
  OUT="app/build/outputs/apk/release/app-release.apk"
  [ -f "$OUT" ] || OUT="app/build/outputs/apk/release/app-release-unsigned.apk"
else
  ./gradlew --no-daemon assembleDebug
  OUT="app/build/outputs/apk/debug/app-debug.apk"
fi

if [ ! -f "$OUT" ]; then
  echo "Build finished but no APK was produced at $OUT" >&2
  exit 1
fi

DEST="$ROOT/performance-$VARIANT.apk"
cp "$OUT" "$DEST"
echo
echo "Built $DEST  ($(du -h "$DEST" | cut -f1))"
case "$OUT" in
  *unsigned*)
    echo
    echo "This APK is unsigned and will not install. Set the signing variables"
    echo "listed at the top of this script, or build the debug variant instead."
    ;;
esac
