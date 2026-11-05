CREATE TABLE IF NOT EXISTS hs_native_mqtt_observation (
 installation_id text PRIMARY KEY,
 connected boolean NOT NULL,
 subscribed boolean NOT NULL,
 observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 last_message_id text,
 last_message_at timestamptz,
 last_projection_id text
);
