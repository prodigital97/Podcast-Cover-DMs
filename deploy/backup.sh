#!/usr/bin/env bash
# Nightly snapshot of the lead database. Installed as /usr/local/bin/dms-backup.
#
# Uses sqlite3 .backup rather than cp — copying a live SQLite file can capture a
# torn write mid-transaction, which restores as a corrupt database.

set -euo pipefail

DB=/var/lib/podcast-cover-dms/dms.sqlite3
DEST=/var/backups/podcast-cover-dms
KEEP_DAYS=14

[[ -f "$DB" ]] || exit 0
mkdir -p "$DEST"

stamp="$(date +%Y-%m-%d)"
sqlite3 "$DB" ".backup '$DEST/dms-$stamp.sqlite3'"
gzip -f "$DEST/dms-$stamp.sqlite3"
find "$DEST" -name 'dms-*.sqlite3.gz' -mtime "+$KEEP_DAYS" -delete
