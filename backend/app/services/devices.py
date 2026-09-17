from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models import Device


def infer_device_type(device_id: str) -> str:
    parts = device_id.split(".")
    if len(parts) >= 3 and parts[0] == "harpisense":
        return parts[1]
    return "poste"


def ensure_device(db: Session, device_id: str, origin: str | None = None) -> Device:
    device = db.get(Device, device_id)
    if device:
        return device

    device_type = infer_device_type(device_id)
    if db.bind and db.bind.dialect.name == "postgresql":
        statement = (
            insert(Device)
            .values(device_id=device_id, device_type=device_type, origin=origin)
            .on_conflict_do_nothing(index_elements=[Device.device_id])
        )
        db.execute(statement)
        return db.get_one(Device, device_id)

    device = Device(device_id=device_id, device_type=device_type, origin=origin)
    db.add(device)
    db.flush()
    return device
