"""Read real batches; mutate ONLY temporary copies. Never run collectors or SQL.

No session binding is invented: UNBOUND is a diagnostic label, not a P08 session.
The actual artifact gate must block, and this is not full pipeline validation.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--adapter-dir', type=Path, required=True)
parser.add_argument('--state-root', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.adapter_dir))
from p08_p09_pipeline import run_pipeline

EXPECTED = {
    'mqtt_v4_acabf4a909f00b5f68cfa3c906d58cf1483931902f394c58e4ddc9178e1dc9bf.json': 'cff3245d0be5afb5a792a5d81eed6d721323fd7fb46dfc8f6de5fd1f3b49edae',
    'mqtt_v4_acabf4a909f00b5f68cfa3c906d58cf1483931902f394c58e4ddc9178e1dc9bf.manifest.json': 'daf510c455b18483c61ae0d75e529f9bcde89efb9d43e992e836e229223541b9',
    'mqtt_v4_d94cc2181f5932c7876b065ed9d61533d42542342494ae56b03ddb7ce96a41d1.json': '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945',
    'mqtt_v4_d94cc2181f5932c7876b065ed9d61533d42542342494ae56b03ddb7ce96a41d1.manifest.json': 'cf2661162abfe050c97ef1706adc740c84f794025eadcf1f649472fdc2c260d8',
    'mqtt_collection_checkpoint.json': '7ffe3b525549e4610c8c1a5a8b829cdb8ca6f0845388777960c14909d31a0aa0',
}
audit = args.state_root / 'auditoria_cobertura_p08'
def snapshot():
    return {name: dict(sha256=hashlib.sha256((audit / name).read_bytes()).hexdigest(),
                       mtime_ns=str((audit / name).stat().st_mtime_ns)) for name in EXPECTED}
before = snapshot()
assert {k: v['sha256'] for k, v in before.items()} == EXPECTED, 'Original state changed; stop'
def invoke(batch):
    return run_pipeline(audit, 'UNBOUND-AUXILIARY-AUDIT', None, [], [], [], batch_path=batch)
def blocked(result):
    assert result['authorized_for_inference'] is False
    assert result['authorized_for_ips'] is False
    assert result['log_counts'] == {}
report = dict(captured_at_utc=datetime.now(timezone.utc).isoformat(), python=sys.version,
              adapter_dir=str(args.adapter_dir), state_root=str(args.state_root),
              scope='real batches via candidate/selected code; unbound diagnostic input; no complete P08 session',
              session_binding_verified=False, full_pipeline_validated=False,
              batches=[], isolated_copy_tampering=[])
for name in EXPECTED:
    if not name.startswith('mqtt_v4_') or name.endswith('.manifest.json'): continue
    batch = audit / name
    result = invoke(batch)
    blocked(result)
    auxiliary = result['auxiliary_audit']
    assert result['batch_integrity_verified'] is True
    assert auxiliary['coverage'] == 'UNKNOWN' and auxiliary['log_counts'] == {}
    assert auxiliary['authorized_for_inference'] is False and auxiliary['authorized_for_ips'] is False
    assert auxiliary['rejected_records'] == 0 and auxiliary['continuity_verified'] is False
    assert auxiliary['previous_cursor'] and auxiliary['next_cursor']
    assert result['artifact_consistent'] is False and result['coverage_diagnostic'] is None
    assert any('FileNotFoundError' in reason for reason in result['reasons'])
    assert all(e.get('journal_cursor') and e.get('journal_boot_id') for e in auxiliary['auxiliary_evidence'])
    report['batches'].append(dict(batch=name, batch_integrity_verified=True,
        manifest_sha256=auxiliary['manifest_sha256'], auxiliary_event_count=auxiliary['auxiliary_event_count'],
        event_types=[e['event_type'] for e in auxiliary['auxiliary_evidence']],
        event_traceability_present=all(e.get('journal_cursor') and e.get('journal_boot_id') for e in auxiliary['auxiliary_evidence']),
        manifest_cursors_present=True, rejected_records=auxiliary['rejected_records'], coverage=auxiliary['coverage'],
        authorized_for_inference=False, authorized_for_ips=False, log_counts={},
        artifact_consistent=False, coverage_diagnostic=None, reasons=result['reasons']))
    for mutation in ('batch_bytes', 'manifest_digest', 'missing_manifest'):
        with tempfile.TemporaryDirectory(prefix='harpisense-isolated-batch-copy-') as directory:
            copied = Path(directory) / name
            manifest = copied.with_suffix('.manifest.json')
            copied.write_bytes(batch.read_bytes())
            manifest.write_bytes(batch.with_suffix('.manifest.json').read_bytes())
            if mutation == 'batch_bytes': copied.write_bytes(copied.read_bytes() + b'\n')
            elif mutation == 'manifest_digest':
                value = json.loads(manifest.read_bytes())
                value['events_sha256'] = '0' * 64
                manifest.write_text(json.dumps(value))
            else: manifest.unlink()
            invalid = invoke(copied)
            blocked(invalid)
            assert invalid['batch_integrity_verified'] is False and invalid['auxiliary_audit'] is None
            report['isolated_copy_tampering'].append(dict(batch=name, mutation=mutation,
                rejected=True, reasons=invalid['reasons']))
assert [b['auxiliary_event_count'] for b in report['batches']] == [1, 0]
after = snapshot()
assert after == before, 'Original batches/manifests/checkpoint changed'
report.update(original_state_before=before, original_state_after=after, originals_unchanged=True,
              pipeline_sha256=hashlib.sha256((args.adapter_dir / 'p08_p09_pipeline.py').read_bytes()).hexdigest(),
              adapter_sha256=hashlib.sha256((args.adapter_dir / 'auxiliary_audit_adapter.py').read_bytes()).hexdigest())
print(json.dumps(report, indent=2))
