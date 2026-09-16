# HarpiSense IoT Firmware

## Poste 1 ESP32

The firmware in `iot/esp32/poste1` publishes the contracted environment telemetry topic:

```text
harpisense/v1/telemetry/harpisense.poste.poste-1/environment
```

It uses MQTT client id `poste-1`, matching the Mosquitto ACL pattern.

### Build configuration

Copy `include/config.example.h` to `include/config.h` and replace local lab values before building. `config.h` is ignored by Git.

```powershell
cd iot\esp32\poste1
pio run
pio run --target upload
pio device monitor
```

### Hardware dependency

The shared contracts define Poste 1 as an ESP32 physical device but do not define the sensor model or pin mapping. The current firmware therefore publishes the correct MQTT contract with `temperature_c` and `humidity_pct` as `null` until the hardware details are approved. No power topic is published because voltage/current/power sensors are not defined.
