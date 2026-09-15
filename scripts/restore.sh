#!/usr/bin/env bash
# Restore a backup into the running db container.
#   ./scripts/restore.sh backups/ledger_2026-09-15_0230.dump
set -euo pipefail
FILE="${1:?usage: restore.sh <backup.dump>}"
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
echo "This will REPLACE the contents of database '${POSTGRES_DB:-ledger}'. Ctrl-C to abort."
sleep 4
docker compose stop app
docker compose exec -T db pg_restore -U "${POSTGRES_USER:-ledger}" -d "${POSTGRES_DB:-ledger}" --clean --if-exists --no-owner < "$FILE"
docker compose start app
echo "Restored from $FILE"
