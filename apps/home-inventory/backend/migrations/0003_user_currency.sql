-- =============================================================================
-- 0003_user_currency — per-user default currency, shown in Settings → profile
-- and used to pre-fill new assets. Purely a display default: existing assets
-- keep whatever currency they were saved with, nothing is converted.
-- =============================================================================

ALTER TABLE users ADD COLUMN currency CHAR(3) NOT NULL DEFAULT 'INR';
