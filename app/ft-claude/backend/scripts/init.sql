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

-- Starter categories/sources so the app isn't empty on first login.
-- Household members can edit or delete these freely afterward.
INSERT INTO categories (name, type, icon, color) VALUES
    ('Groceries', 'expense', 'cart', '#f97316'),
    ('Rent', 'expense', 'home', '#ef4444'),
    ('Utilities', 'expense', 'bolt', '#eab308'),
    ('Dining Out', 'expense', 'utensils', '#f59e0b'),
    ('Transport', 'expense', 'car', '#3b82f6'),
    ('Healthcare', 'expense', 'pill', '#ec4899'),
    ('Entertainment', 'expense', 'film', '#a855f7'),
    ('Shopping', 'expense', 'bag', '#14b8a6'),
    ('Other Expense', 'expense', 'box', '#64748b'),
    ('Salary', 'income', 'briefcase', '#22c55e'),
    ('Freelance', 'income', 'laptop', '#06b6d4'),
    ('Interest', 'income', 'bank', '#84cc16'),
    ('Other Income', 'income', 'plus', '#10b981')
ON CONFLICT (name, type) DO NOTHING;

INSERT INTO payment_sources (name, kind, running_balance) VALUES
    ('Cash', 'cash', 0),
    ('Primary Bank Account', 'bank_account', 0),
    ('Credit Card', 'credit_card', 0),
    ('UPI', 'upi', 0)
ON CONFLICT (name) DO NOTHING;
