from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.session import get_db
from app.schemas.security_event import NetworkEventIn, SecurityEventAccepted
from app.schemas.telemetry import IngestAccepted, TelemetryIn
from app.services.security_events import ingest_network_event
from app.services.telemetry import ingest_telemetry

router = APIRouter(dependencies=[Depends(require_admin)])


@router.post("/telemetry", response_model=IngestAccepted, status_code=status.HTTP_202_ACCEPTED)
def post_telemetry(payload: TelemetryIn, db: Annotated[Session, Depends(get_db)]) -> IngestAccepted:
    record, duplicate = ingest_telemetry(db, payload)
    return IngestAccepted(duplicate=duplicate, id=record.id, received_at=record.received_at)


@router.post("/network-events", response_model=SecurityEventAccepted, status_code=status.HTTP_202_ACCEPTED)
def post_network_event(payload: NetworkEventIn, db: Annotated[Session, Depends(get_db)]) -> SecurityEventAccepted:
    event, duplicate = ingest_network_event(db, payload)
    return SecurityEventAccepted(duplicate=duplicate, id=event.id, received_at=event.received_at)
