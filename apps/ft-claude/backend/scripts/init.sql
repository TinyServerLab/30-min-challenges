-- Runs once, automatically, on first Postgres container start
-- (docker-entrypoint-initdb.d). Compose only triggers it on an empty
-- data volume, so schema changes later require a manual migration.

CREATE TYPE txn_type AS ENUM ('income', 'expense');
CREATE TYPE source_kind AS ENUM ('cash', 'bank_account', 'credit_card', 'upi', 'wallet');
CREATE TYPE investment_kind AS ENUM ('equity', 'mutual_fund', 'fd', 'ppf', 'other');

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255) NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS categories (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    type       txn_type NOT NULL,
    icon       VARCHAR(50)  DEFAULT '',
    color      VARCHAR(20)  DEFAULT '#64748b',
    essential  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, type)
);

CREATE TABLE IF NOT EXISTS payment_sources (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    kind            source_kind NOT NULL,
    running_balance NUMERIC(14, 2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount      NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    txn_date    DATE NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    source_id   INTEGER NOT NULL REFERENCES payment_sources(id) ON DELETE RESTRICT,
    type        txn_type NOT NULL,
    note        TEXT DEFAULT '',
    recurring   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions (txn_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions (category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions (source_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions (user_id);

CREATE TABLE IF NOT EXISTS investments (
    id                   SERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind                 investment_kind NOT NULL,
    label                VARCHAR(150) NOT NULL,
    contribution_amount  NUMERIC(14, 2) NOT NULL DEFAULT 0,
    current_value        NUMERIC(14, 2) NOT NULL DEFAULT 0,
    entry_date           DATE NOT NULL,
    note                 TEXT DEFAULT '',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_investments_user ON investments (user_id);

CREATE TYPE billing_cycle AS ENUM ('weekly', 'monthly', 'quarterly', 'yearly');
CREATE TYPE subscription_status AS ENUM ('active', 'paused', 'cancelled');
CREATE TYPE subscription_usage AS ENUM ('essential', 'regular', 'rarely', 'unused');

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

-- Monthly limits adopted from the savings plan, one per expense category.
CREATE TABLE IF NOT EXISTS spending_caps (
    id             SERIAL PRIMARY KEY,
    category_id    INTEGER NOT NULL UNIQUE REFERENCES categories(id) ON DELETE CASCADE,
    monthly_limit  NUMERIC(14, 2) NOT NULL CHECK (monthly_limit > 0),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Starter categories/sources so the app isn't empty on first login.
-- Household members can edit or delete these freely afterward.
INSERT INTO categories (name, type, icon, color, essential) VALUES
    ('Groceries', 'expense', 'cart', '#f97316', TRUE),
    ('Rent', 'expense', 'home', '#ef4444', TRUE),
    ('Utilities', 'expense', 'bolt', '#eab308', TRUE),
    ('Dining Out', 'expense', 'utensils', '#f59e0b', FALSE),
    ('Transport', 'expense', 'car', '#3b82f6', TRUE),
    ('Healthcare', 'expense', 'pill', '#ec4899', TRUE),
    ('Entertainment', 'expense', 'film', '#a855f7', FALSE),
    ('Shopping', 'expense', 'bag', '#14b8a6', FALSE),
    ('Subscriptions', 'expense', 'repeat', '#8b5cf6', FALSE),
    ('Other Expense', 'expense', 'box', '#64748b', TRUE),
    ('Salary', 'income', 'briefcase', '#22c55e', TRUE),
    ('Freelance', 'income', 'laptop', '#06b6d4', TRUE),
    ('Interest', 'income', 'bank', '#84cc16', TRUE),
    ('Other Income', 'income', 'plus', '#10b981', TRUE)
ON CONFLICT (name, type) DO NOTHING;

INSERT INTO payment_sources (name, kind, running_balance) VALUES
    ('Cash', 'cash', 0),
    ('Primary Bank Account', 'bank_account', 0),
    ('Credit Card', 'credit_card', 0),
    ('UPI', 'upi', 0)
ON CONFLICT (name) DO NOTHING;
