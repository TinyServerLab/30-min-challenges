#!/bin/sh
set -eu
[ -f .env ] && . ./.env
if [ -z "${1:-}" ]; then
  echo "Usage: $0 data/backups/finance-YYYYMMDD-HHMMSS.dump.gz"
  exit 1
fi
echo "WARNING: restore replaces the current database."
docker compose stop app backup
gzip -dc "$1" | docker compose exec -T db pg_restore -U "${POSTGRES_USER:-finance}" -d "${POSTGRES_DB:-finance}" --clean --if-exists --no-owner --no-privileges
docker compose start app backup
