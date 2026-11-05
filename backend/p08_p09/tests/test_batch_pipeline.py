"""Synthetic fixtures only. No collector, real batch, checkpoint or database."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'adaptador_logs_p08_p09'), str(Path(__file__).parent / 'fixtures')]
import auxiliary_audit_adapter as adapter
import p08_p09_pipeline as pipeline
import previous_pipeline
import previous_auxiliary_audit_adapter as previous_adapter


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def envelope(kind='validation_failure'):
    return {'event': {'event_type': kind, 'source': 'telemetry_consumer',
                      'observed_at': '2026-10-26T12:00:05Z'},
            'journal_cursor': 'SYNTHETIC-cursor-event', 'journal_boot_id': 'SYNTHETIC-boot'}


def write_batch(base, events, **overrides):
    digest = hashlib.sha256(canonical(events)).hexdigest()
    manifest = dict(schema_version='4.0', events_sha256=digest,
                    audit_events_found=len(events), journal_records_read=max(1, len(events)),
                    previous_cursor='SYNTHETIC-previous', next_cursor='SYNTHETIC-next',
                    coverage='UNKNOWN', continuity_verified=False,
                    authorized_for_inference=False, authorized_for_ips=False)
    manifest.update(overrides)
    identity = {key: manifest[key] for key in ('previous_cursor', 'next_cursor', 'events_sha256')}
    name = hashlib.sha256(canonical(identity)).hexdigest()
    batch = base / f'mqtt_v4_{name}.json'
    batch.write_bytes(canonical(events))
    batch.with_suffix('.manifest.json').write_bytes(canonical(manifest))
    return batch


class TestBatchPipeline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='SYNTHETIC-p08-p09-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.session = 'SYNTHETIC-session'
        self.window = dict(window_id='SYNTHETIC-window', window_start='2026-10-26T12:00:00Z',
                           window_end='2026-10-26T12:00:10Z', collection_session_id=self.session,
                           sensor_id='SYNTHETIC-sensor', target_ref='SYNTHETIC-target')

    def run_batch(self, batch, events=None):
        return pipeline.run_pipeline(self.base, self.session, events, [self.window], [],
                                     ['telemetry_consumer'], batch_path=batch)

    def blocked(self, result):
        self.assertIs(result['authorized_for_inference'], False)
        self.assertIs(result['authorized_for_ips'], False)
        self.assertEqual(result['log_counts'], {})
        if result['auxiliary_audit'] is not None:
            auxiliary = result['auxiliary_audit']
            self.assertEqual(auxiliary['coverage'], 'UNKNOWN')
            self.assertIs(auxiliary['authorized_for_inference'], False)
            self.assertIs(auxiliary['authorized_for_ips'], False)
            self.assertEqual(auxiliary['log_counts'], {})

    def synthetic_artifacts(self):
        pcap = self.base / f'{self.session}.pcap'
        pcap.write_bytes(b'SYNTHETIC artifact consistency fixture; not a real capture')
        session = dict(pcap_path=str(pcap), pcap_size_bytes=pcap.stat().st_size,
                       pcap_sha256=hashlib.sha256(pcap.read_bytes()).hexdigest(),
                       collection_complete=False, ready_for_inference=False)
        coverage = dict(session=self.session, collection_complete=False, ready_for_inference=False)
        (self.base / f'{self.session}.session.json').write_bytes(canonical(session))
        (self.base / f'{self.session}.coverage.json').write_bytes(canonical(coverage))
        return pcap

    def test_valid_event_provenance_survives_missing_session(self):
        batch = write_batch(self.base, [envelope()])
        result = self.run_batch(batch)
        self.blocked(result)
        self.assertEqual(result['input_mode'], 'batch')
        self.assertEqual(result['batch_reference'], str(batch))
        self.assertTrue(result['batch_integrity_verified'])
        auxiliary = result['auxiliary_audit']
        self.assertEqual(auxiliary['batch_file'], batch.name)
        self.assertTrue(auxiliary['batch_integrity_verified'])
        self.assertEqual(auxiliary['rejected_records'], 0)
        self.assertEqual(auxiliary['auxiliary_event_count'], 1)
        self.assertEqual(auxiliary['previous_cursor'], 'SYNTHETIC-previous')
        self.assertEqual(auxiliary['next_cursor'], 'SYNTHETIC-next')
        self.assertFalse(auxiliary['continuity_verified'])
        evidence = auxiliary['auxiliary_evidence'][0]
        self.assertEqual(evidence['event_type'], 'telemetry_validation_failure')
        self.assertEqual(evidence['journal_cursor'], 'SYNTHETIC-cursor-event')
        self.assertEqual(evidence['journal_boot_id'], 'SYNTHETIC-boot')
        self.assertFalse(result['artifact_consistent'])
        self.assertIsNone(result['coverage_diagnostic'])
        self.assertIn('FileNotFoundError', result['reasons'][0])

    def test_empty_batch_retains_manifest_provenance(self):
        result = self.run_batch(write_batch(self.base, []))
        self.blocked(result)
        self.assertTrue(result['batch_integrity_verified'])
        self.assertEqual(result['auxiliary_audit']['auxiliary_evidence'], [])
        self.assertEqual(result['auxiliary_audit']['auxiliary_event_count'], 0)
        self.assertEqual(result['auxiliary_audit']['next_cursor'], 'SYNTHETIC-next')

    def test_modified_bytes_and_missing_manifest(self):
        batch = write_batch(self.base, [envelope()])
        batch.write_bytes(batch.read_bytes() + b'\n')
        result = self.run_batch(batch)
        self.assertFalse(result['batch_integrity_verified'])
        self.assertIsNone(result['auxiliary_audit'])
        self.blocked(result)
        batch = write_batch(self.base, [envelope()])
        batch.with_suffix('.manifest.json').unlink()
        result = self.run_batch(batch)
        self.assertFalse(result['batch_integrity_verified'])
        self.assertIn('FileNotFoundError', result['reasons'][0])
        self.blocked(result)

    def test_manifest_tampering_in_isolated_copies(self):
        original = write_batch(self.base, [envelope()])
        original_manifest = original.with_suffix('.manifest.json')
        original_hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (original, original_manifest)]
        mutations = [dict(events_sha256='0' * 64), dict(audit_events_found=2),
                     dict(audit_events_found=True), dict(schema_version='5.0'),
                     dict(previous_cursor='SYNTHETIC-tampered'), dict(next_cursor=''),
                     dict(journal_records_read=0), dict(journal_records_read=True),
                     dict(coverage='COMPLETE'), dict(continuity_verified=True),
                     dict(authorized_for_inference=True), dict(authorized_for_ips=True)]
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=mutation):
                isolated = self.base / f'copy-{index}'
                isolated.mkdir()
                batch = isolated / original.name
                batch.write_bytes(original.read_bytes())
                manifest = json.loads(original_manifest.read_bytes())
                manifest.update(mutation)
                batch.with_suffix('.manifest.json').write_bytes(canonical(manifest))
                result = self.run_batch(batch)
                self.blocked(result)
                self.assertFalse(result['batch_integrity_verified'])
                self.assertIsNone(result['auxiliary_audit'])
        self.assertEqual(original_hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in (original, original_manifest)])

    def test_unknown_event_rejected_even_with_consistent_hashes(self):
        result = self.run_batch(write_batch(self.base, [envelope('unknown-event')]))
        self.blocked(result)
        self.assertFalse(result['batch_integrity_verified'])
        self.assertIsNone(result['auxiliary_audit'])

    def test_missing_traceability_rejected(self):
        for key in ('journal_cursor', 'journal_boot_id'):
            with self.subTest(key=key):
                event = envelope()
                event.pop(key)
                result = self.run_batch(write_batch(self.base, [event]))
                self.blocked(result)
                self.assertFalse(result['batch_integrity_verified'])

    def test_malformed_batch_manifest_and_envelope(self):
        for content in (b'{', b'{}'):
            with self.subTest(batch=content):
                batch = write_batch(self.base, [envelope()])
                batch.write_bytes(content)
                self.blocked(self.run_batch(batch))
                self.assertFalse(self.run_batch(batch)['batch_integrity_verified'])
        for content in (b'{', b'[]'):
            with self.subTest(manifest=content):
                batch = write_batch(self.base, [envelope()])
                batch.with_suffix('.manifest.json').write_bytes(content)
                self.assertFalse(self.run_batch(batch)['batch_integrity_verified'])
        for event in (None, {'event': None}):
            self.assertFalse(self.run_batch(write_batch(self.base, [event]))['batch_integrity_verified'])

    def test_both_inputs_rejected_before_io_even_empty_events(self):
        for events in ([], [envelope()]):
            with self.subTest(events=events), patch.object(pipeline, 'prepare_auxiliary_audit_batch') as batch_call, patch.object(pipeline, 'prepare_auxiliary_audit') as events_call, patch.object(pipeline, 'validate_p08_artifacts') as gate:
                result = self.run_batch(self.base / 'absent.json', events=events)
                self.blocked(result)
                self.assertEqual(result['input_mode'], 'conflict')
                self.assertFalse(result['batch_integrity_verified'])
                batch_call.assert_not_called()
                events_call.assert_not_called()
                gate.assert_not_called()

    def test_normalizes_once_and_never_feeds_auxiliary_counts(self):
        self.synthetic_artifacts()
        batch = write_batch(self.base, [envelope()])
        with patch.object(adapter, 'prepare_auxiliary_audit', wraps=adapter.prepare_auxiliary_audit) as normalize, patch.object(pipeline, 'prepare_auxiliary_audit', wraps=adapter.prepare_auxiliary_audit) as old_entry, patch.object(pipeline, 'prepare_verified_log_counts', wraps=pipeline.prepare_verified_log_counts) as gate:
            result = self.run_batch(batch)
            self.blocked(result)
            self.assertTrue(result['artifact_consistent'])
            normalize.assert_called_once()
            old_entry.assert_not_called()
            gate.assert_called_once()
            self.assertEqual(gate.call_args.kwargs['events'], [])

    def test_artifact_and_coverage_gates_not_bypassed(self):
        pcap = self.synthetic_artifacts()
        batch = write_batch(self.base, [envelope()])
        result = self.run_batch(batch)
        self.blocked(result)
        self.assertTrue(result['artifact_consistent'])
        self.assertIsNotNone(result['coverage_diagnostic'])
        self.assertTrue(any('insuficiente' in reason for reason in result['reasons']))
        self.assertTrue(any('Procedência independente' in reason for reason in result['reasons']))
        pcap.write_bytes(b'SYNTHETIC-modified')
        result = self.run_batch(batch)
        self.blocked(result)
        self.assertTrue(result['batch_integrity_verified'])
        self.assertFalse(result['artifact_consistent'])
        self.assertIsNone(result['coverage_diagnostic'])

    def test_legacy_results_unchanged_and_no_forged_batch_integrity(self):
        for artifacts in (False, True):
            if artifacts: self.synthetic_artifacts()
            for events in ([], [envelope()], [envelope('duplicate_message')],
                           [envelope('unknown-event')], [None, {'event': None}], None, {}):
                with self.subTest(artifacts=artifacts, events=events):
                    snapshot = copy.deepcopy(events)
                    args = (self.base, self.session, events, [self.window], [], ['telemetry_consumer'])
                    before = previous_pipeline.run_pipeline(*args)
                    after = pipeline.run_pipeline(*args)
                    self.assertEqual(before, {key: after[key] for key in before})
                    self.assertEqual(events, snapshot)
                    self.assertFalse(after['batch_integrity_verified'])
                    self.blocked(after)
                    if after['auxiliary_audit'] is not None:
                        self.assertNotIn('batch_integrity_verified', after['auxiliary_audit'])
                        self.assertEqual(previous_adapter.prepare_auxiliary_audit(events), adapter.prepare_auxiliary_audit(events))


if __name__ == '__main__':
    unittest.main()
