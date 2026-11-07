-- Immutable assessment events; an assessment never authorizes a defense.
CREATE TABLE IF NOT EXISTS hs_incident_assessment (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 incident_id text NOT NULL,
 incident_revision integer NOT NULL CHECK(incident_revision>=1),
 assessment text NOT NULL CHECK(assessment IN ('confirmed','discarded','inconclusive')),
 reason text NOT NULL CHECK(length(reason) BETWEEN 3 AND 1000),
 actor text NOT NULL,
 origin text NOT NULL CHECK(origin IN ('synthetic','trusted-service','unknown')),
 at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS ix_incident_assessment_latest ON hs_incident_assessment(incident_id,id DESC);
