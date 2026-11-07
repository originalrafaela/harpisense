-- Additive internal action review. Assessment remains hs_incident_assessment.
BEGIN;
CREATE TABLE IF NOT EXISTS hs_action_review (
 kind text NOT NULL CHECK(kind IN ('approval','result','verification')),
 decision_id text NOT NULL,
 data jsonb NOT NULL,
 actor text NOT NULL CHECK(length(btrim(actor)) > 0),
 at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(kind,decision_id)
);
COMMIT;
