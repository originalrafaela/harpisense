from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import TelemetryRecord
from app.schemas.telemetry import TelemetryIn
from app.services.devices import ensure_device
from app.services.idempotency import IdentifierConflictError


def _telemetry_payload(record: TelemetryRecord) -> dict:
    return {
        "schema_version": record.schema_version,
        "message_id": record.message_id,
        "device_id": record.device_id,
        "observed_at": record.observed_at,
        "sensor_type": record.sensor_type,
        "sequence": record.sequence,
        "measurements": record.measurements,
        "status": record.status,
    }


def _ensure_same_payload(existing: TelemetryRecord, payload: TelemetryIn) -> None:
    if _telemetry_payload(existing) != payload.model_dump():
        raise IdentifierConflictError("message_id", payload.message_id)


def ingest_telemetry(db: Session, payload: TelemetryIn) -> tuple[TelemetryRecord, bool]:
    existing = db.scalar(select(TelemetryRecord).where(TelemetryRecord.message_id == payload.message_id))
    if existing:
        _ensure_same_payload(existing, payload)
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
            _ensure_same_payload(duplicate, payload)
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
    query = select(TelemetryRecord).order_by(
        TelemetryRecord.observed_at.desc(),
        TelemetryRecord.received_at.desc(),
        TelemetryRecord.id.desc(),
    )
    if device_id:
        query = query.where(TelemetryRecord.device_id == device_id)
    if observed_from:
        query = query.where(TelemetryRecord.observed_at >= observed_from)
    if observed_to:
        query = query.where(TelemetryRecord.observed_at <= observed_to)
    return query.limit(limit)
