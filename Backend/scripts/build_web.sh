#!/usr/bin/env bash
# Builds the Flutter web app and drops it where FastAPI serves it (app/web),
# so the whole study ships as one origin: no CORS, one deploy, one domain.
#
# Run this before every deploy — app/web is a build artifact and is gitignored,
# so the image is only as fresh as the last run of this script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND="$ROOT/Frontend"
TARGET="$ROOT/Backend/app/web"

FLUTTER="${FLUTTER:-flutter}"
command -v "$FLUTTER" >/dev/null || {
  echo "flutter not found. Set FLUTTER=/path/to/flutter/bin/flutter" >&2
  exit 1
}

cd "$FRONTEND"

# pub.dev is often unreachable here; --offline reuses ~/.pub-cache so a build
# does not depend on the network. Drop PUB_OFFLINE=1 to fetch new packages.
if [ "${PUB_OFFLINE:-1}" = "1" ]; then
  "$FLUTTER" pub get --offline || echo "pub get --offline reported issues; continuing with the existing .dart_tool" >&2
  "$FLUTTER" build web --release --base-href / --no-pub
else
  "$FLUTTER" pub get
  "$FLUTTER" build web --release --base-href /
fi

rm -rf "$TARGET"
mkdir -p "$TARGET"
cp -R "$FRONTEND/build/web/." "$TARGET/"

echo "✅ Flutter web build copied to $TARGET"
