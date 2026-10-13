-- Subscription manager + savings plan.
--
-- init.sql only runs on an empty data volume, so an existing database
-- (including the shared-postgres setup) needs this applied once by hand:
--
--   docker exec -i shared-postgres psql -U finance_db_user -d finance_db \
--     < backend/scripts/migrations/001_subscriptions_savings.sql
--
-- Safe to re-run: every step checks before it creates.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'categories' AND column_name = 'essential'
    ) THEN
        ALTER TABLE categories ADD COLUMN essential BOOLEAN NOT NULL DEFAULT TRUE;
        -- Only on first add, so re-running never overwrites a household's
        -- own essential/discretionary choices.
        UPDATE categories SET essential = FALSE
        WHERE type = 'expense' AND name IN ('Dining Out', 'Entertainment', 'Shopping');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'billing_cycle') THEN
        CREATE TYPE billing_cycle AS ENUM ('weekly', 'monthly', 'quarterly', 'yearly');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_status') THEN
        CREATE TYPE subscription_status AS ENUM ('active', 'paused', 'cancelled');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_usage') THEN
        CREATE TYPE subscription_usage AS ENUM ('essential', 'regular', 'rarely', 'unused');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS subscriptions (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name           VARCHAR(150) NOT NULL,
    amount         NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    billing_cycle  billing_cycle NOT NULL DEFAULT 'monthly',
    next_due_date  DATE NOT NULL,
    category_id    INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    source_id      INTEGER REFERENCES payment_sources(id) ON DELETE SET NULL,
    status         subscription_status NOT NULL DEFAULT 'active',
    usage          subscription_usage NOT NULL DEFAULT 'regular',
    note           TEXT DEFAULT '',
    cancelled_on   DATE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_status_due ON subscriptions (status, next_due_date);

CREATE TABLE IF NOT EXISTS spending_caps (
    id             SERIAL PRIMARY KEY,
    category_id    INTEGER NOT NULL UNIQUE REFERENCES categories(id) ON DELETE CASCADE,
    monthly_limit  NUMERIC(14, 2) NOT NULL CHECK (monthly_limit > 0),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A default home for subscription charges; discretionary so the savings
-- plan considers it. Skipped if the household already has one.
INSERT INTO categories (name, type, icon, color, essential)
VALUES ('Subscriptions', 'expense', 'repeat', '#8b5cf6', FALSE)
ON CONFLICT (name, type) DO NOTHING;
