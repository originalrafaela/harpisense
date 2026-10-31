"""Administrative envelopes, separate from the five canonical P03 records."""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json
import re

from jsonschema import Draft202012Validator
from harpisense_contracts.canonical import canonical_json, fingerprint

VERSION = "1.0.0"
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"
REF_PATTERN = r"^secret://[a-z0-9][a-z0-9-]{0,31}/[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"


class ConfigError(ValueError):
    """Only stable codes; never include submitted keys/values in errors."""


class Binding(TypedDict):
    sensor_id: str
    network: str
    observation_point: str


class Parameters(TypedDict, total=False):
    display_name: str
    timezone: str
    network_cidrs: list[str]
    sensor_bindings: list[Binding]
    capture_filter_profile: str
    capture_window_seconds: Literal[10]
    feature_schema_version: str
    mqtt_broker_host: str
    mqtt_broker_port: int
    mqtt_tls_mode: Literal["required"]
    mqtt_ca_ref: str
    mqtt_identity_secret_ref: str
    mqtt_topics: list[str]
    mqtt_client_id: str
    rf_model_ref: str
    if_model_ref: str
    protocol_adapter_ref: str
    external_credential_ref: str
    vpn_auth_ref: str


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


def text(max_length=128, pattern=None):
    result = {"type": "string", "minLength": 1, "maxLength": max_length}
    if pattern:
        result["pattern"] = pattern
    return result


IDENTIFIER = text(64, ID_PATTERN)
REFERENCE = text(140, REF_PATTERN)
PARAMETER_SCHEMA = obj({
    "display_name": text(100, r"^[^\x00-\x1f\x7f]+$"),
    "timezone": text(64, r"^[A-Za-z0-9_+/-]+$"),
    "network_cidrs": {"type": "array", "minItems": 1, "maxItems": 64,
                      "uniqueItems": True, "items": text(64)},
    "sensor_bindings": {"type": "array", "minItems": 1, "maxItems": 128,
                        "uniqueItems": True, "items": obj({
                            "sensor_id": IDENTIFIER, "network": text(64),
                            "observation_point": IDENTIFIER})},
    "capture_filter_profile": IDENTIFIER,
    "capture_window_seconds": {"type": "integer", "const": 10},
    "feature_schema_version": {"const": "harpisense.if.window.v1"},
    "mqtt_broker_host": text(253),
    "mqtt_broker_port": {"type": "integer", "minimum": 1, "maximum": 65535},
    "mqtt_tls_mode": {"const": "required"},
    "mqtt_ca_ref": IDENTIFIER,
    "mqtt_identity_secret_ref": REFERENCE,
    "mqtt_topics": {"type": "array", "minItems": 1, "maxItems": 64,
                    "uniqueItems": True, "items": text(256, r"^[A-Za-z0-9_./-]+$")},
    "mqtt_client_id": IDENTIFIER,
    "rf_model_ref": IDENTIFIER, "if_model_ref": IDENTIFIER,
    "protocol_adapter_ref": IDENTIFIER,
    "external_credential_ref": REFERENCE, "vpn_auth_ref": REFERENCE,
}, [])
PARAMETER_SCHEMA["minProperties"] = 1
DOCUMENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:harpisense:config.document:1.0.0",
    **obj({"schema_version": {"const": VERSION}, "record_type": {"const": "config.document"},
           "parameters": PARAMETER_SCHEMA}),
}
REQUEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:harpisense:config.proposal:1.0.0",
    **obj({"schema_version": {"const": VERSION},
           "record_type": {"const": "config.proposal"},
           "request_id": text(36, r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
           "idempotency_key": text(128, r"^[A-Za-z0-9_.-]{8,128}$"),
           "expected_revision": {"type": "integer", "minimum": 0},
           "reason_code": {"enum": ["INITIAL_IMPORT", "ADMIN_CHANGE", "RESTORE"]},
           "document": DOCUMENT_SCHEMA}),
}


def checked(value, schema):
    try:
        # Canonical P03 serialization also rejects NaN and unsupported Python types.
        encoded = canonical_json(value)
        if len(encoded.encode("utf-8")) > 65536:
            raise ConfigError("DOCUMENT_TOO_LARGE")
        result = json.loads(encoded)
        if not Draft202012Validator(schema).is_valid(result):
            raise ConfigError("INVALID_CONFIG_SCHEMA")
        return result
    except (ValueError, TypeError, RecursionError):
        raise ConfigError("INVALID_CONFIG_SCHEMA") from None


