import logging

from app.core.config import settings
from app.mqtt.consumer import run_forever

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    if not settings.mqtt_enabled:
        raise SystemExit("MQTT ingestion is disabled. Set HARPI_MQTT_ENABLED=true to run this worker.")
    run_forever()
