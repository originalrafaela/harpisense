from datetime import datetime

from fastapi import HTTPException, status

from app.schemas.common import validate_utc_datetime


def normalize_query_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    try:
        return validate_utc_datetime(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
