# HarpiSense Laboratory Notes

The current IoT/MQTT delivery covers simulated legitimate MQTT traffic and broker validation. It does not include gateway capture, IDS, ML, blocking or backend persistence.

## Simulated tests

Simulated tests use Docker Mosquitto plus the Python publisher/subscriber in `lab/legitimate-traffic`.

1. Generate example lab auth and start Mosquitto:

   ```powershell
   cd mqtt
   docker compose --profile init run --rm mosquitto-init
   docker compose up -d mosquitto
   ```

2. Install Python dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python -m pip install -r lab\legitimate-traffic\requirements.txt
   ```

3. Start subscriber:

   ```powershell
   $env:MQTT_PASSWORD="change-me-subscriber-lab"
   .\.venv\Scripts\python lab\legitimate-traffic\test_subscriber.py --expected-count 2
   ```

4. Publish simulated telemetry with a forced client reconnect:

   ```powershell
   $env:MQTT_PASSWORD="change-me-iot-lab"
   .\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --device poste-2 --count 2 --interval 1 --exercise-reconnect
   ```

## Hardware tests

Hardware testing for Poste 1 requires:

- ESP32 board available locally.
- Approved sensor model and ESP32 pin mapping for temperature/humidity.
- Local `iot/esp32/poste1/include/config.h` with Wi-Fi and MQTT lab values.

Until those are available, only firmware compilation and simulated MQTT tests can be claimed.
