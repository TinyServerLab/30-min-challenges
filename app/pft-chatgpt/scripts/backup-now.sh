#!/bin/sh
set -eu
set -a
[ -f .env ] && . ./.env
set +a
mkdir -p data/backups
docker compose exec -T db pg_dump -Fc | gzip -9 > "data/backups/manual-$(date +%Y%m%d-%H%M%S).dump.gz"
echo "Manual backup written to data/backups/"
