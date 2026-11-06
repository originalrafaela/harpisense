"""Validate bytes emitted by the actual portable C++ serializer using P06, offline."""
import argparse
import json
import re
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--p06', type=Path, required=True)
parser.add_argument('--fixtures', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.p06.resolve()))
from telemetry_contract.core import parse, fingerprint  # Identified dependency, no copied schema.

topic = 'harpisense/v1/telemetry/harpisense.poste.poste-1/ldr'
messages = []
for raw in args.fixtures.read_bytes().splitlines():
    payload = parse(raw, topic)
    assert payload['device_id'] == 'harpisense.poste.poste-1'
    assert payload['status']['origin_type'] == 'PHYSICAL'
    seq = payload['sequence']
    assert type(seq) is int and 0 <= seq <= 9007199254740991
    assert re.fullmatch(r'harpisense\.poste\.poste-1-[0-9a-f]{16}-' + str(seq), payload['message_id'])
    assert payload['observed_at'].endswith('Z')
    assert 'calibration_version' not in payload['status']
    value = payload['measurements']['ldr_adc_raw']
    assert value is None or type(value) is int and 0 <= value <= 4095
    assert type(payload['measurements']['led_commanded_on']) is bool
    assert len(raw) <= 1024 and len(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()) <= 1024
    assert fingerprint(payload) == fingerprint(parse(raw, topic))
    messages.append(payload)
assert len(messages) == 7
assert len({p['message_id'] for p in messages}) == 7
assert {p['status']['reading_quality'] for p in messages} == {'RAW_UNCALIBRATED', 'UNAVAILABLE', 'OUT_OF_RANGE'}
print('PASS: 7 firmware-generated payloads accepted by P06 and local physical-profile assertions')
