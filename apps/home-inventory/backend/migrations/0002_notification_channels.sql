-- =============================================================================
-- 0002_notification_channels — per-channel on/off switch, settings and health
-- Email and ntfy keep their connection settings in .env; Discord and Telegram are
-- configured from Settings → Notifications and stored in `config`.
-- =============================================================================

CREATE TABLE notification_channels (
    channel          TEXT        PRIMARY KEY
                        CHECK (channel IN ('email', 'ntfy', 'discord', 'telegram')),
    enabled          BOOLEAN     NOT NULL DEFAULT FALSE,
    config           JSONB       NOT NULL DEFAULT '{}'::jsonb,   -- discord: webhook_url, mention
                                                                 -- telegram: bot_token, chat_id
    last_attempt_at  TIMESTAMPTZ,
    last_ok          BOOLEAN,
    last_error       TEXT,
    updated_by       BIGINT      REFERENCES users(id) ON DELETE SET NULL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- email/ntfy stay ON so existing .env-based reminders keep working after the upgrade
INSERT INTO notification_channels (channel, enabled) VALUES
    ('email',    TRUE),
    ('ntfy',     TRUE),
    ('discord',  FALSE),
    ('telegram', FALSE);

CREATE TRIGGER notification_channels_updated_at
    BEFORE UPDATE ON notification_channels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
