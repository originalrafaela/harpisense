from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.time import to_iso_z
from app.schemas.common import UtcDatetime


class TelemetryIn(BaseModel):
    schema_version: str = Field(pattern=r"^1\.0$")
    message_id: str = Field(min_length=1, max_length=64)
    device_id: str = Field(pattern=r"^harpisense\.poste\.[a-z0-9-]+$", max_length=128)
    observed_at: UtcDatetime
    sensor_type: str = Field(min_length=1, max_length=64)
    sequence: int | None = None
    measurements: dict = Field(default_factory=dict)
    status: dict | None = None

    @field_validator("measurements")
    @classmethod
    def measurements_must_not_be_empty(cls, value: dict) -> dict:
        if not value:
            raise ValueError("measurements must not be empty")
        return value

    @field_validator("observed_at", mode="before")
    @classmethod
    def observed_at_must_use_z_suffix(cls, value: object) -> object:
        if isinstance(value, str) and not value.endswith("Z"):
            raise ValueError("observed_at must use UTC ISO 8601 format with suffix Z")
        return value


class IngestAccepted(BaseModel):
    accepted: bool = True
    duplicate: bool
    id: UUID
    received_at: datetime

    model_config = ConfigDict(json_encoders={datetime: to_iso_z})


class TelemetryOut(BaseModel):
    id: UUID
    schema_version: str
    message_id: str
    device_id: str
    observed_at: datetime
    received_at: datetime
    sensor_type: str
    sequence: int | None
    measurements: dict
    status: dict | None

    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: to_iso_z})
