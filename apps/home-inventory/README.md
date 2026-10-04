# Home Asset + Warranty

A self-hosted household app for purchases, invoices, warranties and reminders. It runs on a Raspberry Pi 5 with Docker, alongside your **existing shared PostgreSQL and Caddy**. It serves from `https://apps.tinyserverlab.in/inventory`.

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

**5. First sign-in.** Open `https://apps.tinyserverlab.in/inventory`, sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`, then **delete `ADMIN_PASSWORD` from `.env`**. It is only used when the users table is empty.

### Adding family members (no public sign-up)

Add them under **Settings → Family members**, or from the command line:

```bash
docker compose exec app python -m app.cli create-user --email joe@example.com --name "Joe" --username Joe
docker compose exec app python -m app.cli create-user --email me@example.com --name TSL --admin
docker compose exec app python -m app.cli reset-password --email joe@example.com
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
| `reminder_log` | one row per reminder sent per channel, so nothing is sent twice |
| `notification_channels` | on/off switch, Discord/Telegram settings and last delivery status per channel |
| `audit_log` | logins, creates, deletes |
| `schema_migrations` | applied migration versions |

**Warranty rule:** expiry = start + N months − 1 day. For example, 12 months from 15 Aug 2025 runs to 14 Aug 2026. The start is the purchase date unless you set an installation date. An extended warranty starts the day after the manufacturer warranty ends. You can also type an exact expiry date.

**Schema changes:** add `backend/migrations/0002_something.sql`. It is applied once on the next start, inside an advisory lock.

## Reminders & notifications

- Every day at `REMINDER_HOUR` (IST), warranties at 30, 7 and 0 days before expiry are collected into **one digest per channel**.
- Only the closest tier is sent. If you add an item with 5 days left, you get the 7-day reminder, not three messages.
- Nothing is sent twice on the same channel. If the Pi was off at 9 am, the next run catches up, and a channel you switch on later still receives what is currently due.

**Settings → Notifications** has an on/off switch, a status line (last delivery or the last error) and a **Test** button for each channel. Only admins can change them.

| Channel | Where it's set up |
|---|---|
| **Telegram** | In the app. Create a bot with **@BotFather** (`/newbot`) and paste the token. Open the bot and press **Start**, or add it to your family group and send a message. Then click **Find my chat** and pick the chat. |
| **Discord** | In the app. In Discord go to **Server Settings → Integrations → Webhooks → New Webhook**, pick a channel, copy the URL and paste it. You can optionally ping `@here`, `@everyone`, a role (`<@&id>`) or a person (`<@id>`). |
| **Email** | `.env`: set `SMTP_*`. For Gmail, use an App Password with `smtp.gmail.com:587`. Each user can opt out under their profile. |
| **ntfy push** | `.env`: set `NTFY_URL=https://ntfy.sh/<long-random-topic>` and subscribe in the ntfy app. |

- The Discord webhook URL and Telegram bot token are stored in the `home_inventory` database. They are only ever shown masked in the browser and are kept out of the logs.
- The Pi needs outbound HTTPS to `discord.com` and `api.telegram.org`.
- Asset names are escaped, so an item called "@everyone" can't ping your server.
- Long digests are split automatically to fit Discord's and Telegram's message limits.
- **Send due reminders now** (admin) runs the daily job immediately. You can also run `docker compose exec app python -m app.cli send-reminders`.

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
# Discord/Telegram tests against fake servers (fresh database; run from backend/)
cd backend && python ../scripts/test_notifications.py
```

## Resource use on a Pi 5

The app idles at roughly 120–180 MB RAM. OCR of a phone photo takes about 3–8 s on the Pi 5, and only one OCR job runs at a time. Invoices take about 0.3–1.5 MB each after re-encoding.
