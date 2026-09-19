# HarpiSense MQTT Lab

This directory contains the reproducible Mosquitto setup for the first IoT/MQTT delivery.

## Broker setup

Generate a local password file from example lab credentials plus the externally
provided backend consumer password:

```powershell
cd mqtt
$env:HARPISENSE_BACKEND_CONSUMER_PASSWORD="<senha-mqtt-backend-consumer>"
docker compose --profile init run --rm -e HARPISENSE_BACKEND_CONSUMER_PASSWORD mosquitto-init
docker compose up -d mosquitto
Remove-Item Env:\HARPISENSE_BACKEND_CONSUMER_PASSWORD
```

The generated `mqtt/config/passwords` file is ignored by Git. The example
passwords in `lab-users.example` are not real credentials and must be replaced
for any real lab network.

`create-password-file.sh` refuses to overwrite an existing password file by
default. To intentionally rotate or recreate the local credentials, pass
`--force` as the third script argument:

```powershell
cd mqtt
$env:HARPISENSE_BACKEND_CONSUMER_PASSWORD="<nova-senha-mqtt-backend-consumer>"
docker compose --profile init run --rm -e HARPISENSE_BACKEND_CONSUMER_PASSWORD mosquitto-init /mosquitto/config/create-password-file.sh /mosquitto/config/lab-users.example /mosquitto/config/passwords --force
Remove-Item Env:\HARPISENSE_BACKEND_CONSUMER_PASSWORD
```

For local-only credentials, create `mqtt/config/lab-users.local` with the same
`username:password` format and use it as the first script argument. That file is
ignored by Git. Do not place `harpisense_backend_consumer` in the users file; the
script adds that user from `HARPISENSE_BACKEND_CONSUMER_PASSWORD` so the password
is supplied externally and never versioned.

## Access control

- `iot_device_lab` can publish only telemetry topics matching its MQTT client id: `poste-1`, `poste-2` or `poste-3`.
- `mqtt_test_subscriber` can read `harpisense/v1/telemetry/#` and cannot publish.
- `harpisense_backend_consumer` can read `harpisense/v1/telemetry/#` and cannot publish.
- `harpisense_backend_consumer` has no ACL for `harpisense/v1/security/#`.
- `mqtt_auth_exporter` is reserved for the future `harpisense/v1/security/mqtt-auth-event` flow.

The backend MQTT consumer should use the dedicated read-only user, separate from
publisher and test subscriber credentials:

| Backend setting | Broker value |
| --- | --- |
| `HARPI_MQTT_USERNAME` | `harpisense_backend_consumer` |
| `HARPI_MQTT_PASSWORD` | local password supplied by `HARPISENSE_BACKEND_CONSUMER_PASSWORD` during provisioning |
| `HARPI_MQTT_HOST` | broker host, for example `localhost` |
| `HARPI_MQTT_PORT` | `1883` |
| `HARPI_MQTT_TELEMETRY_TOPIC` | `harpisense/v1/telemetry/+/+` |

The broker ACL grants the backend consumer `read harpisense/v1/telemetry/#`,
which covers the telemetry topics currently defined in the shared contract:

- `harpisense/v1/telemetry/harpisense.poste.poste-1/environment`
- `harpisense/v1/telemetry/harpisense.poste.poste-1/power`
- `harpisense/v1/telemetry/harpisense.poste.poste-2/environment`
- `harpisense/v1/telemetry/harpisense.poste.poste-3/environment`

It does not grant publication rights or access to security topics.

## ACL tests

Prepare the password file and run the broker-backed ACL test:

```powershell
.\tests\integration\test_mqtt_backend_consumer_acl.ps1 -BackendConsumerPassword "<senha-mqtt-backend-consumer>"
```

The test checks:

- telemetry subscription succeeds for `harpisense_backend_consumer`;
- telemetry publication by `harpisense_backend_consumer` is rejected;
- subscription to `harpisense/v1/security/#` is rejected;
- publication to `harpisense/v1/security/network-event` is rejected.

Only treat the ACLs as validated after this test runs against a real Mosquitto
broker.

## Logs

Mosquitto writes to stdout and to `mqtt/log/mosquitto.log`. Log files are intentionally not versioned.
