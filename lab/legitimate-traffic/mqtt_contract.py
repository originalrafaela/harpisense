from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "1.0"

DEFAULT_POSTE_IDS = ("poste-2", "poste-3")

POSTE_DEVICE_IDS = {
    "poste-1": "harpisense.poste.poste-1",
    "poste-2": "harpisense.poste.poste-2",
    "poste-3": "harpisense.poste.poste-3",
}

ENVIRONMENT_TOPICS = {
    device: f"harpisense/v1/telemetry/{device_id}/environment"
    for device, device_id in POSTE_DEVICE_IDS.items()
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_message_id() -> str:
    return uuid.uuid4().hex


def device_label_to_id(device: str) -> str:
    if device.startswith("harpisense.poste."):
        return device
    return f"harpisense.poste.{device}"


def topic_for_device_id(device_id: str) -> str:
    return f"harpisense/v1/telemetry/{device_id}/environment"


def topic_for_device(device: str) -> str:
    return topic_for_device_id(device_label_to_id(device))


def build_environment_payload(
    device: str,
    sequence: int,
    *,
    temperature_c: float | None = None,
    humidity_pct: float | None = None,
    rssi_dbm: int | None = None,
    message_id: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    device_id = device_label_to_id(device)
    return {
        "schema_version": SCHEMA_VERSION,
        "message_id": message_id or new_message_id(),
        "device_id": device_id,
        "observed_at": observed_at or utc_now_iso(),
        "sensor_type": "environment",
        "sequence": sequence,
        "measurements": {
            "temperature_c": temperature_c,
            "humidity_pct": humidity_pct,
        },
        "status": {
            "battery_pct": None,
            "rssi_dbm": rssi_dbm,
        },
    }


def dumps_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def validate_environment_payload(topic: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1.0")

    device_id = payload.get("device_id")
    expected_topic = f"harpisense/v1/telemetry/{device_id}/environment"
    if topic != expected_topic:
        errors.append(f"topic mismatch: expected {expected_topic}, got {topic}")

    if not isinstance(device_id, str) or not device_id.startswith("harpisense.poste.poste-"):
        errors.append(f"invalid poste device_id: {device_id}")

    if payload.get("sensor_type") != "environment":
        errors.append("sensor_type must be environment")

    if not payload.get("message_id"):
        errors.append("message_id is required")

    observed_at = payload.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.endswith("Z"):
        errors.append("observed_at must be ISO 8601 UTC with Z suffix")

    sequence = payload.get("sequence")
    if not isinstance(sequence, int) or sequence < 0:
        errors.append("sequence must be a non-negative integer")

    measurements = payload.get("measurements")
    if not isinstance(measurements, dict):
        errors.append("measurements must be an object")
    else:
        for field in ("temperature_c", "humidity_pct"):
            value = measurements.get(field)
            if value is not None and not isinstance(value, (int, float)):
                errors.append(f"{field} must be numeric or null")
        temperature_c = measurements.get("temperature_c")
        if isinstance(temperature_c, (int, float)) and not 15.0 <= temperature_c <= 45.0:
            errors.append("temperature_c must be between 15.0 and 45.0")
        humidity_pct = measurements.get("humidity_pct")
        if isinstance(humidity_pct, (int, float)) and not 20.0 <= humidity_pct <= 95.0:
            errors.append("humidity_pct must be between 20.0 and 95.0")

    status = payload.get("status")
    if not isinstance(status, dict):
        errors.append("status must be an object")
    elif status.get("rssi_dbm") is not None and not isinstance(status.get("rssi_dbm"), int):
        errors.append("status.rssi_dbm must be integer or null")
    elif isinstance(status.get("rssi_dbm"), int) and not -95 <= status["rssi_dbm"] <= -35:
        errors.append("status.rssi_dbm must be between -95 and -35")

    return errors
