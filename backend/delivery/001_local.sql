-- Local isolated bootstrap only. Do not apply automatically to a VM.
BEGIN;
CREATE TABLE IF NOT EXISTS projections (
 kind text NOT NULL, id text NOT NULL, revision integer NOT NULL CHECK(revision>=1),
 source text NOT NULL, data jsonb NOT NULL, created_at timestamptz NOT NULL,
 PRIMARY KEY(kind,id,revision)
);
CREATE INDEX IF NOT EXISTS ix_projection_kind_created ON projections(kind,created_at DESC);
CREATE TABLE IF NOT EXISTS hs_control (
 id integer PRIMARY KEY CHECK(id=1), value jsonb NOT NULL,
 revision integer NOT NULL CHECK(revision>=1), emergency_stopped boolean NOT NULL DEFAULT false,
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK(value->>'operation' IN ('IDS','SIMULATION')),
 CHECK((value->>'autonomy_mode')::integer IN (1,2,3)),
 CHECK(value->>'execution_enabled' IN ('true','false')),
 CHECK(value->>'operation'<>'IDS' OR value->>'execution_enabled'='false')
);
INSERT INTO hs_control(id,value,revision) VALUES(1,'{"operation":"IDS","execution_enabled":false,"autonomy_mode":1}',1)
 ON CONFLICT(id) DO NOTHING;
CREATE TABLE IF NOT EXISTS hs_control_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 actor text NOT NULL, operation text NOT NULL, details jsonb NOT NULL,
 at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS hs_simulation (decision_id text PRIMARY KEY, result jsonb NOT NULL);
COMMIT;
