-- Explicit trusted lifecycle reports. Assessments never write these tables.
CREATE TABLE IF NOT EXISTS hs_activity_event (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source text NOT NULL CHECK(source IN ('incident','anomaly','approval','execution','verification')),
 source_revision bigint NOT NULL CHECK(source_revision>0),
 record_id text NOT NULL,
 origin text NOT NULL CHECK(origin IN ('synthetic','trusted-service')),
 data jsonb NOT NULL,
 at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(source,source_revision,record_id,origin)
);
CREATE INDEX IF NOT EXISTS ix_activity_incident ON hs_activity_event
 ((data->'incident_ref'->>'id'),(data->'incident_ref'->>'revision'));

-- Canonical decisions stay unchanged. This exact-revision sidecar records the
-- control snapshot and policy/context supplied by the admitted producer.
CREATE TABLE IF NOT EXISTS hs_decision_snapshot (
 decision_id text NOT NULL,
 decision_revision integer NOT NULL CHECK(decision_revision>0),
 origin text NOT NULL CHECK(origin IN ('synthetic','trusted-service')),
 historical_profile jsonb NOT NULL,
 policy jsonb NOT NULL,
 context jsonb,
 at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(decision_id,decision_revision)
);
