"""Input dispatch for the existing projection consumer; no network or DB bootstrap.

P06 telemetry_contract is an external, identified dependency, loaded only when
Poste 1 is explicitly enabled. The caller retains its existing Record factory.
"""
import hashlib
import json
import re

from .projections import Record

POSTE1_DEVICE = "harpisense.poste.poste-1"
POSTE1_TOPIC = f"harpisense/v1/telemetry/{POSTE1_DEVICE}/ldr"
POSTE2_TOPIC = "harpisense/poste2/telemetry"


class InputError(ValueError):
    """Stable validation code, without submitted payload or secret values."""


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise InputError("duplicate_key")
        result[key] = value
    return result


def _nonfinite(value):
    raise InputError("nonfinite_json")


def parse_poste1(raw, topic):
    from telemetry_contract.core import ContractError, validate

    if type(raw) is not bytes or len(raw) > 1024:
        raise InputError("payload_bytes_or_size")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_nonfinite)
        validate(data, topic)
        if topic != POSTE1_TOPIC or data["device_id"] != POSTE1_DEVICE:
            raise InputError("identity_mismatch")
        sequence = data.get("sequence")
        if type(sequence) is not int or not 0 <= sequence <= 9007199254740991:
            raise InputError("invalid_sequence")
        if not re.fullmatch(re.escape(POSTE1_DEVICE) + r"-[0-9a-fA-F]{16}-" + str(sequence),
                            data["message_id"]):
            raise InputError("invalid_message_id")
        if not data["observed_at"].endswith("Z"):
            raise InputError("utc_z_required")
        status, measurements = data["status"], data["measurements"]
        if status["origin_type"] != "PHYSICAL" or "calibration_version" in status:
            raise InputError("invalid_physical_profile")
        adc = measurements["ldr_adc_raw"]
        if adc is not None and (type(adc) is not int or not 0 <= adc <= 4095):
            raise InputError("invalid_adc")
        if type(measurements["led_commanded_on"]) is not bool:
            raise InputError("invalid_led_command")
        return data
    except InputError:
        raise
    except (ContractError, ValueError, TypeError, KeyError, RecursionError):
        raise InputError("invalid_poste1_payload") from None


class TelemetryInput:
    """Bind subscriptions/on_message in the existing authenticated MQTT consumer.

    Audit receives event codes only. Operational/store errors propagate to the
    caller's operational-error handler and are never classified as duplicates.
    """
    def __init__(self, store, audit, *, poste1_enabled=False, record_factory=Record):
        if type(poste1_enabled) is not bool:
            raise TypeError("poste1_enabled must be bool")
        self.store, self.audit = store, audit
        self.poste1_enabled = poste1_enabled
        self.record_factory = record_factory
        if poste1_enabled:
            from telemetry_contract.core import validate  # Fail closed at setup.

    @property
    def topics(self):
        return (POSTE2_TOPIC, POSTE1_TOPIC) if self.poste1_enabled else (POSTE2_TOPIC,)

    def subscribe(self, client):
        for topic in self.topics:
            client.subscribe(topic, qos=1)

    def handle(self, topic, raw):
        if topic == POSTE1_TOPIC and not self.poste1_enabled:
            return "disabled"
        if topic not in self.topics:
            self.audit("validation_failure")
            return "invalid"
        try:
            if topic == POSTE1_TOPIC:
                data = parse_poste1(raw, topic)
                identity = data["device_id"].encode("utf-8") + b"\0" + data["message_id"].encode("utf-8")
                record_id = "poste1-" + hashlib.sha256(identity).hexdigest()
            else:
                # Preserve the deployed Poste 2 parser, payload and raw-byte ID.
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict) or data.get("device_id") != "poste2":
                    raise InputError("identity_mismatch")
                record_id = "poste2-" + hashlib.sha256(topic.encode() + b"\0" + raw).hexdigest()
        except (ValueError, UnicodeDecodeError, RecursionError):
            self.audit("validation_failure")
            return "invalid"
        record = self.record_factory(id=record_id, revision=1, source="trusted-service", data=data)
        try:
            inserted = self.store.insert("telemetry", record)
        except ValueError as exc:
            if str(exc) != "immutable revision conflict":
                raise
            self.audit("identifier_conflict")
            return "identifier_conflict"
        if not inserted:
            self.audit("duplicate_message")
            return "duplicate"
        return "inserted"

    def on_message(self, client, userdata, message):
        return self.handle(message.topic, message.payload)
