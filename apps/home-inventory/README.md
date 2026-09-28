# Home Asset + Warranty

A self-hosted household app for purchases, invoices, warranties and reminders. It runs on a Raspberry Pi 5 with Docker, alongside your **existing shared PostgreSQL and Caddy**. It serves from `https://home.tinyserverlab.in/inventory`.

```
Photo / PDF of invoice ─► OCR suggests name, brand, model, serial, store, invoice no., date, total, warranty
                        ─► you confirm ─► warranty expiry calculated ─► dashboard ─► 30/7/0-day reminders
                        ─► spending by month / category / store
```

## What's inside

| Part | Tech |
|---|---|
| Backend | FastAPI (Python 3.12), SQLAlchemy 2, psycopg 3 |
| Frontend | React 18, Vite, Tailwind 4, Recharts. Built into the same image, no separate web server |
| OCR | Tesseract + poppler (runs on the Pi; nothing leaves the house) |
| Reminders | In-process daily job (APScheduler), sent by email over SMTP and/or phone push through ntfy |
| Auth | Argon2id password hashes and server-side sessions (httpOnly, Secure, SameSite=Lax cookie scoped to `/inventory`). Also a CSRF header check and login throttling |
| Container | One container, non-root, read-only root filesystem, 512 MB memory cap |

The app does **not** create a PostgreSQL or Caddy container. It never touches any other database.

```
home-inventory/
├── db/01-create-database.sql      # one-time: role + database on the shared Postgres (idempotent)
├── db/init-db.sh                  # runs the SQL above via `docker exec shared-postgres psql`
├── backend/migrations/0001_initial.sql   # schema: applied automatically by the app on start
├── backend/app/…                  # API, auth, OCR, reminders, CLI
├── frontend/…                     # React app
├── Dockerfile, docker-compose.yml, .env.example
├── deploy/Caddyfile.snippet
└── scripts/backup.sh, scripts/smoke_test.py
```

## Deploy on the Pi

```bash
git clone … home-inventory && cd home-inventory      # or copy the folder
cp .env.example .env && nano .env                     # DB_PASSWORD, networks, admin, SMTP/ntfy
mkdir -p data/uploads                                 # owned by your user (uid 1000), not root

# 1. one-time database bootstrap on the EXISTING shared Postgres
./db/init-db.sh

# 2. find the networks your Caddy and Postgres containers are on, put them in .env
docker network ls
docker inspect shared-postgres --format '{{json .NetworkSettings.Networks}}'

# 3. build + start (first ARM64 build takes ~5–8 min on a Pi 5)
docker compose up -d --build
docker compose logs -f app          # expect "Migrations applied: ['0001_initial']" then "Created bootstrap admin"
```

**4. Caddy.** Add the block from `deploy/Caddyfile.snippet` to your existing site. It must be `handle /inventory*` and **not** `handle_path`, because the app expects to receive the prefix. Then reload Caddy:

```bash
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

**5. First sign-in.** Open `https://home.tinyserverlab.in/inventory`, sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`, then **delete `ADMIN_PASSWORD` from `.env`**. It is only used when the users table is empty.

### Adding family members (no public sign-up)

Add them under **Settings → Family members**, or from the command line:

```bash
docker compose exec app python -m app.cli create-user --email amma@example.com --name "Amma" --username amma
docker compose exec app python -m app.cli create-user --email me@example.com --name Sathya --admin
docker compose exec app python -m app.cli reset-password --email amma@example.com
docker compose exec app python -m app.cli list-users
```

When `--password` is omitted, the CLI prompts for it. Passwords need at least 10 characters and a mix of character types.

## Base path `/inventory`

- Everything is served under `BASE_PATH`: the SPA, bundles (`/inventory/_app/…`), the API (`/inventory/api/…`) and invoice files (`/inventory/api/attachments/{id}/file`).
- The frontend is built with relative URLs. The server injects `<base href="/inventory/">` at runtime, so changing `BASE_PATH` needs only a restart, not a rebuild.
- `/` and `/inventory` redirect to `/inventory/`. Deep links like `/inventory/assets/12` work on refresh.
- The session cookie is `Path=/inventory`, so other apps on the same domain never see it.
- `/healthz` (outside the prefix) is used by the Docker health check.