def validate_document(value):
    result = checked(value, DOCUMENT_SCHEMA)
    p = result["parameters"]
    try:
        if "timezone" in p:
            ZoneInfo(p["timezone"])
        networks = [ip_network(n, strict=True) for n in p.get("network_cidrs", [])]
        if any(a.version == b.version and a.overlaps(b)
               for i, a in enumerate(networks) for b in networks[i + 1:]):
            raise ConfigError("AMBIGUOUS_NETWORKS")
        bindings = p.get("sensor_bindings", [])
        if bool(networks) != bool(bindings):
            raise ConfigError("NETWORK_SENSOR_BINDING_REQUIRED")
        if len({(b["sensor_id"], b["network"]) for b in bindings}) != len(bindings):
            raise ConfigError("AMBIGUOUS_SENSOR_BINDING")
        bound = {ip_network(b["network"], strict=True) for b in bindings}
        if bound != set(networks):
            raise ConfigError("NETWORK_SENSOR_BINDING_REQUIRED")
        if "capture_window_seconds" in p or "rf_model_ref" in p or "if_model_ref" in p:
            if p.get("feature_schema_version") != "harpisense.if.window.v1":
                raise ConfigError("FEATURE_SCHEMA_REQUIRED")
        if "mqtt_broker_host" in p:
            required = {"mqtt_broker_port", "mqtt_tls_mode", "mqtt_ca_ref",
                        "mqtt_identity_secret_ref", "mqtt_topics", "mqtt_client_id"}
            if not required <= p.keys():
                raise ConfigError("INCOMPLETE_MQTT_CONFIG")
            host = p["mqtt_broker_host"]
            try:
                ip_address(host)
            except ValueError:
                if not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                           for label in host.split(".")):
                    raise ConfigError("INVALID_BROKER_HOST")
        elif any(key.startswith("mqtt_") for key in p):
            raise ConfigError("INCOMPLETE_MQTT_CONFIG")
    except ConfigError:
        raise
    except (ValueError, ZoneInfoNotFoundError):
        raise ConfigError("INVALID_CONFIG_VALUE") from None
    return result


@dataclass(frozen=True)
class Capabilities:
    """Trusted deployment manifest, never taken from proposal JSON.

    Catalog membership is validation evidence, not connectivity/visibility evidence.
    Model pairs contain (reference, feature schema); approved artifacts remain external.
    """
    revision: str
    secret_refs: frozenset[str] = frozenset()
    ca_refs: frozenset[str] = frozenset()
    mqtt_hosts: frozenset[str] = frozenset()
    mqtt_topics: frozenset[str] = frozenset()
    network_cidrs: frozenset[str] = frozenset()
    sensors: frozenset[tuple[str, str]] = frozenset()
    capture_profiles: frozenset[str] = frozenset()
    rf_models: frozenset[tuple[str, str]] = frozenset()
    if_models: frozenset[tuple[str, str]] = frozenset()
    protocol_adapters: frozenset[str] = frozenset()

    @property
    def digest(self):
        return fingerprint({key: sorted(value) if isinstance(value, frozenset) else value
                            for key, value in vars(self).items()})

    def validate(self, document):
        document = validate_document(document)
        p = document["parameters"]
        checks = [(all(v in self.secret_refs for k, v in p.items() if k.endswith("secret_ref")
                       or k in {"external_credential_ref", "vpn_auth_ref"}), "UNKNOWN_SECRET_REFERENCE")]
        for field, allowed in (("mqtt_ca_ref", self.ca_refs), ("mqtt_broker_host", self.mqtt_hosts),
                               ("capture_filter_profile", self.capture_profiles),
                               ("protocol_adapter_ref", self.protocol_adapters)):
            checks.append((field not in p or p[field] in allowed, "UNSUPPORTED_REFERENCE"))
        checks.append((set(p.get("mqtt_topics", [])) <= self.mqtt_topics, "TOPIC_OUTSIDE_ACL"))
        allowed_networks = [ip_network(n, strict=True) for n in self.network_cidrs]
        checks.append((all(any(network.version == scope.version and network.subnet_of(scope)
                               for scope in allowed_networks)
                           for network in (ip_network(n, strict=True) for n in p.get("network_cidrs", []))),
                       "NETWORK_OUTSIDE_SCOPE"))
        checks.append((all((b["sensor_id"], b["observation_point"]) in self.sensors
                           for b in p.get("sensor_bindings", [])), "UNKNOWN_SENSOR"))
        for field, models in (("rf_model_ref", self.rf_models), ("if_model_ref", self.if_models)):
            checks.append((field not in p or (p[field], p.get("feature_schema_version")) in models,
                           "INCOMPATIBLE_MODEL"))
        for passed, code in checks:
            if not passed:
                raise ConfigError(code)
        return document


def components_for(before, after):
    old, new = before.get("parameters", {}), after["parameters"]
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    groups = set()
    for key in changed:
        if key.startswith("mqtt_"): groups.add("mqtt")
        elif key in {"network_cidrs", "sensor_bindings", "capture_filter_profile", "capture_window_seconds"}:
            groups.add("p08")
        elif key in {"rf_model_ref", "if_model_ref", "feature_schema_version", "protocol_adapter_ref"}:
            groups.add("pipeline")
        elif key == "external_credential_ref": groups.add("backup")
        elif key == "vpn_auth_ref": groups.add("vpn")
        else: groups.add("config-registry")
    return sorted(groups)
