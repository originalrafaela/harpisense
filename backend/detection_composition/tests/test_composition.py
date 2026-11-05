"""Actual sklearn fitting/inference on declared synthetic data, real PostgreSQL/P11.

No mock inference, no laboratory performance claim, no network attack.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import unittest
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import psycopg
from fastapi.testclient import TestClient
from harpisense_contracts import fingerprint, validate, validate_links
from harpisense_data.windows import FEATURES, versions
from harpisense_rf.demo_sintetico import make_session as rf_session
from harpisense_if.demo_sintetico import make_session as if_session
from harpisense_rf.random_forest import train_model as train_rf, save_bundle as save_rf
from harpisense_if.isolation_forest import train_model as train_if, save_bundle as save_if
from harpisense_engines.core import decide
from delivery.projections import create_app
from detection_composition.core import Composition, DependencyBlocked, load_artifact
from detection_composition.store import CompositionStore

ROOT = Path(__file__).resolve().parents[3]
NOW = '2026-11-04T18:00:11+00:00'


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['DATABASE_URL']
        if not cls.dsn.endswith('/detection_composition_test'):
            raise RuntimeError('Only the dedicated disposable test database is allowed')
        cls.artifacts = ROOT / 'local-evidence/detection-composition' / os.urandom(8).hex()
        cls.artifacts.mkdir(parents=True)
        rf_train = pd.concat([rf_session('rf-train-'+str(i), 12, i) for i in range(2)])
        rf_cal = pd.concat([rf_session('rf-cal-'+str(i), 12, 10+i) for i in range(2)])
        rf_train = rf_train[rf_train.label.isin(['normal', 'C01'])]
        rf_cal = rf_cal[rf_cal.label.isin(['normal', 'C01'])]
        if_train = pd.concat([if_session('if-train-'+str(i), 150, 20+i) for i in range(2)])
        if_cal = pd.concat([if_session('if-cal-'+str(i), 150, 30+i) for i in range(2)])
        rf = train_rf(rf_train, rf_cal, features=FEATURES, classes=['normal', 'C01'],
                      profile='demo_tcp_ingress', trees=20)
        isolation = train_if(if_train, if_cal, features=FEATURES,
                             profile='demo_tcp_ingress', n_estimators=20)
        cls.dataset_hashes = {}
        for name, frame, bundle, role in [('rf-train', rf_train, rf, 'train'),
                ('rf-calibration', rf_cal, rf, 'calibration'),
                ('if-train', if_train, isolation, 'train'),
                ('if-calibration', if_cal, isolation, 'calibration')]:
            path = cls.artifacts / (name + '.csv')
            frame.to_csv(path, index=False)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            cls.dataset_hashes[name] = digest
            bundle.setdefault('dataset_sha256', {})[role] = digest
        save_rf(rf, cls.artifacts / 'rf')
        save_if(isolation, cls.artifacts / 'if')
        cls.args = dict(rf_directory=cls.artifacts/'rf', if_directory=cls.artifacts/'if',
                        rf_sha256=hashlib.sha256((cls.artifacts/'rf/model.joblib').read_bytes()).hexdigest(),
                        if_sha256=hashlib.sha256((cls.artifacts/'if/model.joblib').read_bytes()).hexdigest())
        cls.store = CompositionStore(cls.dsn)
        cls.composition = Composition(cls.store, **cls.args)
        frame = rf_session('synthetic-inference-only', 1, 93)
        cls.window = {k: v for k, v in frame[frame.label == 'C01'].iloc[0].to_dict().items()
                      if k in FEATURES or k in ['window_id', 'collection_session_id',
                          'feature_schema_version', 'window_seconds', 'traffic_profile']}
        cls.window.update(sensor_id='synthetic-sensor', window_start='2026-11-04T18:00:00+00:00',
                          window_end='2026-11-04T18:00:10+00:00')
        with psycopg.connect(cls.dsn) as conn:
            conn.execute((ROOT/'backend/delivery/001_local.sql').read_text())

    def setUp(self):
        with psycopg.connect(self.dsn) as conn:
            conn.execute('TRUNCATE projections')

    def run_composition(self, **kwargs):
        return self.composition.process_synthetic(copy.deepcopy(self.window), now=NOW,
            asset={'asset_ref':'synthetic-asset', 'criticality':50, 'scope_ref':'synthetic-scope',
                   'inventory_version':'synthetic-test-only-v1'}, **kwargs)

    def count(self):
        with psycopg.connect(self.dsn) as conn:
            return conn.execute('SELECT count(*) FROM projections').fetchone()[0]

    def test_01_real_estimators_canonical_records_postgres_and_authenticated_p11(self):
        result = self.run_composition()
        rf, isolation = result['detections']
        validate_links(detections=result['detections'], explanations=[],
                       incidents=[result['incident']], decisions=[result['decision']])
        self.assertEqual(rf['model']['detector'], 'random_forest')
        self.assertEqual(isolation['model']['detector'], 'isolation_forest')
        self.assertAlmostEqual(sum(rf['classification']['probabilities'].values()), 1)
        self.assertIn('anomaly_score', isolation['anomaly'])
        self.assertEqual(result['incident']['risk']['status'], 'COMPLETE')
        self.assertEqual(result['decision']['status'], 'OBSERVE_ONLY')
        self.assertFalse(result['decision']['execution_requested'])
        self.assertFalse(result['execution_performed'])
        self.assertEqual(self.count(), 6)
        client = TestClient(create_app(self.store, username='test-admin', password='test-only-password'))
        receipts = {}
        for kind, expected in [('detection', 2), ('incident', 1), ('risk', 1), ('decision', 1), ('window', 1)]:
            self.assertEqual(client.get('/api/v1/p11/'+kind).status_code, 401)
            response = client.get('/api/v1/p11/'+kind, auth=('test-admin', 'test-only-password'))
            self.assertEqual(response.status_code, 200)
            rows = response.json()
            self.assertEqual(len(rows), expected)
            self.assertTrue(all(row['source'] == 'synthetic' for row in rows))
            receipts[kind] = rows
        incident_id = result['incident']['incident_id']
        history = client.get('/api/v1/p11/incident/'+incident_id+'/history',
                             auth=('test-admin', 'test-only-password'))
        self.assertEqual(history.json()[0]['data'], result['incident'])
        out = ROOT/'docs/evidence/detection-composition-20261104'
        out.mkdir(parents=True, exist_ok=True)
        (out/'composition.json').write_text(json.dumps(dict(input_origin='synthetic',
            real_estimators=True, laboratory_validated=False, statistical_validation=False,
            dataset_sha256=self.dataset_hashes, versions=versions(), result=result,
            p11_receipts=receipts), indent=2, ensure_ascii=False, allow_nan=False)+'\n')

    def test_missing_feature_invalid_types_profile_and_units_do_not_write(self):
        variants = []
        missing = copy.deepcopy(self.window); del missing['syn_count']; variants.append(missing)
        for key, value in [('packet_count', True), ('packets_per_second', 999),
                           ('mean_interarrival_ms', 10001), ('traffic_profile', 'unknown'),
                           ('window_seconds', 20), ('bytes_total', float('nan'))]:
            variants.append({**self.window, key:value})
        for window in variants:
            with self.subTest(window=window), self.assertRaises(ValueError):
                self.composition.process_synthetic(window, now=NOW)
            self.assertEqual(self.count(), 0)

    def test_reprocessing_keeps_original_snapshot_and_rejects_changed_input(self):
        first = self.run_composition()
        replay = self.composition.process_synthetic(self.window, now='2026-11-04T18:00:12+00:00',
            asset={'asset_ref':'synthetic-asset', 'criticality':50, 'scope_ref':'synthetic-scope',
                   'inventory_version':'synthetic-test-only-v1'})
        self.assertTrue(replay.pop('replayed'))
        first.pop('replayed')
        self.assertEqual(first, replay)
        with self.assertRaisesRegex(ValueError, 'identifier conflict'):
            self.composition.process_synthetic({**self.window, 'rst_count':1}, now=NOW)
        self.assertEqual(self.count(), 6)

    def test_concurrent_reprocessing_commits_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.run_composition(), range(2)))
        self.assertEqual(sorted(r['replayed'] for r in results), [False, True])
        self.assertEqual(self.count(), 6)

    def test_inference_and_persistence_failure_leave_no_partial_records(self):
        with self.assertRaises(ValueError):
            self.run_composition(mode=4)
        self.assertEqual(self.count(), 0)
        # Real SQL constraint failure during insertion after earlier rows.
        with psycopg.connect(self.dsn) as conn:
            conn.execute("ALTER TABLE projections ADD CONSTRAINT composition_test_failure CHECK(kind <> 'risk')")
        try:
            with self.assertRaises(psycopg.errors.CheckViolation):
                self.run_composition()
            self.assertEqual(self.count(), 0)
        finally:
            with psycopg.connect(self.dsn) as conn:
                conn.execute('ALTER TABLE projections DROP CONSTRAINT composition_test_failure')

    def test_expired_future_window_and_missing_asset_do_not_fabricate_risk(self):
        for now in ['2026-11-04T18:02:00+00:00', '2026-11-04T17:59:59+00:00']:
            with self.assertRaises(ValueError):
                self.composition.process_synthetic(self.window, now=now)
        result = self.composition.process_synthetic(self.window, now=NOW)
        self.assertEqual(result['incident']['risk']['status'], 'INCOMPLETE')
        self.assertIsNone(result['incident']['risk']['score'])
        self.assertEqual(result['decision']['status'], 'OBSERVE_ONLY')

    def test_artifact_hash_and_missing_bundle_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            load_artifact(self.artifacts/'rf', expected_sha256='0'*64, detector='random_forest')
        with self.assertRaises(DependencyBlocked) as caught:
            load_artifact(self.artifacts/'missing', expected_sha256='0'*64, detector='random_forest')
        self.assertIn('model.joblib', str(caught.exception))

    def test_cli_loads_pinned_artifacts_and_writes_explicit_synthetic_input(self):
        source = self.artifacts/'input.synthetic.json'
        source.write_text(json.dumps(dict(window=self.window)))
        result = subprocess.run([sys.executable, '-B', '-m', 'detection_composition',
            '--rf-directory', str(self.args['rf_directory']), '--rf-sha256', self.args['rf_sha256'],
            '--if-directory', str(self.args['if_directory']), '--if-sha256', self.args['if_sha256'],
            '--input', str(source), '--input-origin', 'synthetic', '--now', NOW],
            capture_output=True, text=True, check=True)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['input_origin'], 'synthetic')
        self.assertFalse(receipt['execution_performed'])
        self.assertEqual(self.count(), 6)

    def test_delivered_p08_gate_cannot_be_overridden(self):
        with self.assertRaises(DependencyBlocked) as caught:
            self.composition.process_p08(base_dir='/nonexistent-test-session', session_name='synthetic',
                events=[], window=self.window, coverage_records=[], required_sources=['tcpdump'])
        self.assertFalse(caught.exception.diagnostic['authorized_for_inference'])
        self.assertEqual(self.count(), 0)

    def test_temporal_coverage_unknown_and_signed_provenance_still_block_counts(self):
        from log_coverage_integration import prepare_verified_log_counts
        window = {**self.window, 'target_ref':'synthetic-target'}
        for records, verified in [([], False), ([dict(source='tcpdump', verified=True,
                verification_method='ed25519_signed_manifest_and_interval_chain',
                evidence_refs=[dict(signature_verified=True, manifest_sha256='a'*64)],
                collection_session_id=window['collection_session_id'], sensor_id=window['sensor_id'],
                target_ref=window['target_ref'], start=window['window_start'], end=window['window_end'])], True)]:
            gate = prepare_verified_log_counts([], [window], records, ['tcpdump'],
                                               coverage_provenance_verified=verified)
            self.assertFalse(gate['authorized_for_inference'])
            self.assertEqual(gate['log_counts'], {})
            self.assertTrue(gate['reasons'])

    def test_policy_modes_and_protection_using_existing_declared_fixtures(self):
        # Contract/gate regression only: these records are not model inference.
        import sys
        sys.path.insert(0, str(ROOT/'backend/delivery_tests'))
        from policy_fixtures import context, NOW as fixture_now
        from harpisense_catalog import CATALOG
        covered_groups = set()
        for case in CATALOG:
            ctx = context(case)
            group = CATALOG[case]['group']
            covered_groups.add(group)
            for mode in (1, 2, 3):
                expected = 'REQUEST_APPROVAL' if mode == 1 or (mode == 2 and group != 'Low') else 'AUTHORIZED'
                result = decide(ctx, now=fixture_now, mode=mode)
                self.assertEqual(result['decision']['status'], expected)
                self.assertFalse(result['decision']['execution_requested'])
            for gate in ('verified', 'scope_allowed', 'executor_ready'):
                blocked = copy.deepcopy(ctx); blocked['target'][gate] = None
                self.assertEqual(decide(blocked, now=fixture_now, mode=3)['decision']['status'], 'OBSERVE_ONLY')
            protected = copy.deepcopy(ctx); protected['target']['protected'] = True
            self.assertEqual(decide(protected, now=fixture_now, mode=3)['decision']['status'], 'OBSERVE_ONLY')
        self.assertEqual(covered_groups, {'Low', 'Medium', 'Hard'})


if __name__ == '__main__':
    unittest.main()