## Database

| Table | Purpose |
|---|---|
| `users`, `sessions` | family logins; sessions store only a SHA-256 of the cookie token |
| `categories` | seeded with 9 household categories (editable) |
| `assets` | product, purchase, manufacturer warranty, extended warranty / AMC, status |
| `attachments` | invoice, warranty card, photos, manuals (metadata + OCR text; files on the volume) |
| `service_records` | repairs, services, warranty claims with cost and complaint number |
| `reminder_log` | one row per reminder sent, so nothing is sent twice |
| `audit_log` | logins, creates, deletes |
| `schema_migrations` | applied migration versions |

**Warranty rule:** expiry = start + N months − 1 day. For example, 12 months from 15 Aug 2025 runs to 14 Aug 2026. The start is the purchase date unless you set an installation date. An extended warranty starts the day after the manufacturer warranty ends. You can also type an exact expiry date.

**Schema changes:** add `backend/migrations/0002_something.sql`. It is applied once on the next start, inside an advisory lock.

## Reminders

- Every day at `REMINDER_HOUR` (IST), warranties at 30, 7 and 0 days before expiry are collected into **one digest**.
- Only the closest tier is sent. If you add an item with 5 days left, you get the 7-day reminder, not three messages.
- If the Pi was off at 9 am, the next run catches up.
- **Email:** set `SMTP_*`. For Gmail, use an App Password with `smtp.gmail.com:587`.
- **Phone push:** set `NTFY_URL=https://ntfy.sh/<long-random-topic>` (or your own ntfy server) and subscribe in the ntfy app.
- To test, use **Settings → Send test notification** or **Send due reminders now** (admin only). You can also run `docker compose exec app python -m app.cli send-reminders`.

## Backups

```bash
chmod +x scripts/backup.sh
crontab -e
30 2 * * * /home/pi/home-inventory/scripts/backup.sh >> /home/pi/home-inventory/backups/backup.log 2>&1
```

This dumps only `home_inventory` (`pg_dump -Fc`) and tars `data/uploads`, keeping 14 days. Restore steps are at the bottom of the script. **Always back up the database and the uploads together.**

## Security notes

- Every `/api` route except `login` and `health` requires a session. Invoice files are served only through an authenticated endpoint, never as a static folder.
- Uploads are checked by **content** (magic bytes), not by extension. Only JPEG/PNG/WEBP/HEIC/PDF are allowed, up to 20 MB.
- Photos are re-encoded, which strips EXIF data such as GPS location. HEIC is converted to JPEG, and images larger than 3000 px are downscaled.
- State-changing requests must send `X-Requested-With: fetch`. Combined with the SameSite cookie, this blocks CSRF.
- Security headers include a strict CSP, `nosniff`, `frame-ancestors 'self'` and `noindex`.
- After 5 failed logins for an account, or 20 from one IP, the account or IP is locked out for 15 minutes.
- Abandoned draft uploads are purged after 24 hours.

## Local development

```bash
# backend (needs a Postgres you can reach)
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
DB_HOST=127.0.0.1 DB_PASSWORD=… COOKIE_SECURE=false UPLOAD_DIR=./uploads ADMIN_EMAIL=me@x.com ADMIN_PASSWORD='Dev#Pass1234' \
  uvicorn app.main:application --reload --port 8000
# frontend (hot reload at http://localhost:5173, API proxied to :8000/inventory)
cd frontend && npm install && npm run dev
# end-to-end API test (after `npm run build && cp -r dist ../backend/static`)
python scripts/smoke_test.py http://localhost:8000/inventory me@x.com 'Dev#Pass1234'
```

## Resource use on a Pi 5

The app idles at roughly 120–180 MB RAM. OCR of a phone photo takes about 3–8 s on the Pi 5, and only one OCR job runs at a time. Invoices take about 0.3–1.5 MB each after re-encoding.
