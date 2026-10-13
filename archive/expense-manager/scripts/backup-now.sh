#!/usr/bin/env bash
# Trigger an immediate backup (same script cron runs nightly).
cd "$(dirname "$0")/.." && docker compose exec backup /usr/local/bin/backup.sh
