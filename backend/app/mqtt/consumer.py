import json
import logging

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.telemetry import TelemetryIn
from app.services.telemetry import ingest_telemetry

logger = logging.getLogger(__name__)


def _topic_matches_payload(topic: str, payload: TelemetryIn) -> bool:
    parts = topic.split("/")
    if len(parts) != 5:
        return False
    return (
        parts[0] == "harpisense"
        and parts[1] == "v1"
        and parts[2] == "telemetry"
        and parts[3] == payload.device_id
        and parts[4] == payload.sensor_type
    )


def _on_connect(client: mqtt.Client, userdata: object, flags: dict, reason_code: int, properties: object | None = None) -> None:
    if reason_code == 0:
        client.subscribe(settings.mqtt_telemetry_topic)
        logger.info("Subscribed to MQTT telemetry topic %s", settings.mqtt_telemetry_topic)
    else:
        logger.error("MQTT connection failed with reason code %s", reason_code)


def _on_message(client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
    try:
        raw_payload = message.payload.decode("utf-8")
        payload = TelemetryIn.model_validate(json.loads(raw_payload))
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Rejected invalid MQTT telemetry payload on %s: %s", message.topic, exc)
        return

    if not _topic_matches_payload(message.topic, payload):
        logger.warning("Rejected MQTT telemetry payload with mismatched topic %s", message.topic)
        return

    with SessionLocal() as db:
        record, duplicate = ingest_telemetry(db, payload)
        logger.info("Stored MQTT telemetry message_id=%s duplicate=%s id=%s", payload.message_id, duplicate, record.id)


def build_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="harpisense-backend-telemetry")
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.on_connect = _on_connect
    client.on_message = _on_message
    return client


def run_forever() -> None:
    client = build_client()
    client.connect(settings.mqtt_host, settings.mqtt_port)
    client.loop_forever()
