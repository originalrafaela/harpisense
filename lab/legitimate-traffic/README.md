# Legitimate MQTT Traffic

These scripts generate and validate legitimate telemetry using the shared contract.
Simulator output is synthetic laboratory data. The synthetic marker is written in
session metadata and JSONL wrapper records; the shared MQTT telemetry payload is
not extended with local-only fields.

## Install

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r lab\legitimate-traffic\requirements.txt
```

## Publish simulated telemetry

Use the default simulated posts, `poste-2` and `poste-3`:

```powershell
$env:MQTT_PASSWORD="change-me-iot-lab"
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --count 3 --interval 1
```

Configure quantity, identifiers, publication interval, duration and random seed:

```powershell
$env:MQTT_PASSWORD="change-me-iot-lab"
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --devices poste-2,poste-3,poste-4 --count 5 --interval 2 --duration 30 --seed 12345
```

Or generate identifiers from a count:

```powershell
$env:MQTT_PASSWORD="change-me-iot-lab"
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --post-count 4 --start-post-number 2 --count 3 --interval 1 --seed 42
```

The simulator publishes environment telemetry to topics like:

- `harpisense/v1/telemetry/harpisense.poste.poste-2/environment`
- `harpisense/v1/telemetry/harpisense.poste.poste-3/environment`

Each configured device keeps a stable `device_id` and monotonically increasing
`sequence`. Generated readings vary gradually within plausible lab ranges.

## Generate local JSONL without a broker

Use `--jsonl` to inspect the format without connecting to MQTT:

```powershell
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --devices poste-2,poste-3 --count 2 --interval 0 --seed 123 --jsonl lab\legitimate-traffic\samples\synthetic-telemetry.jsonl
```

Use `--jsonl -` to write JSONL to stdout:

```powershell
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --post-count 2 --count 1 --seed 123 --jsonl -
```

The first JSONL line is `session_metadata` with `"synthetic": true`. Telemetry
lines wrap the unchanged MQTT payload as:

```json
{"record_type":"telemetry","synthetic":true,"topic":"harpisense/v1/telemetry/harpisense.poste.poste-2/environment","payload":{"schema_version":"1.0"}}
```

## Validate received telemetry

```powershell
$env:MQTT_PASSWORD="change-me-subscriber-lab"
.\.venv\Scripts\python lab\legitimate-traffic\test_subscriber.py --expected-count 3
```

## Reconnection check

The simulator can force a client disconnect/reconnect after the first publish:

```powershell
$env:MQTT_PASSWORD="change-me-iot-lab"
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --device poste-2 --count 2 --interval 1 --exercise-reconnect
```

This is a simulated client reconnection test, not a broker failover or hardware reconnection test.
If a publish attempt fails and `--publish-retries` is greater than zero, the
simulator retransmits the same encoded payload, preserving `message_id`.
