#!/usr/bin/env bash
set -euo pipefail

STAMP=$(date +%Y%m%d_%H%M%S)
OUT_DIR="/backups"
FILE="${OUT_DIR}/finance_${STAMP}.sql.gz"

mkdir -p "${OUT_DIR}"

echo "[$(date -Iseconds)] Starting backup -> ${FILE}"
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
  -h "${PGHOST}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  --no-owner --no-privileges \
  | gzip > "${FILE}"
echo "[$(date -Iseconds)] Backup written: $(du -h "${FILE}" | cut -f1)"

# Prune backups older than the retention window.
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
find "${OUT_DIR}" -name 'finance_*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete

# Optional offsite copy. Configure once with:
#   docker compose exec backup rclone config
# then set RCLONE_REMOTE=your-remote:path in .env
if [ -n "${RCLONE_REMOTE:-}" ]; then
  echo "[$(date -Iseconds)] Syncing backups to ${RCLONE_REMOTE}"
  rclone copy "${OUT_DIR}" "${RCLONE_REMOTE}" --min-age 0s || \
    echo "[$(date -Iseconds)] WARNING: offsite sync failed — local backup is still safe"
fi

echo "[$(date -Iseconds)] Backup complete"
