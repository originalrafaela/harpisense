# HarpiSense MQTT Lab

This directory contains the reproducible Mosquitto setup for the first IoT/MQTT delivery.

## Broker setup

Generate a local password file from example lab credentials:

```powershell
cd mqtt
docker compose --profile init run --rm mosquitto-init
docker compose up -d mosquitto
```

The generated `mqtt/config/passwords` file is ignored by Git. The example passwords in `lab-users.example` are not real credentials and must be replaced for any real lab network.

## Access control

- `iot_device_lab` can publish only telemetry topics matching its MQTT client id: `poste-1`, `poste-2` or `poste-3`.
- `mqtt_test_subscriber` can read `harpisense/v1/telemetry/#` and cannot publish.
- `mqtt_auth_exporter` is reserved for the future `harpisense/v1/security/mqtt-auth-event` flow.

## Logs

Mosquitto writes to stdout and to `mqtt/log/mosquitto.log`. Log files are intentionally not versioned.
