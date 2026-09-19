#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
MQTT_HOST="${MQTT_HOST:-127.0.0.1}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USERNAME="${MQTT_USERNAME:-iot_device_lab}"
SYNTHETIC_DEVICE="${SYNTHETIC_DEVICE:-poste-2}"
SYNTHETIC_SEED="${SYNTHETIC_SEED:-20260919}"
POLL_ATTEMPTS="${POLL_ATTEMPTS:-30}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-2}"

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 2
  fi
}

require_env MQTT_PASSWORD
require_env HARPI_ADMIN_USERNAME
require_env HARPI_ADMIN_PASSWORD
require_env HARPI_GATEWAY_USERNAME
require_env HARPI_GATEWAY_PASSWORD

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  echo "Missing $ROOT_DIR/.venv/bin/python. Create the repository venv and install backend, edge and simulator requirements first." >&2
  exit 2
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

echo "== HarpiSense first delivery synthetic integration test =="
echo "API: $API_BASE_URL"
echo "MQTT: $MQTT_HOST:$MQTT_PORT"
echo "Synthetic data only: this script does not prove real sensor capture or real attack/incident detection."

curl -fsS "$API_BASE_URL/api/v1/health" >/dev/null

publish_log="$tmpdir/simulator.log"
(
  cd "$ROOT_DIR"
  MQTT_HOST="$MQTT_HOST" \
  MQTT_PORT="$MQTT_PORT" \
  MQTT_USERNAME="$MQTT_USERNAME" \
  MQTT_PASSWORD="$MQTT_PASSWORD" \
    .venv/bin/python lab/legitimate-traffic/simulate_poste.py \
      --device "$SYNTHETIC_DEVICE" \
      --count 1 \
      --interval 0 \
      --seed "$SYNTHETIC_SEED"
) | tee "$publish_log"

message_id="$(sed -n 's/.*message_id=\([^ ]*\).*/\1/p' "$publish_log" | tail -n 1)"
if [[ -z "$message_id" ]]; then
  echo "Could not extract message_id from simulator output." >&2
  exit 1
fi

device_id="harpisense.poste.${SYNTHETIC_DEVICE}"
echo "Published synthetic telemetry message_id=$message_id device_id=$device_id"

telemetry_json="$tmpdir/telemetry.json"
found_telemetry="false"
for attempt in $(seq 1 "$POLL_ATTEMPTS"); do
  curl -fsS -u "$HARPI_ADMIN_USERNAME:$HARPI_ADMIN_PASSWORD" \
    "$API_BASE_URL/api/v1/telemetry?device_id=$device_id&limit=25" > "$telemetry_json"
  if "$ROOT_DIR/.venv/bin/python" - "$telemetry_json" "$message_id" <<'PY'
import json
import sys

path, message_id = sys.argv[1], sys.argv[2]
items = json.load(open(path, encoding="utf-8"))
raise SystemExit(0 if any(item.get("message_id") == message_id for item in items) else 1)
PY
  then
    found_telemetry="true"
    break
  fi
  sleep "$POLL_INTERVAL_SECONDS"
done

if [[ "$found_telemetry" != "true" ]]; then
  echo "Telemetry was not persisted after polling. Check the backend MQTT consumer logs and Mosquitto ACLs." >&2
  exit 1
fi
echo "Telemetry persisted and visible through the administrative API."

event_id="synthetic-vm-network-$(date -u +%Y%m%dT%H%M%SZ)"
event_json="$tmpdir/network-event.json"
"$ROOT_DIR/.venv/bin/python" - "$event_json" "$event_id" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, event_id = sys.argv[1], sys.argv[2]
observed_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
payload = {
    "schema_version": "1.0",
    "event_id": event_id,
    "event_type": "network_event",
    "observed_at": observed_at,
    "sensor_id": "harpisense.gateway.edge-1",
    "capture": {
        "interface": "synthetic-vm",
        "direction": "iot_to_test",
        "protocol": "tcp",
        "src_ip": "192.0.2.10",
        "src_port": 49152,
        "dst_ip": "192.0.2.20",
        "dst_port": 1883,
        "packet_size_bytes": 128,
        "tcp_flags": "PA",
    },
    "mqtt": {
        "present": True,
        "message_type": "PUBLISH",
        "topic": "harpisense/v1/telemetry/harpisense.poste.poste-2/environment",
        "client_id": "synthetic-poste-simulator",
    },
    "classification": {
        "stage": "raw_capture",
        "label": "unknown",
        "confidence": None,
    },
    "aggregation": {
        "window_seconds": 30,
        "window_start": observed_at,
        "window_end": observed_at,
        "first_observed_at": observed_at,
        "last_observed_at": observed_at,
        "packet_count": 1,
        "total_packet_size_bytes": 128,
        "interfaces_observed": ["synthetic-vm"],
        "expected_interfaces": ["synthetic-vm"],
        "traversal_verified": True,
        "traversal_reason": "synthetic integration test event, not real gateway evidence",
        "traversal_evidence": {
            "observed_interfaces": ["synthetic-vm"],
            "required_interfaces": ["synthetic-vm"],
            "flow_key": {
                "protocol": "tcp",
                "src_ip": "192.0.2.10",
                "src_port": 49152,
                "dst_ip": "192.0.2.20",
                "dst_port": 1883,
                "direction": "iot_to_test",
                "mqtt_message_type": "PUBLISH",
                "mqtt_topic": "harpisense/v1/telemetry/harpisense.poste.poste-2/environment",
            },
        },
    },
}
json.dump(payload, open(path, "w", encoding="utf-8"), separators=(",", ":"))
PY

network_response="$tmpdir/network-response.json"
curl -fsS -u "$HARPI_GATEWAY_USERNAME:$HARPI_GATEWAY_PASSWORD" \
  -H "Content-Type: application/json" \
  -d "@$event_json" \
  "$API_BASE_URL/api/v1/ingest/network-events" > "$network_response"

"$ROOT_DIR/.venv/bin/python" - "$network_response" <<'PY'
import json
import sys

body = json.load(open(sys.argv[1], encoding="utf-8"))
if body.get("accepted") is not True:
    raise SystemExit(f"network event was not accepted: {body}")
PY
echo "Synthetic network_event accepted with gateway Basic credentials: event_id=$event_id"

network_list="$tmpdir/network-events.json"
curl -fsS -u "$HARPI_ADMIN_USERNAME:$HARPI_ADMIN_PASSWORD" \
  "$API_BASE_URL/api/v1/network-events?dst_port=1883&limit=25" > "$network_list"
"$ROOT_DIR/.venv/bin/python" - "$network_list" "$event_id" <<'PY'
import json
import sys

items = json.load(open(sys.argv[1], encoding="utf-8"))
event_id = sys.argv[2]
matches = [item for item in items if item.get("event_id") == event_id]
if not matches:
    raise SystemExit("network event is not visible through the administrative API")
if matches[0].get("aggregation", {}).get("packet_count") != 1:
    raise SystemExit("network event aggregation was not returned as persisted")
PY

echo "Administrative API returned the synthetic network_event with aggregation."
echo "PASS: synthetic MQTT telemetry and authenticated network_event ingestion were validated against the running stack."
