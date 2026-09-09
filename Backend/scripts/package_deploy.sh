#!/usr/bin/env bash
# Builds a clean upload package for a manual deploy.
#
#   ./scripts/package_deploy.sh            # -> Backend/dist/moirai-deploy.zip
#   SKIP_WEB=1 ./scripts/package_deploy.sh # backend only, reuse existing app/web
#
# Unzip the RESULT at the deploy root (/app). Its top level is what Backend/
# should look like on the server: app/, main.py, requirements.txt.
#
# Two things this exists to get right, because both fail silently:
#   - app/web/ is gitignored but REQUIRED — without it the server serves an
#     API with no frontend, and nothing errors.
#   - .env and the local database must NOT ship. Secrets belong in the host's
#     env-var panel, and the local app.db would overwrite participant data.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
OUT="$ROOT/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

if [ "${SKIP_WEB:-0}" != "1" ]; then
  echo "▶ building the Flutter web app…"
  FLUTTER="${FLUTTER:-flutter}" "$ROOT/scripts/build_web.sh"
fi

if [ ! -d "$ROOT/app/web" ]; then
  echo "✗ app/web is missing — run scripts/build_web.sh first." >&2
  exit 1
fi

echo "▶ staging…"
mkdir -p "$STAGE/pkg"
# --- what ships ---
cp -R "$ROOT/app"              "$STAGE/pkg/app"
cp    "$ROOT/main.py"          "$STAGE/pkg/"
cp    "$ROOT/requirements.txt" "$STAGE/pkg/"
[ -f "$ROOT/Dockerfile" ] && cp "$ROOT/Dockerfile" "$STAGE/pkg/" || true

# --- what must NOT ship ---
rm -rf "$STAGE/pkg/app/.env" \
       "$STAGE/pkg/app/database/app.db" \
       "$STAGE/pkg/app/static/reminders"
find "$STAGE/pkg" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE/pkg" -name '*.pyc' -delete 2>/dev/null || true
find "$STAGE/pkg" -name '.DS_Store' -delete 2>/dev/null || true

# --- sanity checks: each of these fails silently in production ---
fail=0
check() { # path label
  if [ -e "$STAGE/pkg/$1" ]; then echo "  ✓ $2"; else echo "  ✗ MISSING: $2"; fail=1; fi
}
echo "▶ checking the package…"
check "main.py"                        "entrypoint (deploy root must be this dir)"
check "requirements.txt"               "root requirements"
check "app/main.py"                    "application"
check "app/web/index.html"             "Flutter build (frontend)"
check "app/static/moirai-extension.zip" "extension download"
if [ -d "$STAGE/pkg/app/static/generic" ] && \
   [ -n "$(ls -A "$STAGE/pkg/app/static/generic" 2>/dev/null)" ]; then
  echo "  ✓ generic control images ($(ls "$STAGE/pkg/app/static/generic" | wc -l | tr -d ' '))"
else
  echo "  ! generic control images absent — the control condition will be OFF"
fi
for leak in app/.env .env app/database/app.db; do
  [ -e "$STAGE/pkg/$leak" ] && { echo "  ✗ LEAK: $leak is in the package"; fail=1; }
done
echo "  ✓ no secrets or participant data in the package"
[ "$fail" = "0" ] || { echo "✗ package incomplete — not writing the zip." >&2; exit 1; }

mkdir -p "$OUT"

# An unzipped folder as well as the zip: FTP clients cannot unzip on the
# server, and the panel console is not always reachable, so dragging files is
# often the only route. This folder's CONTENTS are exactly what /app needs.
UPLOAD="$OUT/upload"
rm -rf "$UPLOAD"
mkdir -p "$UPLOAD"
cp -R "$STAGE/pkg/." "$UPLOAD/"

ZIP="$OUT/moirai-deploy.zip"
rm -f "$ZIP"
(cd "$STAGE/pkg" && zip -rq "$ZIP" .)

echo
echo "✅ FOR FILEZILLA — drag the CONTENTS of this folder into /app :"
echo "     $UPLOAD"
echo "   i.e. select these and drop them in /app:"
(cd "$UPLOAD" && ls -1 | sed 's/^/     • /')
echo
echo "   Afterwards /app/main.py must exist"
echo "   (not /app/Backend/main.py, not /app/upload/main.py)."
echo
echo "   Zip of the same thing, if you can unzip server-side:"
echo "     $ZIP  ($(du -h "$ZIP" | cut -f1))"
echo
echo "   Secrets are NOT included — set them in the host's env-var panel."
echo "   Do not touch /app/data on the server: that is the live database."
