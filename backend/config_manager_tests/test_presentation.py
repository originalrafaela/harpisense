"""Real SQL, runtime artifacts and independent consumer; no public fault knobs."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import tempfile
import threading
import unittest
from uuid import uuid4

import psycopg
from config_manager.schema import Capabilities, ConfigError
from config_manager.store import ConfigStore, Conflict, migrate
from config_manager.presentation import PresentationApplicator
from test_config_manager import request, document


@unittest.skipUnless(os.getenv('HARPISENSE_CONFIG_TEST_DSN'), 'Isolated PostgreSQL required')
class PresentationTests(unittest.TestCase):
    def setUp(self):
        dsn = os.environ['HARPISENSE_CONFIG_TEST_DSN']
        self.connect = lambda: psycopg.connect(dsn)
        with self.connect() as conn:
            if conn.info.dbname != 'config_fixture': raise RuntimeError('Fixture only')
        migrate(self.connect)
        self.store = ConfigStore(self.connect, Capabilities(revision='presentation-tests'))
        self.installation = 'present-' + uuid4().hex
        self.store.provision_registry(self.installation)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.worker = PresentationApplicator(self.store, self.installation, self.temp.name)

    def propose(self, name='Display one', zone='America/Sao_Paulo'):
        head = self.store.current(self.installation)
        op = self.store.propose(self.installation, 'test-admin', request(
            head['desired_revision'], document(display_name=name, timezone=zone)))
        return self.store.validate(op['operation_id'], 'test-admin', op['revision'])

    def test_effective_only_after_consumption_idempotency_and_restart(self):
        op = self.propose()
        self.assertIsNone(self.store.current(self.installation)['effective_revision'])
        result = self.worker.apply(op['operation_id'], op['revision'])
        self.assertEqual(result['status'], 'APPLIED')
        self.assertFalse(result['operational'])
        value = result['presentation']
        self.assertEqual(value['displayed_instant'], '2026-11-01T09:00:00-03:00')
        self.assertEqual(value['original_instant'], '2026-11-01T12:00:00Z')
        self.assertEqual(self.store.current(self.installation)['effective_revision'], 1)
        self.assertTrue(self.worker.apply(op['operation_id'], 1)['idempotent'])
        fresh = PresentationApplicator(self.store, self.installation, self.temp.name)
        fresh.recover()
        self.assertEqual(fresh.observe(), value)
        self.assertEqual([e['event'] for e in self.store.history(self.installation)],
                         ['PROPOSED','VALIDATED','APPLYING','VERIFIED','APPLIED'])

    def test_restores_prior_values_and_audits_rollback_after_effects(self):
        first = self.propose()
        self.worker.apply(first['operation_id'], 1)
        second = self.propose('Must roll back', 'Asia/Tokyo')
        def fault(stage):
            if stage == 'after_verify': raise OSError('fixture')
        self.worker.fault = fault
        result = self.worker.apply(second['operation_id'], 2)
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['recovery'], 'rolled_back')
        self.assertEqual(result['presentation']['parameters']['display_name'], 'Display one')
        self.assertTrue(result['presentation']['verified'])
        self.assertEqual(self.store.current(self.installation)['effective_revision'], 1)
        self.assertEqual(self.store.history(self.installation)[-1]['result_code'], 'PRESENTATION_ROLLBACK_VERIFIED')

    def test_failed_recovery_unknown_and_restart_reconciliation(self):
        op = self.propose()
        def fault(stage):
            if stage in {'after_write','rollback_write'}: raise OSError('fixture')
        self.worker.fault = fault
        result = self.worker.apply(op['operation_id'], 1)
        self.assertEqual(result['status'], 'RECOVERY_REQUIRED')
        self.assertFalse(result['presentation']['verified'])
        self.assertEqual(result['presentation']['status'], 'unknown')
        with self.assertRaises(Conflict): self.worker.apply(op['operation_id'], 1)
        fresh = PresentationApplicator(self.store, self.installation, self.temp.name)
        fresh.recover()
        self.assertEqual(fresh.observe()['parameters']['display_name'], 'HarpiSense')
        self.assertIsNone(self.store.current(self.installation)['active_operation'])
        self.assertEqual(self.store.revision(self.installation, 1)['status'], 'FAILED')

    def test_process_interruption_and_obsolete_fence(self):
        op = self.propose()
        def crash(stage):
            if stage == 'after_write': raise KeyboardInterrupt()
        self.worker.fault = crash
        with self.assertRaises(KeyboardInterrupt): self.worker.apply(op['operation_id'], 1)
        head = self.store.current(self.installation)
        self.store.fail_application(op['operation_id'], 'test-worker', head['fence'])
        old = json.loads(self.worker.journal_path.read_text())
        with self.assertRaises(Conflict): self.worker._guarded_write(old, old['target'])
        fresh = PresentationApplicator(self.store, self.installation, self.temp.name)
        fresh.recover()
        self.assertEqual(fresh.observe()['status'], 'bootstrap_defaults')

    def test_superseded_scope_name_and_zone_are_rejected(self):
        first = self.propose()
        second = self.propose('Second')
        with self.assertRaises(Conflict): self.worker.apply(first['operation_id'], 1)
        for p in ({'display_name':'   ','timezone':'UTC'},
                  {'display_name':'valid','timezone':'Invalid/Zone'},
                  {'display_name':'valid','timezone':'UTC','capture_filter_profile':'x'}):
            from config_manager.presentation import parameters
            with self.assertRaises(ConfigError): parameters(p)
        self.assertFalse(self.worker.consumer.path.exists())

    def test_simultaneous_workers_have_one_effect_and_old_content_is_immutable(self):
        op = self.propose()
        entered, release = threading.Event(), threading.Event()
        def pause(stage):
            if stage == 'before_write': entered.set(); release.wait(10)
        self.worker.fault = pause
        with ThreadPoolExecutor(2) as pool:
            one = pool.submit(self.worker.apply, op['operation_id'], 1)
            self.assertTrue(entered.wait(5))
            other = PresentationApplicator(self.store, self.installation, self.temp.name)
            try:
                with self.assertRaises(Conflict): other.apply(op['operation_id'], 1)
            finally: release.set()
            self.assertEqual(one.result()['status'], 'APPLIED')
        with self.connect() as conn:
            original = conn.execute('SELECT document FROM hs_config.revision WHERE installation_id=%s', (self.installation,)).fetchone()[0]
        self.assertEqual(original['parameters']['timezone'], 'America/Sao_Paulo')
        self.assertEqual([e['event'] for e in self.store.history(self.installation)].count('APPLIED'), 1)

    def test_runtime_drift_never_claims_effective_consumption(self):
        op = self.propose()
        self.worker.apply(op['operation_id'], 1)
        value = self.worker.consumer.read()
        value['parameters']['display_name'] = 'Changed outside application'
        self.worker._write(self.worker.consumer.path, value)
        self.assertFalse(self.worker.observe()['verified'])
        with self.assertRaises(ConfigError): self.worker.apply(op['operation_id'], 1)

    def test_corrupt_prior_journal_never_confirms_rollback(self):
        op = self.propose()
        def crash(stage):
            if stage == 'after_write': raise KeyboardInterrupt()
        self.worker.fault = crash
        with self.assertRaises(KeyboardInterrupt): self.worker.apply(op['operation_id'], 1)
        journal = json.loads(self.worker.journal_path.read_text())
        journal['before']['parameters']['display_name'] = 'Corrupted prior state'
        self.worker._write(self.worker.journal_path, journal)
        fresh = PresentationApplicator(self.store, self.installation, self.temp.name)
        with self.assertRaises(ConfigError): fresh.recover()
        self.assertFalse(fresh.observe()['verified'])
        self.assertIsNotNone(self.store.current(self.installation)['active_operation'])


import test_api as http_fixture
from fastapi.testclient import TestClient
from unittest.mock import patch
from delivery.app import build_candidate_app


class PresentationHttpTests(http_fixture.ApiTests):
    """Run existing HTTP regressions again with the real applicator installed."""
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        with patch.dict(os.environ, DATABASE_URL=self.dsn,
                        HARPISENSE_ADMIN_USER='technical-fixture',
                        HARPISENSE_ADMIN_PASSWORD='technical-fixture-password'):
            candidate = build_candidate_app(installation_id=self.installation,
                capabilities=self.store.capabilities, allowed_origins=['http://localhost'],
                presentation_directory=directory.name)
        self.client = TestClient(candidate)

    def test_apply_requires_session_scope_and_fresh_password_not_browser_receipt(self):
        req = request(doc=document(display_name='HTTP display', timezone='UTC'))
        operation = self.client.post('/api/v1/config/proposals', headers=self.headers, json=req).json()
        key = operation['operation_id']
        self.client.post(f'/api/v1/config/proposals/{key}/validate', headers=self.headers, json={'expected_revision':1})
        url = f'/api/v1/config/proposals/{key}/apply'
        self.assertEqual(self.client.post(url, json={}).status_code, 401)
        self.assertEqual(self.client.post(url, headers=self.headers, json={'expected_revision':1}).status_code, 422)
        wrong = self.client.post(url, headers=self.headers, json={'expected_revision':1,'current_password':'wrong-secret'})
        self.assertEqual(wrong.status_code, 403)
        self.assertNotIn('wrong-secret', wrong.text)
        self.assertIsNone(self.store.current(self.installation)['effective_revision'])
        valid = {'expected_revision':1,'current_password':'isolated-config-fixture-password'}
        result = self.client.post(url, headers=self.headers, json=valid)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['status'], 'APPLIED')
        self.assertTrue(self.client.post(url, headers=self.headers,json=valid).json()['idempotent'])
        observed = self.client.get('/api/v1/config/presentation', headers=self.headers)
        self.assertEqual(observed.json()['parameters']['display_name'], 'HTTP display')
        self.assertTrue(observed.json()['verified'])
        self.assertFalse(observed.json()['operational'])
        self.assertEqual(self.client.post(url, headers={**self.headers,'Origin':'https://denied.invalid'},json=valid).status_code,403)
