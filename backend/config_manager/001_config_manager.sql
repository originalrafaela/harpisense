-- Additive and explicit. No P11, authentication, bootstrap or domain table changes.
CREATE SCHEMA hs_config;
REVOKE ALL ON SCHEMA hs_config FROM PUBLIC;
CREATE TABLE hs_config.migration (
 version integer PRIMARY KEY CHECK (version = 1), checksum text NOT NULL
);
CREATE TABLE hs_config.installation (
 installation_id text PRIMARY KEY,
 desired_revision bigint NOT NULL DEFAULT 0 CHECK (desired_revision >= 0),
 effective_revision bigint,
 fence bigint NOT NULL DEFAULT 0 CHECK (fence >= 0),
 active_operation uuid,
 CHECK (effective_revision IS NULL OR effective_revision BETWEEN 1 AND desired_revision)
);
CREATE TABLE hs_config.revision (
 installation_id text NOT NULL REFERENCES hs_config.installation,
 revision bigint NOT NULL CHECK (revision > 0),
 schema_version text NOT NULL CHECK (schema_version = '1.0.0'),
 document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
 fingerprint text NOT NULL CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (installation_id, revision)
);
CREATE TABLE hs_config.operation (
 operation_id uuid PRIMARY KEY,
 installation_id text NOT NULL,
 revision bigint NOT NULL,
 actor text NOT NULL,
 request_id uuid NOT NULL,
 idempotency_key text NOT NULL,
 request_fingerprint text NOT NULL,
 reason_code text NOT NULL CHECK (reason_code IN ('INITIAL_IMPORT','ADMIN_CHANGE','RESTORE')),
 status text NOT NULL CHECK (status IN
 ('DRAFT','VALIDATED','REJECTED','APPLYING','APPLIED','FAILED','RECOVERY_REQUIRED')),
 capability_fingerprint text,
 required_components jsonb,
 fence bigint,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE (installation_id, actor, idempotency_key),
 UNIQUE (installation_id, actor, request_id),
 UNIQUE (installation_id, revision),
 FOREIGN KEY (installation_id, revision) REFERENCES hs_config.revision
);
ALTER TABLE hs_config.installation ADD CONSTRAINT hs_config_effective_fk
 FOREIGN KEY (installation_id, effective_revision) REFERENCES hs_config.revision;
ALTER TABLE hs_config.installation ADD CONSTRAINT hs_config_active_fk
 FOREIGN KEY (active_operation) REFERENCES hs_config.operation;
CREATE TABLE hs_config.audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 installation_id text NOT NULL REFERENCES hs_config.installation,
 operation_id uuid REFERENCES hs_config.operation,
 revision bigint NOT NULL,
 actor text NOT NULL,
 event text NOT NULL CHECK (event IN
 ('PROPOSED','VALIDATED','REJECTED','APPLYING','VERIFIED','APPLIED','FAILED','RECOVERY_REQUIRED')),
 result_code text NOT NULL,
 at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX hs_config_audit_history ON hs_config.audit (installation_id, id);
CREATE TABLE hs_config.receipt (
 operation_id uuid NOT NULL REFERENCES hs_config.operation,
 component text NOT NULL,
 fence bigint NOT NULL,
 document_fingerprint text NOT NULL,
 verifier_ref text NOT NULL,
 evidence_ref text NOT NULL,
 observed_at timestamptz NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (operation_id, component)
);
CREATE FUNCTION hs_config.immutable_row() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'CONFIG_IMMUTABLE_RECORD' USING ERRCODE = '23000';
END;
$$;
CREATE TRIGGER revision_immutable BEFORE UPDATE OR DELETE ON hs_config.revision
 FOR EACH ROW EXECUTE FUNCTION hs_config.immutable_row();
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON hs_config.audit
 FOR EACH ROW EXECUTE FUNCTION hs_config.immutable_row();
CREATE TRIGGER receipt_immutable BEFORE UPDATE OR DELETE ON hs_config.receipt
 FOR EACH ROW EXECUTE FUNCTION hs_config.immutable_row();
