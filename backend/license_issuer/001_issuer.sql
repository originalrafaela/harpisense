BEGIN;
SELECT pg_advisory_xact_lock(7261102902);
CREATE TABLE hs_issuer_license (
 license_id uuid PRIMARY KEY,
 key_hash text NOT NULL UNIQUE CHECK(length(key_hash)=64),
 delivered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 installation_id uuid,
 installation_key_id text,
 installation_public_key text,
 platform text CHECK(platform IN ('windows','ubuntu')),
 receipt jsonb,
 CHECK((installation_id IS NULL) = (receipt IS NULL))
);
CREATE TABLE hs_issuer_challenge (
 challenge_id uuid PRIMARY KEY,
 license_id uuid NOT NULL REFERENCES hs_issuer_license(license_id),
 installation_id uuid NOT NULL,
 installation_key_id text NOT NULL,
 installation_public_key text NOT NULL,
 platform text NOT NULL CHECK(platform IN ('windows','ubuntu')),
 document jsonb NOT NULL,
 expires_at bigint NOT NULL,
 attempts integer NOT NULL DEFAULT 0,
 consumed_at timestamptz
);
CREATE TABLE hs_issuer_throttle (
 bucket text PRIMARY KEY,
 window_start timestamptz NOT NULL DEFAULT clock_timestamp(),
 attempts integer NOT NULL DEFAULT 0
);
COMMIT;
