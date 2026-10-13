# Self-hosted application

## Inventory
| Application | Path | What it is | Stack | Database | Access |
| ----- | ------ | ----- | ----- | ----- | ----- |
| Finance tracker | ./apps/ft-claude | Household income, expenses, investments, subscriptions and savings plan | FastAPI + React (Vite, Tailwind, Recharts) | Shared Postgres (`shared-postgres`) | `127.0.0.1:8090`, public via shared Caddy |
| Home Inventory | ./apps/home-inventory | Purchases, invoices (OCR), warranties and expiry reminders | FastAPI + React, Tesseract OCR, APScheduler | Shared Postgres (`shared-postgres`) | `https://apps.tinyserverlab.in/inventory` via shared Caddy |
| Personal finance tracker (ChatGPT build) | ./apps/pft-chatgpt | Alternative household finance tracker | FastAPI + server-rendered templates | Own Postgres container (`127.0.0.1:5434`) | `127.0.0.1:8080`, public via Cloudflare Tunnel |
| Household Ledger *(archived)* | ./archive/expense-manager | Earlier finance tracker, formerly at the repo root; kept for reference, not deployed | FastAPI + static JS (Chart.js) | Own Postgres container | — |

All apps target a Raspberry Pi 5 (ARM64) with Docker Compose, bind only to
`127.0.0.1`, and are reached from outside through Cloudflare Tunnel or the
shared Caddy reverse proxy. See each app's own README for setup.

## Changelog

Newest first. Append new entries at the top of this list.

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
