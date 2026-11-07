-- Explicit additive migration after 001_config_manager.sql.
BEGIN;
SELECT pg_advisory_xact_lock(7261103101);
CREATE TABLE IF NOT EXISTS hs_config.asset (
 installation_id text NOT NULL REFERENCES hs_config.installation(installation_id),
 technical_id text NOT NULL,
 revision bigint NOT NULL CHECK(revision>0),
 document jsonb NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(installation_id,technical_id)
);
CREATE TABLE IF NOT EXISTS hs_config.asset_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 installation_id text NOT NULL REFERENCES hs_config.installation(installation_id),
 technical_id text NOT NULL,
 revision bigint NOT NULL,
 actor text NOT NULL,
 event text NOT NULL,
 at timestamptz NOT NULL DEFAULT clock_timestamp()
);
COMMIT;
