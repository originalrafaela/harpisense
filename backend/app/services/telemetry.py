from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import TelemetryRecord
from app.schemas.telemetry import TelemetryIn
from app.services.devices import ensure_device


def ingest_telemetry(db: Session, payload: TelemetryIn) -> tuple[TelemetryRecord, bool]:
    existing = db.scalar(select(TelemetryRecord).where(TelemetryRecord.message_id == payload.message_id))
    if existing:
        return existing, True

    ensure_device(db, payload.device_id)
    record = TelemetryRecord(
        schema_version=payload.schema_version,
        message_id=payload.message_id,
        device_id=payload.device_id,
        observed_at=payload.observed_at,
        sensor_type=payload.sensor_type,
        sequence=payload.sequence,
        measurements=payload.measurements,
        status=payload.status,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = db.scalar(select(TelemetryRecord).where(TelemetryRecord.message_id == payload.message_id))
        if duplicate:
            return duplicate, True
        raise
    db.refresh(record)
    return record, False


def build_telemetry_query(
    device_id: str | None,
    observed_from: datetime | None,
    observed_to: datetime | None,
    limit: int,
) -> Select[tuple[TelemetryRecord]]:
    query = select(TelemetryRecord).order_by(TelemetryRecord.observed_at.desc(), TelemetryRecord.received_at.desc())
    if device_id:
        query = query.where(TelemetryRecord.device_id == device_id)
    if observed_from:
        query = query.where(TelemetryRecord.observed_at >= observed_from)
    if observed_to:
        query = query.where(TelemetryRecord.observed_at <= observed_to)
    return query.limit(limit)
