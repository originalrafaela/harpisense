-- Explicit additive migration AFTER 001; no account/password/session mutation.
BEGIN;
SELECT pg_advisory_xact_lock(7261102901);
CREATE TABLE IF NOT EXISTS hs_admin_mfa (
 account_id integer PRIMARY KEY REFERENCES hs_admin_account(id),
 required boolean NOT NULL DEFAULT false,
 secret_cipher text,
 last_step bigint NOT NULL DEFAULT -1,
 enabled_at timestamptz
);
ALTER TABLE hs_admin_session ADD COLUMN IF NOT EXISTS mfa_verified boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS hs_admin_mfa_challenge (
 token_hash text PRIMARY KEY CHECK(length(token_hash)=64),
 account_id integer NOT NULL REFERENCES hs_admin_account(id),
 credential_revision bigint NOT NULL,
 purpose text NOT NULL CHECK(purpose IN ('login','enroll')),
 pending_cipher text,
 expires_at timestamptz NOT NULL,
 attempts integer NOT NULL DEFAULT 0,
 consumed_at timestamptz
);
CREATE TABLE IF NOT EXISTS hs_admin_recovery_code (
 code_hash text PRIMARY KEY CHECK(length(code_hash)=64),
 account_id integer NOT NULL REFERENCES hs_admin_account(id),
 used_at timestamptz
);
CREATE TABLE IF NOT EXISTS hs_admin_local_grant (
 id integer PRIMARY KEY CHECK(id=1),
 token_hash text NOT NULL CHECK(length(token_hash)=64),
 purpose text NOT NULL CHECK(purpose IN ('bootstrap','recover')),
 credential_revision bigint,
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz
);
CREATE TABLE IF NOT EXISTS hs_admin_mfa_schema (version integer PRIMARY KEY CHECK(version=1));
INSERT INTO hs_admin_mfa_schema VALUES(1) ON CONFLICT DO NOTHING;
COMMIT;
