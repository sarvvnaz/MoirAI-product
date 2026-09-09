# Restoring a backup

Produced by `scripts/backup.sh`. Each archive contains:

```
MANIFEST.txt        when/where it came from, and which database it was
app.db              (SQLite deployments)
database.dump       (Postgres deployments, pg_dump custom format)
reminders/*.png     the generated reminder images
```

## Test this before recruiting participants

An untested backup is not a backup. Do a full restore into a throwaway
environment once, confirm participant counts match, then delete it. Repeat
after any change to `DATABASE_URL` or `DATA_DIR`.

## Restore

```bash
mkdir -p /tmp/restore && tar -xzf moirai-<timestamp>.tar.gz -C /tmp/restore
cat /tmp/restore/MANIFEST.txt
```

Stop the server first. Restoring underneath a running server gives you a
corrupted database, not a restored one.

### SQLite

```bash
cp /tmp/restore/app.db /data/app.db
cp -R /tmp/restore/reminders/. /data/reminders/
```

### Postgres

`--clean` drops the existing objects first, so run it against the intended
database and no other.

```bash
pg_restore --no-owner --clean --if-exists -d "$DATABASE_URL" /tmp/restore/database.dump
cp -R /tmp/restore/reminders/. /data/reminders/
```

Then start the server and verify:

```bash
curl -H "X-Export-Key: $ADMIN_EXPORT_KEY" https://<host>/api/research/export \
  | python -c "import json,sys; d=json.load(sys.stdin); print({k: len(v) for k,v in d.items() if isinstance(v,list)})"
```

The counts should match the pre-loss dataset. Images must be restored
alongside the database — `reminder_assets.image_url` rows point at files by
name, and a row whose PNG is missing renders as a broken reminder.

## Scheduling

Run daily, and keep the copies somewhere other than this server:

```
0 3 * * * cd /srv && DATA_DIR=/data DATABASE_URL="$DATABASE_URL" ./scripts/backup.sh >> /data/backup.log 2>&1
```

Archives contain the complete dataset in the clear — store them somewhere
access-controlled, and prune old ones on a schedule you have actually decided
on rather than letting them accumulate indefinitely.
