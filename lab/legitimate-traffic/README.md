# Legitimate MQTT Traffic

These scripts generate and validate legitimate telemetry using the shared contract.

## Install

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r lab\legitimate-traffic\requirements.txt
```

## Publish simulated telemetry

Use `poste-2` or `poste-3` for simulated posts:

```powershell
$env:MQTT_PASSWORD="change-me-iot-lab"
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --device poste-2 --count 3 --interval 1
```

The simulator publishes to:

- `harpisense/v1/telemetry/harpisense.poste.poste-2/environment`
- `harpisense/v1/telemetry/harpisense.poste.poste-3/environment`

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
