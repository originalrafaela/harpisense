BEGIN;
SELECT pg_advisory_xact_lock(72611027);
CREATE TABLE IF NOT EXISTS hs_harpia_explanation (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 incident_id text NOT NULL,
 incident_revision integer NOT NULL CHECK(incident_revision>0),
 fingerprint text NOT NULL,
 explanation jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(incident_id,incident_revision,fingerprint)
);
CREATE INDEX IF NOT EXISTS hs_harpia_incident_history ON hs_harpia_explanation(incident_id,id DESC);
COMMIT;
