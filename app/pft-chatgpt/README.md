# Self-hosted Personal Finance Tracker

A lightweight household finance tracker designed for **Raspberry Pi 5 (8GB), ARM64, Docker Compose and Cloudflare Tunnel**.

## Architecture

```text
                         Internet
                            |
                    Cloudflare Edge
                            |
                  Cloudflare Access + MFA
                            |
                    Existing cloudflared
                     (Pi host process)
                            |
                  http://127.0.0.1:8080
                            |
                    +----------------+
                    | Finance API/UI |
                    | FastAPI        |
                    | 384 MB limit   |
                    +-------+--------+
                            |
                    Docker bridge network
                            |
                  +---------+---------+
                  |                   |
           +------+-----+       +-----+------+
           | PostgreSQL |       | Nightly    |
           | 16-alpine |       | backup     |
           | 512 MB    |       | 96 MB      |
           +-----+-----+       +-----+------+
                 |                    |
           Docker volume        ./data/backups
           postgres_data        local .dump.gz
                 |
             host port
          127.0.0.1:5434
```

The app is the only HTTP service. PostgreSQL is bound to **127.0.0.1:5434**, so it is not exposed to the LAN or Internet. Cloudflare Tunnel is expected to run on the Pi host and point to `http://127.0.0.1:8080`.

## Features

- Email/password login with HttpOnly JWT cookie.
- 7-day JWT lifetime; active requests refresh the token.
- No public signup.
- First admin user seeded from `.env`.
- Multiple named household users.
- Expense/income categories.
- Payment sources with optional opening/running balance.
- Income/expense transactions.
- Current-month dashboard with date range picker.
- Category expense pie/donut chart rendered without a JS chart dependency.
- Income, expense, net savings and net-worth cards.
- Savings/investment entries for Equity, Mutual Funds, FD, PPF and Others.
- CSV and PDF report exports.
- Nightly compressed PostgreSQL backups, configurable retention.
- Manual backup/restore scripts.
- No cloudflared container.
- ARM64-friendly official base images.
- One-command start/update after cloning.

## Deploy on Raspberry Pi 5

```bash
git clone <YOUR-GIT-URL> personal-finance-tracker
cd personal-finance-tracker
cp .env.example .env
nano .env
docker compose up -d --build
docker compose ps
```

Open locally for first test:

`http://127.0.0.1:8080`

The PostgreSQL host port is:

`127.0.0.1:5434`

The application itself uses PostgreSQL's internal Docker port 5432.

## Updating

```bash
cd personal-finance-tracker
git pull
docker compose up -d --build
```

Database data survives image rebuilds because it is in the `postgres_data` Docker volume.

## Cloudflare

Because `cloudflared` already runs on the Pi host, do not add it to this Compose file.

Add this ingress to the existing tunnel:

```yaml
ingress:
  - hostname: finance.example.com
    service: http://127.0.0.1:8080
  - service: http_status:404
```

Then create a Cloudflare Zero Trust Access application for the hostname and allow only the household identities you choose. Enable MFA through your identity provider/Access policy.

The application login remains enabled even behind Access: this is intentional defense in depth.

## Backups

Nightly backup runs at approximately 02:30 local Pi time.

Files are stored under:

```text
data/backups/
```

Default retention is 14 days.

Manual backup:

```bash
./scripts/backup-now.sh
```

Restore:

```bash
docker compose stop app backup
./scripts/restore.sh data/backups/finance-YYYYMMDD-HHMMSS.dump.gz
```

For offsite backup, sync `data/backups/` to another trusted storage target. Do not put database credentials in Git.

## Security notes

1. Generate a long random `APP_SECRET`.
2. Use a long random PostgreSQL password.
3. Change the seeded admin password after first login.
4. Keep `.env` out of Git.
5. Keep PostgreSQL bound to `127.0.0.1:5434`.
6. Use Cloudflare Access + MFA in front of the tunnel.
7. Do not expose port 8080 or 5434 through router port forwarding.
8. Review backups periodically by doing a test restore.
9. This is a household application, not a bank-grade accounting system.

## Resource target

Compose limits are intentionally conservative:

- App: 384 MB
- PostgreSQL: 512 MB
- Backup: 96 MB
- Total container memory limits: ~992 MB

Actual usage depends on database size, PostgreSQL cache behavior and traffic. The limits leave headroom below the requested 1.5 GB container footprint.

## Project layout

```text
.
├── app/
│   ├── main.py
│   ├── templates/index.html
│   └── static/
├── data/backups/
├── scripts/
│   ├── backup-loop.sh
│   ├── backup-now.sh
│   └── restore.sh
├── cloudflare-tunnel.example.yml
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```
