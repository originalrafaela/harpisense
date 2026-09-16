from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


MQTT_MESSAGE_TYPES = {
    1: "CONNECT",
    2: "CONNACK",
    3: "PUBLISH",
    4: "PUBACK",
    5: "PUBREC",
    6: "PUBREL",
    7: "PUBCOMP",
    8: "SUBSCRIBE",
    9: "SUBACK",
    10: "UNSUBSCRIBE",
    11: "UNSUBACK",
    12: "PINGREQ",
    13: "PINGRESP",
    14: "DISCONNECT",
    15: "AUTH",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def datetime_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_mqtt_from_tcp_payload(payload: bytes) -> dict[str, Any]:
    """Extract non-sensitive MQTT metadata from a TCP payload when visible.

    This is intentionally shallow. Authentication result and broker decision data
    are not present in ordinary TCP packet metadata, so this parser never emits
    success/failure.
    """
    if not payload:
        return {"present": False, "message_type": None, "topic": None, "client_id": None}

    packet_type = payload[0] >> 4
    message_type = MQTT_MESSAGE_TYPES.get(packet_type, f"TYPE_{packet_type}")
    topic = None
    client_id = None

    try:
        remaining_offset = _mqtt_remaining_length_offset(payload)
        variable_header = payload[remaining_offset:]
        if packet_type == 3 and len(variable_header) >= 2:
            topic_len = int.from_bytes(variable_header[:2], "big")
            topic_bytes = variable_header[2 : 2 + topic_len]
            topic = topic_bytes.decode("utf-8", errors="replace") if topic_bytes else None
        elif packet_type == 1:
            client_id = _mqtt_connect_client_id(variable_header)
    except (IndexError, ValueError):
        pass

    return {
        "present": True,
        "message_type": message_type,
        "topic": topic,
        "client_id": client_id,
    }


def _mqtt_remaining_length_offset(payload: bytes) -> int:
    offset = 1
    multiplier = 1
    value = 0
    while True:
        encoded_byte = payload[offset]
        value += (encoded_byte & 127) * multiplier
        offset += 1
        if encoded_byte & 128 == 0:
            return offset
        multiplier *= 128
        if multiplier > 128 * 128 * 128:
            raise ValueError("invalid MQTT remaining length")


def _mqtt_connect_client_id(variable_header: bytes) -> str | None:
    # MQTT CONNECT variable header: protocol name, level, flags, keepalive,
    # followed by payload where the first UTF-8 field is client_id.
    if len(variable_header) < 10:
        return None
    payload = variable_header[10:]
    if len(payload) < 2:
        return None
    client_id_len = int.from_bytes(payload[:2], "big")
    client_id_bytes = payload[2 : 2 + client_id_len]
    return client_id_bytes.decode("utf-8", errors="replace") if client_id_bytes else None


@dataclass(frozen=True)
class PacketObservation:
    observed_at: datetime
    interface: str
    direction: str
    protocol: str
    src_ip: str
    src_port: int | None
    dst_ip: str
    dst_port: int | None
    packet_size_bytes: int
    tcp_flags: str | None = None
    mqtt_present: bool = False
    mqtt_message_type: str | None = None
    mqtt_topic: str | None = None
    mqtt_client_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def flow_key(self) -> tuple[Any, ...]:
        return (
            self.protocol,
            self.src_ip,
            self.src_port,
            self.dst_ip,
            self.dst_port,
            self.direction,
            self.mqtt_message_type,
            self.mqtt_topic,
        )


def build_network_event(
    observation: PacketObservation,
    sensor_id: str,
    *,
    event_id: str | None = None,
    aggregation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "schema_version": "1.0",
        "event_id": event_id or f"evt-{uuid4().hex}",
        "event_type": "network_event",
        "observed_at": datetime_to_iso(observation.observed_at),
        "sensor_id": sensor_id,
        "capture": {
            "interface": observation.interface,
            "direction": observation.direction,
            "protocol": observation.protocol,
            "src_ip": observation.src_ip,
            "src_port": observation.src_port,
            "dst_ip": observation.dst_ip,
            "dst_port": observation.dst_port,
            "packet_size_bytes": observation.packet_size_bytes,
            "tcp_flags": observation.tcp_flags,
        },
        "mqtt": {
            "present": observation.mqtt_present,
            "message_type": observation.mqtt_message_type,
            "topic": observation.mqtt_topic,
            "client_id": observation.mqtt_client_id,
        },
        "classification": {
            "stage": "raw_capture",
            "label": "unknown",
            "confidence": None,
        },
    }
    if aggregation:
        event["aggregation"] = aggregation
    return event
