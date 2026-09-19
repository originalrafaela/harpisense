"""initial schema for devices, telemetry and security events

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-09-16 00:24:34.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("device_type", sa.String(length=32), nullable=False),
        sa.Column("origin", sa.String(length=64), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("device_type IN ('poste', 'gateway', 'broker')", name="ck_devices_device_type"),
        sa.PrimaryKeyConstraint("device_id"),
    )

    op.create_table(
        "telemetry_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sensor_type", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=True),
        sa.Column("measurements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_telemetry_records_message_id"),
    )
    op.create_index("ix_telemetry_records_device_observed_at", "telemetry_records", ["device_id", "observed_at"])
    op.create_index("ix_telemetry_records_observed_at", "telemetry_records", ["observed_at"])

    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sensor_id", sa.String(length=128), nullable=True),
        sa.Column("broker_id", sa.String(length=128), nullable=True),
        sa.Column("client_id", sa.String(length=128), nullable=True),
        sa.Column("capture_interface", sa.String(length=64), nullable=True),
        sa.Column("capture_direction", sa.String(length=64), nullable=True),
        sa.Column("protocol", sa.String(length=32), nullable=True),
        sa.Column("src_ip", postgresql.INET(), nullable=True),
        sa.Column("src_port", sa.Integer(), nullable=True),
        sa.Column("dst_ip", postgresql.INET(), nullable=True),
        sa.Column("dst_port", sa.Integer(), nullable=True),
        sa.Column("packet_size_bytes", sa.Integer(), nullable=True),
        sa.Column("tcp_flags", sa.String(length=32), nullable=True),
        sa.Column("mqtt_present", sa.Boolean(), nullable=True),
        sa.Column("mqtt_message_type", sa.String(length=64), nullable=True),
        sa.Column("mqtt_topic", sa.String(length=255), nullable=True),
        sa.Column("mqtt_client_id", sa.String(length=128), nullable=True),
        sa.Column("classification_stage", sa.String(length=64), nullable=True),
        sa.Column("classification_label", sa.String(length=64), nullable=True),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.Column("capture", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mqtt", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("classification", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["devices.device_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sensor_id"], ["devices.device_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_security_events_event_id"),
    )
    op.create_index("ix_security_events_dst_ip", "security_events", ["dst_ip"])
    op.create_index("ix_security_events_dst_port", "security_events", ["dst_port"])
    op.create_index("ix_security_events_event_type_observed_at", "security_events", ["event_type", "observed_at"])
    op.create_index("ix_security_events_observed_at", "security_events", ["observed_at"])
    op.create_index("ix_security_events_src_ip", "security_events", ["src_ip"])


def downgrade() -> None:
    op.drop_index("ix_security_events_src_ip", table_name="security_events")
    op.drop_index("ix_security_events_observed_at", table_name="security_events")
    op.drop_index("ix_security_events_event_type_observed_at", table_name="security_events")
    op.drop_index("ix_security_events_dst_port", table_name="security_events")
    op.drop_index("ix_security_events_dst_ip", table_name="security_events")
    op.drop_table("security_events")
    op.drop_index("ix_telemetry_records_observed_at", table_name="telemetry_records")
    op.drop_index("ix_telemetry_records_device_observed_at", table_name="telemetry_records")
    op.drop_table("telemetry_records")
    op.drop_table("devices")
