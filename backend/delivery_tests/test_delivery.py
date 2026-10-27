"""Isolated fixtures, never VM evidence or production queue authority."""
import copy
import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/domain'), str(ROOT/'genai')]
from fastapi.testclient import TestClient
from harpisense_catalog import CATALOG, AUTONOMY
from harpisense_engines import decide
from harpisense_contracts import validate
from delivery.controls import Controls, Rejected, stamp
from delivery.control_store import PostgresControls
from delivery.routes import install_controls
from delivery.projections import create_app
from delivery.simulation import simulate
from harpia.p11 import install_deterministic_harpia
from policy_fixtures import context, NOW


class MemoryRepository:
    """Transactional protocol fake. Production has no memory/SQLite fallback."""
    def __init__(self):
        self.lock = threading.RLock()
        self.state = dict(value=dict(operation='IDS', execution_enabled=False, autonomy_mode=1),
                          revision=1, emergency_stopped=False, updated_at=stamp())
        self.events, self.results = [], {}

    @contextmanager
    def transaction(self):
        with self.lock:
            before = copy.deepcopy((self.state, self.events, self.results))
            try:
                yield self
            except Exception:
                self.state, self.events, self.results = before
                raise

    def read(self): return copy.deepcopy(self.state)
    def save(self, value, revision, stopped):
        self.state = dict(value=value, revision=revision, emergency_stopped=stopped, updated_at=stamp())
    def log(self, actor, operation, details):
        self.events.append(dict(actor=actor, operation=operation, details=details))
    def audit(self, limit=50, offset=0): return self.events[::-1][offset:offset+limit]
    def simulation_once(self, decision_id, result):
        return self.results.setdefault(decision_id, result)


class IsolatedQueue:
    def __init__(self): self.blockers = []
    def snapshot(self, tx): return dict(reliable=True, blockers=copy.deepcopy(self.blockers))


