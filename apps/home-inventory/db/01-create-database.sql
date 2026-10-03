-- =============================================================================
-- Home Asset + Warranty — one-time database bootstrap on the SHARED PostgreSQL
-- =============================================================================
-- Run ONCE as a PostgreSQL superuser (e.g. `postgres`). Idempotent: safe to re-run.
-- It only creates a role + a database for this app. It does not touch any other
-- database, role or schema on the shared instance.
--
-- Usage (normally via db/init-db.sh):
--   psql -U postgres -v app_db=home_inventory -v app_user=home_inventory_user \
--        -v app_password='s3cret' -f 01-create-database.sql
--
-- Tables are NOT created here. The application creates/upgrades its own schema
-- on startup from backend/migrations/*.sql (see 0001_initial.sql).
-- =============================================================================

\set ON_ERROR_STOP on

-- 1. Application login role (create or rotate password)
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE',
              :'app_user', :'app_password')
\gexec

-- 2. Dedicated database owned by the app role
SELECT format('CREATE DATABASE %I OWNER %I ENCODING ''UTF8'' TEMPLATE template0',
              :'app_db', :'app_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'app_db')
\gexec

-- 3. Lock the database down: only the app role (and superusers) may connect
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'app_db') \gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I', :'app_db', :'app_user') \gexec

-- 4. Inside the new database: make the app role own the public schema
\connect :app_db
SELECT format('ALTER SCHEMA public OWNER TO %I', :'app_user') \gexec
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

\echo 'Done. Database' :app_db 'is ready for role' :app_user
