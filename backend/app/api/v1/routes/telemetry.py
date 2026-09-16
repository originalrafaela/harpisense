from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.query_params import normalize_query_timestamp
from app.core.security import require_admin
from app.db.session import get_db
from app.schemas.telemetry import TelemetryOut
from app.services.telemetry import build_telemetry_query

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=list[TelemetryOut])
def list_telemetry(
    db: Annotated[Session, Depends(get_db)],
    device_id: str | None = None,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[TelemetryOut]:
    observed_from = normalize_query_timestamp(observed_from)
    observed_to = normalize_query_timestamp(observed_to)
    query = build_telemetry_query(device_id, observed_from, observed_to, limit)
    return list(db.scalars(query).all())
