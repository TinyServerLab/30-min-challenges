# Self-hosted application

## Inventory
| Application | Path | What it is | Stack | Database | Access |
| ----- | ------ | ----- | ----- | ----- | ----- |
| Finance tracker | ./apps/ft-claude | Household income, expenses, investments, subscriptions and savings plan | FastAPI + React (Vite, Tailwind, Recharts) | Shared Postgres (`shared-postgres`) | `https://apps.tinyserverlab.in/finance` via shared Caddy (`127.0.0.1:8090` direct) |
| Home Inventory | ./apps/home-inventory | Purchases, invoices (OCR), warranties and expiry reminders | FastAPI + React, Tesseract OCR, APScheduler | Shared Postgres (`shared-postgres`) | `https://apps.tinyserverlab.in/inventory` via shared Caddy |
| Personal finance tracker (ChatGPT build) | ./apps/pft-chatgpt | Alternative household finance tracker | FastAPI + server-rendered templates | Own Postgres container (`127.0.0.1:5434`) | `127.0.0.1:8080`, public via Cloudflare Tunnel |
| Household Ledger *(archived)* | ./archive/expense-manager | Earlier finance tracker, formerly at the repo root; kept for reference, not deployed | FastAPI + static JS (Chart.js) | Own Postgres container | — |

All apps target a Raspberry Pi 5 (ARM64) with Docker Compose, bind only to
`127.0.0.1`, and are reached from outside through Cloudflare Tunnel or the
shared Caddy reverse proxy. See each app's own README for setup.

## Changelog

Newest first. Append new entries at the top of this list.

### 2026-10-31 — Home Inventory: option to split off the shared database
- New `apps/home-inventory/docker-compose-standalone.yml`, same pattern as
  the Finance tracker's: an extra `db` service running its own Postgres
  instead of reusing `shared-postgres`. `docker-compose.yml` (the default,
  shared-DB setup) is unchanged — this is only for when you want to pull an
  app off the shared database.
- **Upgrade step:** none for the default setup. To switch an existing
  install, dump the `home_inventory` database from shared-postgres, restore
  it into the new `db` service, then swap the compose file in. A fresh
  install just needs `docker compose -f docker-compose-standalone.yml up -d
  --build` — the app creates its own schema, no dump needed.

### 2026-10-31 — Home Inventory: per-user currency + account removal
- Settings → profile now has a currency picker. It's a label only — it sets
  the default currency for assets that user adds next; nothing already saved
  is converted or re-labeled.
- Settings → profile has "Delete my account" (asks for your password first).
  Settings → Family members has "Remove" per family member. Either way, the
  person's assets stay, just without their name attached. The first account
  ever created can't be removed by either path, so the household can't lock
  itself out.
- **Upgrade step:** `docker compose up -d --build` in `apps/home-inventory` —
  the new `currency` column is applied automatically on startup (migration
  `0003_user_currency`), defaulting every existing account to `INR`.

### 2026-10-22 — Finance tracker: works behind Caddy at /finance
- The app assumed it was served at the site root, so through
  `https://apps.tinyserverlab.in/finance` its scripts and API calls went to
  `/assets/…` and `/api/…` outside the `/finance*` route, and the page was blank.
- New `BASE_PATH` setting (default `/finance` in `docker-compose.yml`). The
  frontend uses relative asset URLs and takes its API and router prefix
  from a `<base>` tag filled in by the backend, so the same image works at
  `/finance` or at the root. Same approach as Home Inventory.
- **Upgrade step:** `docker compose up -d --build` in `apps/ft-claude`. Keep
  Caddy's `handle /finance*` (not `handle_path`). Log in again on the new
  hostname, because saved logins are kept per site.

### 2026-10-13 — Home Inventory: moved to the shared apps hostname
- Now served at `https://apps.tinyserverlab.in/inventory` (was
  `home.tinyserverlab.in`). Updated the Caddy site address, the default
  `PUBLIC_URL` (used in reminder links), `.env.example` and the docs.
- **Upgrade step:** update the site block in the live Caddyfile and reload
  Caddy. Set `PUBLIC_URL` in the Pi's `.env` if it's set there. Route
  `apps.tinyserverlab.in` to Caddy in the Cloudflare Tunnel.

### 2026-10-13 — Finance tracker: subscription manager + savings plan
- **Subscriptions page:** track each subscription's amount, billing cycle
  (weekly/monthly/quarterly/yearly), next due date, category, payment source
  and a usage rating (essential / regular / rarely / unused).
  - Summary cards: active count, monthly and yearly cost, and how much
    you'd save by cancelling the subscriptions you rarely or never use.
  - Renewals due in the next 30 days.
  - **Mark paid** logs the expense and moves the due date forward one cycle.
  - Pause, resume and cancel (cancelled ones keep their history).
  - Finds repeated expenses in the last 6 months that look like untracked
    subscriptions, with a one-click **Track**.
- **Savings plan page:** averages the last 1–12 full months of spending and
  suggests:
  1. cancelling subscriptions you rarely or never use,
  2. trimming non-essential categories by 10–50% with a suggested monthly
     cap you can adopt or edit.
  - Shows the current vs. projected savings rate.
  - Tracks this month's spending against each adopted cap.
- **Categories:** new "Essential" flag. Only non-essential categories are
  targeted by the savings plan.
- **Upgrade step for an existing database:** apply
  `apps/ft-claude/backend/scripts/migrations/001_subscriptions_savings.sql`
  once (see `apps/ft-claude/README.md`, "Schema changes for an existing
  database").
