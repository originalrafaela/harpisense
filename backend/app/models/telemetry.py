from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TelemetryRecord(Base):
    __tablename__ = "telemetry_records"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_telemetry_records_message_id"),
        Index("ix_telemetry_records_device_observed_at", "device_id", "observed_at"),
        Index("ix_telemetry_records_observed_at", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.device_id", ondelete="RESTRICT"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sensor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int | None] = mapped_column(BigInteger)
    measurements: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[dict | None] = mapped_column(JSONB)

    device = relationship("Device", back_populates="telemetry_records")
