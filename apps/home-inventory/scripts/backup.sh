#!/usr/bin/env bash
# Nightly backup: database dump + invoice files, kept for KEEP_DAYS.
#   crontab -e  →  30 2 * * *  /home/pi/home-inventory/scripts/backup.sh >> /home/pi/home-inventory/backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; # shellcheck disable=SC1091
source .env; set +a

DEST="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEST"

echo "[$(date)] dumping ${DB_NAME}"
docker exec -e PGPASSWORD="$DB_PASSWORD" "${PG_CONTAINER:-shared-postgres}" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner > "$DEST/db-$STAMP.dump"

echo "[$(date)] archiving uploads"
tar -czf "$DEST/uploads-$STAMP.tar.gz" -C ./data uploads

find "$DEST" -name 'db-*.dump' -mtime +"$KEEP_DAYS" -delete
find "$DEST" -name 'uploads-*.tar.gz' -mtime +"$KEEP_DAYS" -delete
echo "[$(date)] done: $(du -sh "$DEST" | cut -f1) in $DEST"

# Restore:
#   docker compose stop app
#   docker exec -i -e PGPASSWORD=... shared-postgres pg_restore -U home_inventory_user -d home_inventory --clean --if-exists --no-owner < backups/db-XXXX.dump
#   tar -xzf backups/uploads-XXXX.tar.gz -C ./data
#   docker compose start app
