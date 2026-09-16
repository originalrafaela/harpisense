from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SecurityEvent
from app.schemas.security_event import NetworkEventIn
from app.services.devices import ensure_device


def ingest_network_event(db: Session, payload: NetworkEventIn) -> tuple[SecurityEvent, bool]:
    existing = db.scalar(select(SecurityEvent).where(SecurityEvent.event_id == payload.event_id))
    if existing:
        return existing, True

    ensure_device(db, payload.sensor_id)
    capture = payload.capture.model_dump()
    mqtt = payload.mqtt.model_dump() if payload.mqtt else None
    classification = payload.classification.model_dump()
    event = SecurityEvent(
        schema_version=payload.schema_version,
        event_id=payload.event_id,
        event_type=payload.event_type,
        observed_at=payload.observed_at,
        sensor_id=payload.sensor_id,
        capture_interface=capture.get("interface"),
        capture_direction=capture.get("direction"),
        protocol=capture.get("protocol"),
        src_ip=capture.get("src_ip"),
        src_port=capture.get("src_port"),
        dst_ip=capture.get("dst_ip"),
        dst_port=capture.get("dst_port"),
        packet_size_bytes=capture.get("packet_size_bytes"),
        tcp_flags=capture.get("tcp_flags"),
        mqtt_present=mqtt.get("present") if mqtt else None,
        mqtt_message_type=mqtt.get("message_type") if mqtt else None,
        mqtt_topic=mqtt.get("topic") if mqtt else None,
        mqtt_client_id=mqtt.get("client_id") if mqtt else None,
        classification_stage=classification.get("stage"),
        classification_label=classification.get("label"),
        classification_confidence=classification.get("confidence"),
        capture=capture,
        mqtt=mqtt,
        classification=classification,
        payload=payload.model_dump(mode="json"),
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = db.scalar(select(SecurityEvent).where(SecurityEvent.event_id == payload.event_id))
        if duplicate:
            return duplicate, True
        raise
    db.refresh(event)
    return event, False


def build_network_events_query(
    src_ip: str | None,
    dst_ip: str | None,
    dst_port: int | None,
    observed_from: datetime | None,
    observed_to: datetime | None,
    limit: int,
) -> Select[tuple[SecurityEvent]]:
    query = (
        select(SecurityEvent)
        .where(SecurityEvent.event_type == "network_event")
        .order_by(SecurityEvent.observed_at.desc(), SecurityEvent.received_at.desc())
    )
    if src_ip:
        query = query.where(SecurityEvent.src_ip == src_ip)
    if dst_ip:
        query = query.where(SecurityEvent.dst_ip == dst_ip)
    if dst_port is not None:
        query = query.where(SecurityEvent.dst_port == dst_port)
    if observed_from:
        query = query.where(SecurityEvent.observed_at >= observed_from)
    if observed_to:
        query = query.where(SecurityEvent.observed_at <= observed_to)
    return query.limit(limit)
