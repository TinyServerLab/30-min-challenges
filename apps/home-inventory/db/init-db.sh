#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# One-time bootstrap: create the home_inventory role + database on the EXISTING
# shared PostgreSQL container. Reads DB_NAME / DB_USER / DB_PASSWORD from .env.
#
#   ./db/init-db.sh                      # uses container "shared-postgres", superuser "postgres"
#   PG_CONTAINER=pg PG_SUPERUSER=admin ./db/init-db.sh
#   PG_CONTAINER= PGHOST=127.0.0.1 PGPORT=5432 ./db/init-db.sh   # use local psql instead of docker exec
# -----------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a; # shellcheck disable=SC1091
  source .env; set +a
fi

: "${DB_NAME:=home_inventory}"
: "${DB_USER:=home_inventory_user}"
: "${DB_PASSWORD:?DB_PASSWORD must be set in .env}"
PG_CONTAINER="${PG_CONTAINER-shared-postgres}"
PG_SUPERUSER="${PG_SUPERUSER:-postgres}"

echo "→ Creating role '${DB_USER}' and database '${DB_NAME}' (other databases are untouched)"

PSQL_ARGS=(-v ON_ERROR_STOP=1 -U "$PG_SUPERUSER" -d postgres
           -v "app_db=${DB_NAME}" -v "app_user=${DB_USER}" -v "app_password=${DB_PASSWORD}")

if [[ -n "$PG_CONTAINER" ]]; then
  docker exec -i "$PG_CONTAINER" psql "${PSQL_ARGS[@]}" < db/01-create-database.sql
else
  psql "${PSQL_ARGS[@]}" -f db/01-create-database.sql
fi

echo "✓ Bootstrap complete. Tables are created by the app on first start (backend/migrations)."
