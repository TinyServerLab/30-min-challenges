#!/bin/sh
set -eu
: "${BACKUP_CRON:=30 2 * * *}"
echo "${BACKUP_CRON} /usr/local/bin/backup.sh >> /proc/1/fd/1 2>&1" > /etc/crontabs/root
echo "backup: scheduled '${BACKUP_CRON}' (TZ=${TZ:-UTC}), keeping ${BACKUP_KEEP_DAYS:-30} days in /backups"
# take one on start so a fresh deploy always has a baseline
/usr/local/bin/backup.sh || true
exec crond -f -l 6
