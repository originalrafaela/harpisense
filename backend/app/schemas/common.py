from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def validate_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must include UTC timezone with suffix Z")
    value = value.astimezone(UTC)
    return value


UtcDatetime = Annotated[datetime, AfterValidator(validate_utc_datetime)]
