from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lab" / "legitimate-traffic"))

from mqtt_contract import ENVIRONMENT_TOPICS, build_environment_payload, validate_environment_payload  # noqa: E402
from simulate_poste import configured_devices, make_postes, next_payload, publish_payload, write_jsonl  # noqa: E402
from test_subscriber import format_received_message  # noqa: E402


def test_simulated_poste_2_payload_matches_contract() -> None:
    payload = build_environment_payload("poste-2", sequence=42)
    errors = validate_environment_payload(ENVIRONMENT_TOPICS["poste-2"], payload)
    assert errors == []


def test_simulated_poste_3_payload_matches_contract() -> None:
    payload = build_environment_payload("poste-3", sequence=1)
    errors = validate_environment_payload(ENVIRONMENT_TOPICS["poste-3"], payload)
    assert errors == []


def test_topic_mismatch_is_rejected() -> None:
    payload = build_environment_payload("poste-2", sequence=1)
    errors = validate_environment_payload(ENVIRONMENT_TOPICS["poste-3"], payload)
    assert any("topic mismatch" in error for error in errors)


def test_configured_post_count_generates_consistent_poste_ids() -> None:
    args = type(
        "Args",
        (),
        {
            "devices": None,
            "device": None,
            "post_count": 3,
            "device_prefix": "poste-",
            "start_post_number": 2,
        },
    )()

    assert configured_devices(args) == ["poste-2", "poste-3", "poste-4"]


def test_generated_payloads_vary_and_remain_valid() -> None:
    import random

    rng = random.Random(7)
    poste = make_postes(["poste-4"], start_sequence=10, rng=rng)[0]

    first = next_payload(poste, rng)
    second = next_payload(poste, rng)

    assert first["device_id"] == "harpisense.poste.poste-4"
    assert second["device_id"] == first["device_id"]
    assert second["sequence"] == 11
    assert first["measurements"] != second["measurements"]
    assert validate_environment_payload("harpisense/v1/telemetry/harpisense.poste.poste-4/environment", first) == []
    assert validate_environment_payload("harpisense/v1/telemetry/harpisense.poste.poste-4/environment", second) == []


def test_jsonl_mode_writes_session_metadata_and_valid_payloads(tmp_path: Path) -> None:
    import random

    output = tmp_path / "sample.jsonl"
    args = type(
        "Args",
        (),
        {
            "jsonl": str(output),
            "count": 2,
            "duration": 0.0,
            "interval": 0.0,
            "seed": 123,
        },
    )()
    rng = random.Random(args.seed)
    postes = make_postes(["poste-2", "poste-3"], start_sequence=1, rng=rng)

    assert write_jsonl(args, postes, rng) == 0

    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert records[0]["record_type"] == "session_metadata"
    assert records[0]["synthetic"] is True
    assert len(records) == 5

    for record in records[1:]:
        assert record["record_type"] == "telemetry"
        assert record["synthetic"] is True
        assert validate_environment_payload(record["topic"], record["payload"]) == []


def test_subscriber_formats_valid_and_invalid_messages_clearly() -> None:
    payload = build_environment_payload(
        "poste-2",
        sequence=1,
        temperature_c=24.0,
        humidity_pct=61.0,
        rssi_dbm=-58,
        message_id="fixed-message",
    )

    valid = json.loads(format_received_message(ENVIRONMENT_TOPICS["poste-2"], payload, []))
    invalid = json.loads(format_received_message(ENVIRONMENT_TOPICS["poste-2"], payload, ["example error"]))

    assert valid["status"] == "VALID"
    assert invalid["status"] == "INVALID"
    assert invalid["errors"] == ["example error"]


def test_retransmission_reuses_the_same_message_payload() -> None:
    payload = build_environment_payload(
        "poste-2",
        sequence=99,
        temperature_c=25.0,
        humidity_pct=60.0,
        rssi_dbm=-55,
        message_id="same-message-id",
    )
    client = FakeClient([1, 0])

    publish_payload(client, ENVIRONMENT_TOPICS["poste-2"], payload, retries=1)

    assert client.reconnects == 1
    assert len(client.published_payloads) == 2
    assert client.published_payloads[0] == client.published_payloads[1]
    assert json.loads(client.published_payloads[1])["message_id"] == "same-message-id"


class FakePublishResult:
    def __init__(self, rc: int) -> None:
        self.rc = rc

    def wait_for_publish(self) -> None:
        return None


class FakeClient:
    def __init__(self, return_codes: list[int]) -> None:
        self.return_codes = return_codes
        self.published_payloads: list[str] = []
        self.reconnects = 0

    def publish(self, _topic: str, payload: str, qos: int) -> FakePublishResult:
        assert qos == 1
        self.published_payloads.append(payload)
        return FakePublishResult(self.return_codes.pop(0))

    def reconnect(self) -> None:
        self.reconnects += 1
