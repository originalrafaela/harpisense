-- Explicit additive migration after 002. No existing credentials are changed.
BEGIN;
SELECT pg_advisory_xact_lock(7261102901);
CREATE TABLE IF NOT EXISTS hs_admin_password_code (
 code_hash text PRIMARY KEY CHECK(length(code_hash)=64),
 account_id integer NOT NULL REFERENCES hs_admin_account(id),
 credential_revision bigint NOT NULL,
 expires_at timestamptz NOT NULL,
 used_at timestamptz
);
CREATE TABLE IF NOT EXISTS hs_admin_password_grant (
 token_hash text PRIMARY KEY CHECK(length(token_hash)=64),
 account_id integer NOT NULL REFERENCES hs_admin_account(id),
 credential_revision bigint NOT NULL,
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz
);
COMMIT;
