-- =============================================================================
-- 0001_initial — Home Asset + Warranty schema
-- Applied automatically by the app on startup (tracked in schema_migrations).
-- Runs inside the dedicated `home_inventory` database only.
-- =============================================================================

-- ---------------------------------------------------------------- users & auth
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT        NOT NULL,
    username        TEXT,
    display_name    TEXT        NOT NULL,
    password_hash   TEXT        NOT NULL,
    is_admin        BOOLEAN     NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    notify_email    BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);
CREATE UNIQUE INDEX users_email_uq    ON users (lower(email));
CREATE UNIQUE INDEX users_username_uq ON users (lower(username)) WHERE username IS NOT NULL;

-- Server-side sessions: the cookie holds a random token, the DB stores its SHA-256.
CREATE TABLE sessions (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash    TEXT        NOT NULL UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL,
    user_agent    TEXT,
    ip_address    TEXT
);
CREATE INDEX sessions_user_idx    ON sessions (user_id);
CREATE INDEX sessions_expires_idx ON sessions (expires_at);

-- ------------------------------------------------------------------ reference
CREATE TABLE categories (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT    NOT NULL,
    icon        TEXT    NOT NULL DEFAULT 'box',
    color       TEXT    NOT NULL DEFAULT '#64748b',
    sort_order  INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX categories_name_uq ON categories (lower(name));

-- Colours: validated categorical palette (fixed order, colour-blind separated); "Others" is neutral gray.
INSERT INTO categories (name, icon, color, sort_order) VALUES
    ('Mobiles & Tablets',   'smartphone',     '#2a78d6', 10),
    ('Computers & Laptops', 'laptop',         '#eb6834', 20),
    ('TV & Audio',          'tv',             '#1baf7a', 30),
    ('Kitchen Appliances',  'microwave',      '#eda100', 40),
    ('Home Appliances & AC','washing',        '#e87ba4', 50),
    ('Furniture',           'sofa',           '#008300', 60),
    ('Vehicles',            'car',            '#4a3aa7', 70),
    ('Tools & Hardware',    'wrench',         '#e34948', 80),
    ('Others',              'box',            '#64748b', 999);

-- --------------------------------------------------------------------- assets
CREATE TABLE assets (
    id                          BIGSERIAL PRIMARY KEY,
    name                        TEXT          NOT NULL,
    brand                       TEXT,
    model                       TEXT,
    serial_number               TEXT,
    category_id                 BIGINT        REFERENCES categories(id) ON DELETE SET NULL,
    location                    TEXT,                          -- room / where it is kept
    owner_name                  TEXT,                          -- family member who uses it

    -- purchase
    purchase_date               DATE          NOT NULL,
    purchase_price              NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (purchase_price >= 0),
    currency                    CHAR(3)       NOT NULL DEFAULT 'INR',
    vendor                      TEXT,                          -- store / website
    invoice_number              TEXT,
    payment_method              TEXT,

    -- manufacturer warranty
    warranty_months             INTEGER       NOT NULL DEFAULT 12 CHECK (warranty_months >= 0),
    warranty_start_date         DATE,                          -- NULL => purchase_date
    warranty_expiry_date        DATE,                          -- computed by app from start + months
    warranty_expiry_manual      BOOLEAN       NOT NULL DEFAULT FALSE,  -- TRUE => expiry typed in by user

    -- optional extended warranty / AMC
    ext_warranty_provider       TEXT,
    ext_warranty_months         INTEGER       CHECK (ext_warranty_months IS NULL OR ext_warranty_months >= 0),
    ext_warranty_expiry_date    DATE,
    ext_warranty_cost           NUMERIC(12,2) CHECK (ext_warranty_cost IS NULL OR ext_warranty_cost >= 0),

    support_contact             TEXT,                          -- service centre phone / URL
    status                      TEXT          NOT NULL DEFAULT 'active'
                                   CHECK (status IN ('active','in_repair','disposed','sold','lost','gifted')),
    notes                       TEXT,

    created_by                  BIGINT        REFERENCES users(id) ON DELETE SET NULL,
    updated_by                  BIGINT        REFERENCES users(id) ON DELETE SET NULL,
    created_at                  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX assets_category_idx      ON assets (category_id);
CREATE INDEX assets_purchase_date_idx ON assets (purchase_date);
CREATE INDEX assets_warranty_idx      ON assets (warranty_expiry_date);
CREATE INDEX assets_ext_warranty_idx  ON assets (ext_warranty_expiry_date);
CREATE INDEX assets_status_idx        ON assets (status);

-- Effective warranty end = later of manufacturer and extended warranty
CREATE VIEW asset_warranty AS
SELECT a.id AS asset_id,
       GREATEST(a.warranty_expiry_date, a.ext_warranty_expiry_date) AS effective_expiry_date
FROM assets a;

-- ---------------------------------------------------------------- attachments
-- Files live on the uploads volume; only metadata is stored here.
CREATE TABLE attachments (
    id                 BIGSERIAL PRIMARY KEY,
    asset_id           BIGINT      REFERENCES assets(id) ON DELETE CASCADE,  -- NULL while a draft upload
    kind               TEXT        NOT NULL DEFAULT 'invoice'
                          CHECK (kind IN ('invoice','warranty_card','photo','manual','receipt','other')),
    original_filename  TEXT        NOT NULL,
    stored_path        TEXT        NOT NULL UNIQUE,     -- relative to UPLOAD_DIR
    thumb_path         TEXT,
    content_type       TEXT        NOT NULL,
    size_bytes         BIGINT      NOT NULL,
    sha256             TEXT        NOT NULL,
    ocr_text           TEXT,
    uploaded_by        BIGINT      REFERENCES users(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX attachments_asset_idx ON attachments (asset_id);
CREATE INDEX attachments_sha_idx   ON attachments (sha256);

-- ------------------------------------------------------------ service history
CREATE TABLE service_records (
    id               BIGSERIAL PRIMARY KEY,
    asset_id         BIGINT        NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    service_date     DATE          NOT NULL,
    kind             TEXT          NOT NULL DEFAULT 'repair'
                        CHECK (kind IN ('repair','service','claim','installation','other')),
    description      TEXT          NOT NULL,
    vendor           TEXT,
    cost             NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (cost >= 0),
    under_warranty   BOOLEAN       NOT NULL DEFAULT FALSE,
    reference_number TEXT,                                 -- complaint / ticket no.
    created_by       BIGINT        REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX service_records_asset_idx ON service_records (asset_id);
CREATE INDEX service_records_date_idx  ON service_records (service_date);

-- ---------------------------------------------------------------- reminders
-- One row per reminder actually sent, so a reminder never goes out twice.
CREATE TABLE reminder_log (
    id             BIGSERIAL PRIMARY KEY,
    asset_id       BIGINT      NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    warranty_type  TEXT        NOT NULL CHECK (warranty_type IN ('manufacturer','extended')),
    expiry_date    DATE        NOT NULL,
    days_before    INTEGER     NOT NULL,
    channel        TEXT        NOT NULL,
    sent_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, warranty_type, expiry_date, days_before, channel)
);

-- ------------------------------------------------------------------ audit trail
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT        NOT NULL,     -- e.g. asset.create, login.failed
    entity      TEXT,
    entity_id   BIGINT,
    detail      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_created_idx ON audit_log (created_at DESC);

-- ------------------------------------------------------------ updated_at trigger
CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

CREATE TRIGGER users_updated_at  BEFORE UPDATE ON users  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER assets_updated_at BEFORE UPDATE ON assets FOR EACH ROW EXECUTE FUNCTION set_updated_at();