class Projections:
    def list(self, kind, limit=50, offset=0): return []
    def history(self, kind, id): return []


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.queue = MemoryRepository(), IsolatedQueue()
        self.controls = Controls(self.repo, self.queue)

    def change(self, mode=3, revision=1, **patch):
        value = {**self.repo.read()['value'], 'autonomy_mode': mode, **patch}
        return self.controls.change(value=value, expected_revision=revision, reason='isolated test', actor='fixture-admin')

    def test_policy_all_27_cases(self):
        for case in CATALOG:
            for mode in (1, 2, 3):
                with self.subTest(case=case, mode=mode):
                    d = decide(context(case), mode=mode, now=NOW)['decision']
                    manual = mode == 1 or mode == 2 and CATALOG[case]['group'] != 'Low'
                    self.assertEqual(d['status'], 'REQUEST_APPROVAL' if manual else 'AUTHORIZED')
                    validate(d)
        self.assertEqual(AUTONOMY[2]['Medium'], 'MANUAL')

    def test_policy_m3_ineligible_refused_automatically(self):
        for key, value in [('verified', False), ('scope_allowed', False), ('protected', True), ('executor_ready', False)]:
            c = context('C07'); c['target'][key] = value
            self.assertEqual(decide(c, mode=3, now=NOW)['decision']['status'], 'OBSERVE_ONLY')
        c = context(); c['trusted_sources'] = {}
        self.assertEqual(decide(c, mode=3, now=NOW)['decision']['status'], 'OBSERVE_ONLY')

    def test_allowed_transition_does_not_enable_execution_or_dispatch(self):
        result = self.change()
        self.assertEqual(result['value'], dict(operation='IDS', execution_enabled=False, autonomy_mode=3))
        self.assertEqual(result['revision'], 2)
        self.assertEqual(self.repo.results, {})

    def test_unknown_queue_refuses_and_commits_audit(self):
        controls = Controls(self.repo)
        with self.assertRaises(Rejected) as error:
            controls.change(value=dict(operation='IDS', execution_enabled=False, autonomy_mode=2),
                            expected_revision=1, reason='isolated', actor='fixture')
        self.assertEqual(error.exception.detail['code'], 'QUEUE_UNVERIFIED')
        self.assertEqual(self.repo.read()['revision'], 1)
        self.assertEqual(self.repo.events[-1]['operation'], 'CONTROL_CHANGE_REJECTED')

    def test_pending_categories_and_emergency(self):
        for status in ['REQUEST_APPROVAL','AUTHORIZED','QUEUED','APPLYING','COMMAND_ACCEPTED','VERIFYING',
                       'UNKNOWN_OUTCOME','EXPIRING','REVERSING','REVERSAL_FAILED']:
            self.queue.blockers = [dict(id='fixture-pending', state=status)]
            with self.assertRaises(Rejected) as error: self.change()
            self.assertEqual(error.exception.detail['code'], 'OPERATIONAL_PENDING')
        state = self.controls.stop(actor='fixture', reason='isolated emergency')
        self.assertTrue(state['emergency_stopped'])
        self.assertFalse(state['value']['execution_enabled'])

    def test_real_and_emergency_resume_blocked(self):
        with self.assertRaises(Rejected): self.change(operation='REAL', execution_enabled=True)
        self.controls.stop(actor='fixture', reason='isolated emergency')
        with self.assertRaises(Rejected): self.change(revision=2, operation='SIMULATION', execution_enabled=True)

    def test_history_logs_and_explanations_do_not_block_and_stop_never_reads_queue(self):
        self.repo.events.append(dict(operation='HISTORICAL_UNREAD_LOG'))
        self.queue.historical_incidents = ['already-treated']
        self.queue.explanations_pending = ['not-an-execution-pending']
        self.assertEqual(self.change()['revision'], 2)
        class BrokenQueue:
            def snapshot(self, tx): raise AssertionError('Emergency must not read queue')
        stopped = Controls(self.repo, BrokenQueue()).stop(actor='fixture', reason='isolated stop')
        self.assertTrue(stopped['emergency_stopped'])

    def test_stale_revision_and_transaction_failure(self):
        self.change()
        with self.assertRaises(Rejected): self.change(mode=2)
        before = self.repo.read()
        with self.assertRaises(RuntimeError):
            with self.controls.decision_transaction(2) as (tx, state):
                tx.save(dict(operation='IDS', execution_enabled=False, autonomy_mode=1), 3, False)
                raise RuntimeError('interrupted before commit')
        self.assertEqual(self.repo.read(), before)

    def test_concurrent_transitions_have_one_winner(self):
        barrier = threading.Barrier(2)
        def run(mode):
            barrier.wait()
            try: self.change(mode); return 'changed'
            except Rejected: return 'conflict'
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(run, [2, 3]))
        self.assertCountEqual(results, ['changed', 'conflict'])

    def test_concurrent_decision_prevents_transition(self):
        admitted, release = threading.Event(), threading.Event()
        def producer():
            with self.controls.decision_transaction(1):
                self.queue.blockers.append(dict(id='fixture-new-decision', state='AUTHORIZED'))
                admitted.set(); release.wait(3)
        with ThreadPoolExecutor(2) as pool:
            future = pool.submit(producer)
            self.assertTrue(admitted.wait(3))
            change = pool.submit(self.change)
            release.set(); future.result()
            with self.assertRaises(Rejected): change.result()

    def test_transition_invalidates_old_producer_revision(self):
        self.change()
        with self.assertRaises(Rejected):
            with self.controls.decision_transaction(1): self.fail('Old producer must not run')

    def test_simulated_executor_m3_eligible_without_approval_and_no_replay(self):
        self.change(operation='SIMULATION', execution_enabled=True)
        bundle = decide(context('C07'), mode=3, now=NOW)
        result = simulate(self.controls, bundle, context('C07'), expected_revision=2, now=NOW)
        self.assertEqual(result['status'], 'SIMULATED')
        self.assertFalse(result['mitigation_confirmed'])
        self.assertEqual(simulate(self.controls, bundle, context('C07'), expected_revision=2, now=NOW), result)
        self.assertEqual(len(self.repo.results), 1)
        self.change(mode=2, revision=2)
        with self.assertRaises(Rejected): simulate(self.controls, bundle, context('C07'), expected_revision=2, now=NOW)

    def test_simulated_executor_requires_manual_approval_and_fresh_evidence(self):
        self.change(mode=2, operation='SIMULATION', execution_enabled=True)
        for case in ('C04', 'C07'):
            bundle = decide(context(case), mode=2, now=NOW)
            with self.assertRaises(ValueError): simulate(self.controls, bundle, context(case), expected_revision=2, now=NOW)
        bundle = decide(context(), mode=2, now=NOW)
        with self.assertRaises(ValueError): simulate(self.controls, bundle, context(), expected_revision=2, now='2026-10-15T15:05:00Z')

    def test_authenticated_api_empty_states_and_no_generation(self):
        app = create_app(Projections(), username='fixture', password='fixture')
        install_deterministic_harpia(app, Projections()); install_controls(app, self.controls)
        client = TestClient(app); auth = ('fixture','fixture')
        root = '/api/v1/security'
        for path in ['/settings/mode/default', '/audit']:
            self.assertEqual(client.get(root+path).status_code, 401)
        self.assertEqual(client.put(root+'/settings/mode/default', json={}).status_code, 401)
        self.assertEqual(client.post(root+'/emergency-stop', json={'reason':'fixture'}).status_code, 401)
        health = client.get('/api/v1/p11/health', auth=auth).json()
        self.assertFalse(health['harpia']['generation_enabled'])
        for kind in ('telemetry','detection','incident','approval','execution'):
            self.assertEqual(client.get('/api/v1/p11/'+kind, auth=auth).json(), [])
        self.assertEqual(client.get('/api/v1/p11/explain/absent', auth=auth).status_code, 404)
        payload = dict(value=dict(operation='IDS', execution_enabled=False, autonomy_mode=3), expected_revision=1, reason='fixture')
        self.assertEqual(client.put(root+'/settings/mode/default', json=payload, auth=auth).status_code, 200)
        self.assertEqual(client.put(root+'/settings/mode/default', json=payload, auth=auth).status_code, 409)
        payload['expected_revision'] = True
        self.assertEqual(client.put(root+'/settings/mode/default', json=payload, auth=auth).status_code, 422)


