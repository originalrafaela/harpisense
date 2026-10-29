-- Explicit, additive migration on the EXISTING P11 PostgreSQL database.
-- Never run automatically at API startup. No projection/domain tables touched.
BEGIN;
SELECT pg_advisory_xact_lock(7261102901);
CREATE TABLE hs_admin_schema_version (version integer PRIMARY KEY CHECK(version=1));
CREATE TABLE hs_admin_account (
 id integer PRIMARY KEY CHECK(id=1),
 username text NOT NULL CHECK(username ~ '^[A-Za-z0-9_.@-]{3,64}$'),
 password_hash text NOT NULL,
 credential_revision bigint NOT NULL DEFAULT 1 CHECK(credential_revision>0),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
-- Singleton throttle exists even before provisioning; invented usernames cannot bypass it.
CREATE TABLE hs_admin_throttle (
 id integer PRIMARY KEY CHECK(id=1), failures integer NOT NULL DEFAULT 0,
 blocked_until timestamptz NOT NULL DEFAULT '-infinity'
);
INSERT INTO hs_admin_throttle(id) VALUES(1);
CREATE TABLE hs_admin_session (
 token_hash text PRIMARY KEY CHECK(length(token_hash)=64),
 account_id integer NOT NULL REFERENCES hs_admin_account(id),
 credential_revision bigint NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 revoked_at timestamptz
);
CREATE INDEX hs_admin_session_expiry ON hs_admin_session(expires_at);
CREATE TABLE hs_admin_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 event text NOT NULL, at timestamptz NOT NULL DEFAULT clock_timestamp(),
 -- Only stable account id and result code; no submitted names, passwords or tokens.
 account_id integer, result text NOT NULL
);
INSERT INTO hs_admin_schema_version VALUES(1);
COMMIT;
