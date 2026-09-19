from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_security_events_event_id"),
        Index("ix_security_events_dst_ip", "dst_ip"),
        Index("ix_security_events_dst_port", "dst_port"),
        Index("ix_security_events_event_type_observed_at", "event_type", "observed_at"),
        Index("ix_security_events_observed_at", "observed_at"),
        Index("ix_security_events_src_ip", "src_ip"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    sensor_id: Mapped[str | None] = mapped_column(ForeignKey("devices.device_id", ondelete="RESTRICT"))
    broker_id: Mapped[str | None] = mapped_column(ForeignKey("devices.device_id", ondelete="RESTRICT"))
    client_id: Mapped[str | None] = mapped_column(String(128))

    capture_interface: Mapped[str | None] = mapped_column(String(64))
    capture_direction: Mapped[str | None] = mapped_column(String(64))
    protocol: Mapped[str | None] = mapped_column(String(32))
    src_ip: Mapped[str | None] = mapped_column(INET)
    src_port: Mapped[int | None] = mapped_column(Integer)
    dst_ip: Mapped[str | None] = mapped_column(INET)
    dst_port: Mapped[int | None] = mapped_column(Integer)
    packet_size_bytes: Mapped[int | None] = mapped_column(Integer)
    tcp_flags: Mapped[str | None] = mapped_column(String(32))

    mqtt_present: Mapped[bool | None] = mapped_column(Boolean)
    mqtt_message_type: Mapped[str | None] = mapped_column(String(64))
    mqtt_topic: Mapped[str | None] = mapped_column(String(255))
    mqtt_client_id: Mapped[str | None] = mapped_column(String(128))

    classification_stage: Mapped[str | None] = mapped_column(String(64))
    classification_label: Mapped[str | None] = mapped_column(String(64))
    classification_confidence: Mapped[float | None] = mapped_column(Float)

    capture: Mapped[dict | None] = mapped_column(JSONB)
    mqtt: Mapped[dict | None] = mapped_column(JSONB)
    classification: Mapped[dict | None] = mapped_column(JSONB)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    sensor = relationship("Device", back_populates="sensor_events", foreign_keys=[sensor_id])
    broker = relationship("Device", back_populates="broker_events", foreign_keys=[broker_id])

    @property
    def aggregation(self) -> dict | None:
        if not self.payload:
            return None
        return self.payload.get("aggregation")
