-- Run explicitly after 002/003 during native provisioning, never on API startup.
BEGIN;
SELECT pg_advisory_xact_lock(7261102901);
ALTER TABLE hs_admin_password_reset_code ADD COLUMN IF NOT EXISTS purpose text
 NOT NULL DEFAULT 'password_reset' CHECK(purpose='password_reset');
ALTER TABLE hs_admin_password_reset_code ADD COLUMN IF NOT EXISTS generation bigint
 NOT NULL DEFAULT 0 CHECK(generation>=0);
ALTER TABLE hs_admin_password_reset_code ADD COLUMN IF NOT EXISTS revoked_at timestamptz;
ALTER TABLE hs_admin_recovery_code ADD COLUMN IF NOT EXISTS purpose text
 NOT NULL DEFAULT 'authenticator_recovery' CHECK(purpose='authenticator_recovery');
ALTER TABLE hs_admin_recovery_code ADD COLUMN IF NOT EXISTS issued_at timestamptz;
ALTER TABLE hs_admin_recovery_code ADD COLUMN IF NOT EXISTS revoked_at timestamptz;
ALTER TABLE hs_admin_recovery_code ADD COLUMN IF NOT EXISTS generation bigint
 NOT NULL DEFAULT 0 CHECK(generation>=0);
CREATE TABLE IF NOT EXISTS hs_admin_first_access (
 account_id integer PRIMARY KEY REFERENCES hs_admin_account(id),
 password_reset_generation bigint NOT NULL DEFAULT 0 CHECK(password_reset_generation>=0),
 issued_at timestamptz,
 completed_at timestamptz
);
-- Existing accounts must reissue if their one-time response has been lost.
-- No password, TOTP secret, session or existing unused code is changed here.
INSERT INTO hs_admin_first_access(account_id) SELECT id FROM hs_admin_account
 ON CONFLICT(account_id) DO NOTHING;
COMMIT;
