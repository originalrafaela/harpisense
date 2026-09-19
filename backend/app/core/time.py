from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    value = value.astimezone(UTC)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
