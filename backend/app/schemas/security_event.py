from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.time import to_iso_z
from app.schemas.common import UtcDatetime


class Capture(BaseModel):
    interface: str = Field(min_length=1, max_length=64)
    direction: str = Field(min_length=1, max_length=64)
    protocol: str = Field(min_length=1, max_length=32)
    src_ip: str
    src_port: int | None = Field(default=None, ge=0, le=65535)
    dst_ip: str
    dst_port: int | None = Field(default=None, ge=0, le=65535)
    packet_size_bytes: int | None = Field(default=None, ge=0)
    tcp_flags: str | None = Field(default=None, max_length=32)


class MqttMetadata(BaseModel):
    present: bool
    message_type: str | None = Field(default=None, max_length=64)
    topic: str | None = Field(default=None, max_length=255)
    client_id: str | None = Field(default=None, max_length=128)


class Classification(BaseModel):
    stage: str = Field(max_length=64)
    label: str = Field(max_length=64)
    confidence: float | None = Field(default=None, ge=0, le=1)


class NetworkEventIn(BaseModel):
    schema_version: str = Field(pattern=r"^1\.0$")
    event_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(pattern=r"^network_event$")
    observed_at: UtcDatetime
    sensor_id: str = Field(pattern=r"^harpisense\.gateway\.[a-z0-9-]+$", max_length=128)
    capture: Capture
    mqtt: MqttMetadata | None = None
    classification: Classification

    @field_validator("observed_at", mode="before")
    @classmethod
    def observed_at_must_use_z_suffix(cls, value: object) -> object:
        if isinstance(value, str) and not value.endswith("Z"):
            raise ValueError("observed_at must use UTC ISO 8601 format with suffix Z")
        return value

    @model_validator(mode="after")
    def enforce_first_delivery_classification(self) -> "NetworkEventIn":
        if self.classification.stage != "raw_capture" or self.classification.label != "unknown":
            raise ValueError("network_event must remain raw_capture/unknown in this delivery")
        return self

    @field_validator("capture")
    @classmethod
    def validate_capture_protocol(cls, value: Capture) -> Capture:
        value.protocol = value.protocol.lower()
        return value


class SecurityEventAccepted(BaseModel):
    accepted: bool = True
    duplicate: bool
    id: UUID
    received_at: datetime

    model_config = ConfigDict(json_encoders={datetime: to_iso_z})


class NetworkEventOut(BaseModel):
    id: UUID
    schema_version: str
    event_id: str
    event_type: str
    observed_at: datetime
    received_at: datetime
    sensor_id: str | None
    capture: dict | None
    mqtt: dict | None
    classification: dict | None
    src_ip: str | None
    dst_ip: str | None
    dst_port: int | None

    @field_validator("src_ip", "dst_ip", mode="before")
    @classmethod
    def stringify_ip(cls, value: object) -> object:
        if value is None:
            return None
        return str(value)

    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: to_iso_z})
