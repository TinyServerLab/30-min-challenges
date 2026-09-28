#!/bin/sh
set -eu
mkdir -p /backups
echo "Nightly PostgreSQL backup loop started (02:30 local time)."
while true; do
  now="$(date +%H:%M)"
  if [ "$now" = "02:30" ]; then
    ts="$(date +%Y%m%d-%H%M%S)"
    tmp="/backups/.finance-${ts}.dump.gz.tmp"
    out="/backups/finance-${ts}.dump.gz"
    echo "[$(date)] Starting backup..."
    pg_dump -Fc | gzip -9 > "$tmp"
    mv "$tmp" "$out"
    find /backups -type f -name 'finance-*.dump.gz' -mtime +"${BACKUP_RETENTION_DAYS:-14}" -delete
    echo "[$(date)] Backup complete: $out"
    sleep 90
  fi
  sleep 30
done
