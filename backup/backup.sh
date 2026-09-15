#!/bin/sh
# Nightly logical backup: pg_dump (custom format, compressed) -> /backups, prune old, optional rclone offsite.
set -eu
OUT=/backups
STAMP=$(date +%Y-%m-%d_%H%M)
FILE="$OUT/${PGDATABASE}_${STAMP}.dump"
mkdir -p "$OUT"

pg_dump --format=custom --compress=6 --file="$FILE.tmp" "$PGDATABASE"
mv "$FILE.tmp" "$FILE"
echo "backup: wrote $FILE ($(du -h "$FILE" | cut -f1))"

# keep the newest N days
find "$OUT" -name "${PGDATABASE}_*.dump" -mtime +"${BACKUP_KEEP_DAYS:-30}" -print -delete | sed 's/^/backup: pruned /'

# optional offsite copy
if [ -n "${RCLONE_REMOTE:-}" ]; then
  if rclone copy "$FILE" "$RCLONE_REMOTE" --quiet; then
    echo "backup: copied to $RCLONE_REMOTE"
  else
    echo "backup: WARNING rclone copy failed"
  fi
fi
