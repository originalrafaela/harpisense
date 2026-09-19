from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.query_params import normalize_query_timestamp
from app.core.security import require_admin
from app.db.session import get_db
from app.schemas.security_event import NetworkEventOut
from app.services.security_events import build_network_events_query

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=list[NetworkEventOut])
def list_network_events(
    db: Annotated[Session, Depends(get_db)],
    src_ip: str | None = None,
    dst_ip: str | None = None,
    dst_port: Annotated[int | None, Query(ge=0, le=65535)] = None,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[NetworkEventOut]:
    observed_from = normalize_query_timestamp(observed_from)
    observed_to = normalize_query_timestamp(observed_to)
    query = build_network_events_query(src_ip, dst_ip, dst_port, observed_from, observed_to, limit)
    return list(db.scalars(query).all())
