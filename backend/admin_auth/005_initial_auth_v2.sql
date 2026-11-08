-- Explicit provisioning migration, after 001..004. Never on API startup.
BEGIN;
SELECT pg_advisory_xact_lock(7261102901);
ALTER TABLE hs_admin_account ADD COLUMN IF NOT EXISTS installation_id uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE hs_admin_account ADD COLUMN IF NOT EXISTS license_id uuid;
ALTER TABLE hs_admin_mfa ADD COLUMN IF NOT EXISTS enrollment_cipher text;
CREATE TABLE IF NOT EXISTS hs_admin_recovery_set_v2 (
 account_id integer PRIMARY KEY REFERENCES hs_admin_account(id),
 installation_id uuid NOT NULL,
 generation bigint NOT NULL DEFAULT 0 CHECK(generation>=0),
 issued_at timestamptz,
 confirmed_at timestamptz,
 UNIQUE(account_id,installation_id)
);
CREATE TABLE IF NOT EXISTS hs_admin_recovery_v2 (
 account_id integer NOT NULL,
 installation_id uuid NOT NULL,
 generation bigint NOT NULL CHECK(generation>0),
 slot integer NOT NULL CHECK(slot BETWEEN 1 AND 3),
 verifier text NOT NULL UNIQUE CHECK(length(verifier)=64),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 used_at timestamptz,
 revoked_at timestamptz,
 PRIMARY KEY(account_id,installation_id,generation,slot),
 FOREIGN KEY(account_id,installation_id) REFERENCES hs_admin_recovery_set_v2(account_id,installation_id)
);
-- Retain legacy sets for audit. Runtime v2 never accepts them or resets MFA.
UPDATE hs_admin_session SET revoked_at=clock_timestamp() WHERE NOT mfa_verified AND revoked_at IS NULL;
COMMIT;
