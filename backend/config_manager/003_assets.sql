CREATE TABLE IF NOT EXISTS hs_config.asset (
    installation_id text NOT NULL REFERENCES hs_config.installation(installation_id),
    device_id text NOT NULL,
    revision integer NOT NULL CHECK(revision>0),
    document jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(installation_id,device_id)
);
CREATE TABLE IF NOT EXISTS hs_config.asset_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    installation_id text NOT NULL,
    device_id text NOT NULL,
    revision integer NOT NULL,
    actor text NOT NULL,
    document jsonb NOT NULL,
    at timestamptz NOT NULL DEFAULT clock_timestamp()
);
