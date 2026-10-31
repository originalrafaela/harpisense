"""Validate the exact published matrix example offline with the P06 validator."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--p06', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[5]
matrix = subprocess.run(
    ['git', '-C', str(root), 'show',
     'fe88645fee55a9922a3633ff941219f7cb15d176:docs/MATRIZ_COMPATIBILIDADE_POSTE1_20261031.md'],
    check=True, capture_output=True, encoding='utf-8',
).stdout
example = re.search(r'```json\s*\n(.*?)\n```', matrix, re.S).group(1)
sys.path.insert(0, str(args.p06.resolve()))
from telemetry_contract.core import parse, fingerprint

topic = 'harpisense/v1/telemetry/harpisense.poste.poste-1/ldr'
payload = parse(example.encode('utf-8'), topic)
assert payload['device_id'] == 'harpisense.poste.poste-1'
assert type(payload['sequence']) is int and 0 <= payload['sequence'] <= 9007199254740991
assert type(payload['measurements']['ldr_adc_raw']) is int
assert 0 <= payload['measurements']['ldr_adc_raw'] <= 4095
assert payload['status']['origin_type'] == 'PHYSICAL'
print(json.dumps({'result': 'PASS', 'scope': 'matrix example with P06 core; not adapter/runtime',
                  'topic': topic, 'fingerprint': fingerprint(payload)}, sort_keys=True))
