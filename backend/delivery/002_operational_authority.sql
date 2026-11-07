-- Only trusted backend writers holding the controls transaction lock may report.
CREATE TABLE IF NOT EXISTS hs_operational_authority (
    source text PRIMARY KEY CHECK(source IN ('incident','anomaly','approval','execution','verification')),
    revision bigint NOT NULL CHECK(revision>0),
    items jsonb NOT NULL CHECK(jsonb_typeof(items)='array'),
    observed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
