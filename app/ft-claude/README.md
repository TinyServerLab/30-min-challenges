# Personal Finance Tracker

Self-hosted household finance tracker for a Raspberry Pi 5, deployed with
Docker Compose and exposed only through an existing Cloudflare Tunnel. No
ports are forwarded on the router; nothing is reachable on the LAN except
through `cloudflared`.

## Stack

| Layer     | Choice                                                        |
|-----------|-----------------------------------------------------------------|
| Backend   | FastAPI (Python 3.12), SQLAlchemy, JWT auth (access + refresh) |
| Frontend  | React + Vite + Tailwind + Recharts, built to static files and served **by the same FastAPI process** (no separate web server) |
| Database  | Postgres 16 (`postgres:16-alpine`), ARM64-native                |
| Backups   | Alpine + cron sidecar, nightly `pg_dump` → gzip → local disk, optional `rclone` offsite mirror |
| Ingress   | Your existing host-level `cloudflared` — no container, no port-forwarding |

Full diagram: [`docs/architecture.md`](docs/architecture.md).

Everything binds to `127.0.0.1` only — three containers (`db`, `app`,
`backup`), no nginx, no extra frontend runtime. Soft memory limits total
~1GB, under your 1.5GB target with headroom.

## 1. Get the code onto the Pi

```bash
# On your dev machine: push this folder to a new GitHub repo, then...
git clone https://github.com/<you>/finance-tracker.git
cd finance-tracker
```

(Or `scp -r` the folder directly to the Pi if you'd rather skip git.)

## 2. Configure secrets

```bash
cp .env.example .env
nano .env
```

Fill in at minimum:
- `POSTGRES_PASSWORD` — any long random string
- `JWT_SECRET` — generate with `openssl rand -hex 32`
- `CORS_ORIGINS` — your public domain, e.g. `https://finance.yourdomain.tld`
  (harmless in production since the frontend is served same-origin, but
  keep it correct for local dev against `npm run dev`)

## 3. Build and start

```bash
docker compose up -d --build
```

First boot creates the `finance` database and schema automatically via
`backend/scripts/init.sql` (Postgres only runs init scripts against an
empty data volume — re-running `up` later won't re-seed it).

Check everything is healthy:

```bash
docker compose ps
curl http://127.0.0.1:8090/api/health   # -> {"status":"ok"}
```

## 4. Create logins for the household

There's no self-registration by design — seed each person from the host:

```bash
docker compose exec app python scripts/seed_admin.py \
  --email you@example.com --name "Sathya" --password 'choose-a-strong-password'

docker compose exec app python scripts/seed_admin.py \
  --email spouse@example.com --name "Spouse Name" --password 'another-strong-password'
```

Re-running with the same email updates that person's name/password
instead of duplicating them.

## 5. Wire up the Cloudflare Tunnel

You said `cloudflared` is already running at the host level — just add
one ingress rule pointing your chosen subdomain at the app's published
localhost port. See [`cloudflare/config.yml.example`](cloudflare/config.yml.example)
for the exact snippet, then:

```bash
sudo systemctl restart cloudflared   # or however you manage it
```

For the second layer of defense, add a Cloudflare Access policy
restricting that hostname to your household's email addresses (also
documented in the same file).

## 6. Updating later

```bash
git pull
docker compose up -d --build
```

This is the one-command update path — Compose rebuilds only what
changed and restarts in place. The `db` volume (and your data) is
untouched by rebuilds.

## Backups

- Nightly, automatic, no setup required: the `backup` container dumps
  Postgres to `./backups/finance_<timestamp>.sql.gz` on the Pi's local
  disk every night at 02:30 and prunes anything older than
  `BACKUP_RETENTION_DAYS` (default 14).
- Restore a dump:
  ```bash
  gunzip -c backups/finance_20260917_023000.sql.gz | \
    docker compose exec -T db psql -U finance_app -d finance
  ```
- Optional offsite copy: set `RCLONE_REMOTE` in `.env` to a remote you've
  configured (`docker compose exec backup rclone config`, one-time), and
  every nightly run also mirrors to it.
- Run a backup on demand: `docker compose exec backup /app/backup.sh`

## Local development (optional)

You don't need this on the Pi — it's only for iterating on the frontend
with hot reload against a local backend:

```bash
docker compose up -d db          # just the database
cd backend && pip install -r requirements.txt
DATABASE_URL=postgresql+psycopg://finance_app:<pw>@localhost:5434/finance \
  JWT_SECRET=dev-secret uvicorn app.main:app --reload
# in another terminal
cd frontend && npm install && npm run dev   # http://localhost:5173, proxies /api to :8000
```

## Repo layout

```
finance-tracker/
├── docker-compose.yml
├── .env.example
├── backend/            # FastAPI app (also serves the built frontend)
│   ├── Dockerfile      # multi-stage: builds frontend, then Python image
│   ├── app/
│   └── scripts/        # init.sql, seed_admin.py
├── frontend/           # React + Vite + Tailwind SPA
├── backup/             # cron + pg_dump sidecar
├── cloudflare/          # ingress config snippet
└── docs/architecture.md
```
