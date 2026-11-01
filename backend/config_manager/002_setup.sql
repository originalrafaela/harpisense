CREATE TABLE hs_config.setup_schema (version integer PRIMARY KEY, checksum text NOT NULL);
CREATE TABLE hs_config.setup_progress (
 installation_id text PRIMARY KEY REFERENCES hs_config.installation,
 version bigint NOT NULL CHECK(version > 0),
 document jsonb NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE hs_config.setup_request (
 installation_id text NOT NULL REFERENCES hs_config.installation,
 actor text NOT NULL,
 idempotency_key text NOT NULL,
 fingerprint text NOT NULL,
 result jsonb NOT NULL,
 PRIMARY KEY(installation_id,actor,idempotency_key)
);
CREATE TABLE hs_config.setup_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 installation_id text NOT NULL REFERENCES hs_config.installation,
 actor text NOT NULL, version bigint NOT NULL,
 event text NOT NULL CHECK(event='SETUP_SAVED'),
 at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER setup_audit_immutable BEFORE UPDATE OR DELETE ON hs_config.setup_audit
 FOR EACH ROW EXECUTE FUNCTION hs_config.immutable_row();
CREATE TRIGGER setup_request_immutable BEFORE UPDATE OR DELETE ON hs_config.setup_request
 FOR EACH ROW EXECUTE FUNCTION hs_config.immutable_row();
