#!/usr/bin/env bash
# Backs up everything a participant produced: the database and the generated
# reminder images. Run it on a schedule, and copy the output OFF this server —
# a backup that only exists on the disk it is backing up is not a backup.
#
#   ./backup.sh                     # -> ./backups/moirai-<timestamp>.tar.gz
#   BACKUP_DIR=/mnt/backups ./backup.sh
#
# Reads DATABASE_URL and DATA_DIR from the environment, so it backs up
# whatever the running server is actually using. Restore: see RESTORE.md.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups}"
DATA_DIR="${DATA_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../app" && pwd)/static}"
DATABASE_URL="${DATABASE_URL:-}"

STAMP="$(date +%Y%m%d-%H%M%S)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$BACKUP_DIR"

# ── Database ────────────────────────────────────────────────────────────────
case "$DATABASE_URL" in
  postgres*|postgresql*)
    command -v pg_dump >/dev/null || { echo "pg_dump not found (install postgresql-client)" >&2; exit 1; }
    # SQLAlchemy's +psycopg suffix is not valid libpq syntax; strip it.
    PG_URL="${DATABASE_URL/+psycopg/}"
    PG_URL="${PG_URL/+psycopg2/}"
    pg_dump --no-owner --format=custom --file="$STAGE/database.dump" "$PG_URL"
    ;;
  sqlite*|"")
    DB_FILE="${DATABASE_URL#sqlite://}"
    DB_FILE="${DB_FILE#/}"          # sqlite:////abs/path -> /abs/path
    [ -z "$DB_FILE" ] && DB_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../app" && pwd)/database/app.db"
    [ "${DB_FILE:0:1}" = "/" ] || DB_FILE="/$DB_FILE"
    if [ ! -f "$DB_FILE" ]; then
      echo "SQLite file not found: $DB_FILE" >&2
      exit 1
    fi
    # .backup, not cp: it takes a consistent snapshot while the server is
    # mid-write. Copying the file directly can capture a torn database.
    if command -v sqlite3 >/dev/null; then
      sqlite3 "$DB_FILE" ".backup '$STAGE/app.db'"
    else
      echo "sqlite3 CLI not found — falling back to a plain copy (server should be stopped)" >&2
      cp "$DB_FILE" "$STAGE/app.db"
    fi
    ;;
  *)
    echo "Unrecognised DATABASE_URL: $DATABASE_URL" >&2
    exit 1
    ;;
esac

# ── Generated reminder images ───────────────────────────────────────────────
if [ -d "$DATA_DIR/reminders" ]; then
  mkdir -p "$STAGE/reminders"
  cp -R "$DATA_DIR/reminders/." "$STAGE/reminders/" 2>/dev/null || true
fi

# ── Manifest, so a restore months later is not guesswork ────────────────────
cat > "$STAGE/MANIFEST.txt" <<EOF
created_at:   $(date -u +%Y-%m-%dT%H:%M:%SZ)
host:         $(hostname)
database_url: ${DATABASE_URL:-<default sqlite>}
data_dir:     $DATA_DIR
images:       $(find "$STAGE/reminders" -type f 2>/dev/null | wc -l | tr -d ' ')
EOF

ARCHIVE="$BACKUP_DIR/moirai-$STAMP.tar.gz"
tar -czf "$ARCHIVE" -C "$STAGE" .

echo "✅ $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"
echo "   Now copy it off this server. See scripts/RESTORE.md before you need it."