@unittest.skipUnless(os.getenv('TEST_DATABASE_URL'), 'Isolated PostgreSQL not configured')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.dsn = os.environ['TEST_DATABASE_URL']
        # Dedicated disposable database ONLY. Never point this test at deployed data.
        with psycopg.connect(self.dsn) as conn:
            conn.execute((ROOT/'backend/delivery/001_local.sql').read_text(encoding='utf-8'))
            conn.execute('TRUNCATE hs_control_audit,hs_simulation')
            conn.execute("UPDATE hs_control SET value='{"+'"operation":"IDS","execution_enabled":false,"autonomy_mode":1'+"}', revision=1,emergency_stopped=false")
        self.repo = PostgresControls(self.dsn)

    def test_restart_audit_and_cross_connection_concurrency(self):
        queue = IsolatedQueue()
        def change(mode):
            controls = Controls(PostgresControls(self.dsn), queue)
            try:
                return controls.change(value=dict(operation='IDS',execution_enabled=False,autonomy_mode=mode),
                                       expected_revision=1,reason='isolated PG concurrency',actor='fixture')['revision']
            except Rejected: return 'conflict'
        with ThreadPoolExecutor(2) as pool: results = list(pool.map(change,[2,3]))
        self.assertCountEqual(results, [2,'conflict'])
        restarted = Controls(PostgresControls(self.dsn), queue).get()
        self.assertEqual(restarted['revision'], 2)
        self.assertEqual(len(self.repo.audit()), 2)

    def test_unknown_refusal_persists_and_stop_bypasses_queue(self):
        controls = Controls(self.repo)
        with self.assertRaises(Rejected):
            controls.change(value=dict(operation='IDS',execution_enabled=False,autonomy_mode=3),expected_revision=1,reason='isolated PG',actor='fixture')
        self.assertEqual(self.repo.audit()[0]['data']['details']['code'], 'QUEUE_UNVERIFIED')
        self.assertTrue(controls.stop(actor='fixture',reason='isolated')['emergency_stopped'])

    def test_composed_p11_postgresql_telemetry_and_authenticated_controls(self):
        from unittest.mock import patch
        from delivery.app import build_app
        from delivery.postgres_store import PostgresStore
        from delivery.projections import Record
        import uuid
        key = 'synthetic-test-'+uuid.uuid4().hex
        store = PostgresStore(self.dsn)
        store.insert('telemetry', Record(id=key, revision=1, source='synthetic',
                     data={'device_id':'fixture-poste','temperatura':28.4,'observed_at':NOW}))
        with patch.dict(os.environ, DATABASE_URL=self.dsn, HARPISENSE_ADMIN_USER='fixture', HARPISENSE_ADMIN_PASSWORD='fixture'):
            api = TestClient(build_app())
        auth = ('fixture','fixture')
        self.assertEqual(api.get('/api/v1/p11/health').status_code, 401)
        health = api.get('/api/v1/p11/health', auth=auth).json()
        self.assertEqual(health['database'], 'available')
        self.assertFalse(health['harpia']['generation_enabled'])
        rows = api.get('/api/v1/p11/telemetry', auth=auth).json()
        record = next(r for r in rows if r['id'] == key)
        self.assertEqual(record['data']['temperatura'], 28.4)
        self.assertEqual(record['source'], 'synthetic')
        request = dict(value=dict(operation='IDS',execution_enabled=False,autonomy_mode=3), expected_revision=1, reason='isolated API test')
        response = api.put('/api/v1/security/settings/mode/default', auth=auth, json=request)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail']['code'], 'QUEUE_UNVERIFIED')
        self.assertEqual(api.get('/api/v1/security/audit', auth=auth).json()[0]['data']['operation'], 'CONTROL_CHANGE_REJECTED')
        # P11 service-token protection on ingest is retained.
        self.assertEqual(api.post('/api/v1/p11/ingest/telemetry', auth=auth, json=dict(id='fixture',source='trusted-service',data={})).status_code, 403)

    def test_pg_decision_lock_rollback_and_simulation_survive_new_repository(self):
        queue = IsolatedQueue(); controls = Controls(self.repo, queue)
        with self.assertRaises(RuntimeError):
            with controls.decision_transaction(1) as (tx, state):
                tx.save(dict(operation='SIMULATION',execution_enabled=True,autonomy_mode=3),2,False)
                raise RuntimeError('interrupted')
        self.assertEqual(controls.get()['revision'], 1)
        controls.change(value=dict(operation='SIMULATION',execution_enabled=True,autonomy_mode=3),expected_revision=1,reason='isolated PG simulator',actor='fixture')
        bundle = decide(context('C07'),mode=3,now=NOW)
        first = simulate(controls,bundle,context('C07'),expected_revision=2,now=NOW)
        restarted = Controls(PostgresControls(self.dsn), queue)
        self.assertEqual(simulate(restarted,bundle,context('C07'),expected_revision=2,now=NOW), first)
        self.assertEqual(first['status'], 'SIMULATED')
        admitted, release = threading.Event(), threading.Event()
        def producer():
            with controls.decision_transaction(2):
                queue.blockers.append(dict(id='fixture-pending',state='REQUEST_APPROVAL'))
                admitted.set(); release.wait(3)
        def change():
            return restarted.change(value=dict(operation='SIMULATION',execution_enabled=True,autonomy_mode=2),expected_revision=2,reason='isolated PG race',actor='fixture')
        with ThreadPoolExecutor(2) as pool:
            future = pool.submit(producer); self.assertTrue(admitted.wait(3))
            transition = pool.submit(change); release.set(); future.result()
            with self.assertRaises(Rejected): transition.result()


if __name__ == '__main__': unittest.main()
