from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lab" / "legitimate-traffic"))

from mqtt_contract import ENVIRONMENT_TOPICS, build_environment_payload, validate_environment_payload  # noqa: E402


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
