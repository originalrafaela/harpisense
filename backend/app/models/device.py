from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint("device_type IN ('poste', 'gateway', 'broker')", name="ck_devices_device_type"),
    )

    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    telemetry_records = relationship("TelemetryRecord", back_populates="device")
    sensor_events = relationship(
        "SecurityEvent",
        back_populates="sensor",
        foreign_keys="SecurityEvent.sensor_id",
    )
    broker_events = relationship(
        "SecurityEvent",
        back_populates="broker",
        foreign_keys="SecurityEvent.broker_id",
    )
