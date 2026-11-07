import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/domain')]
from delivery.operational_queue import SOURCES, summarize, OperationalQueue
from delivery.controls import Controls, Rejected


def rows(items=None, stale=(), absent=()):
    items = items or {}
    return [(s, items.get(s, []), s not in stale, 7, datetime.now(timezone.utc))
            for s in sorted(SOURCES) if s not in absent]


class SnapshotTests(unittest.TestCase):
    def test_complete_empty_is_only_proof_of_no_active_cases(self):
        state = summarize(rows())
        self.assertTrue(state['reliable'])
        self.assertEqual(state['cases']['status'], 'none_active')
        self.assertEqual(state['cases']['known_active_count'], 0)

    def test_lost_communication_retains_known_attack_and_identifiers(self):
        state = summarize(rows({'incident': [dict(id='attack-1', state='ACTIVE', revision=4)]},
                               stale=SOURCES))
        self.assertFalse(state['reliable'])
        self.assertEqual(state['cases']['status'], 'active')
        self.assertEqual(state['cases']['coverage'], 'unknown')
        item = state['cases']['items'][0]
        self.assertEqual((item['record_id'], item['record_revision'], item['source_revision']), ('attack-1', 4, 7))
        self.assertFalse(item['fresh'])

    def test_no_visibility_does_not_attest_no_cases(self):
        for state in (summarize(rows(stale=SOURCES)), summarize([])):
            self.assertEqual(state['cases']['status'], 'unknown')
            self.assertFalse(state['reliable'])

    def test_partial_missing_source_is_explicit(self):
        state = summarize(rows(absent=['anomaly']))
        self.assertEqual(state['cases']['status'], 'partial')
        source = next(s for s in state['cases']['sources'] if s['source'] == 'anomaly')
        self.assertIsNone(source['source_revision'])
        self.assertFalse(source['fresh'])

    def test_closed_history_does_not_block(self):
        state = summarize(rows({'incident': [dict(id='closed-1', state='CLOSED')],
                                'execution': [dict(id='done-1', state='COMPLETED')]}))
        self.assertTrue(state['reliable'])
        self.assertEqual(state['blockers'], [])
        self.assertEqual(state['cases']['status'], 'none_active')

    def test_unknown_item_prevents_complete_empty_claim(self):
        state = summarize(rows({'incident': [dict(id='unknown-1', state='UNKNOWN')]}))
        self.assertFalse(state['reliable'])
        self.assertEqual(state['cases']['status'], 'partial')
        self.assertEqual(len(state['blockers']), 1)

    def test_duplicate_ids_do_not_attest_complete_coverage(self):
        state = summarize(rows({'incident': [dict(id='same', state='CLOSED'), dict(id='same', state='CLOSED')]}))
        self.assertFalse(state['reliable'])
        self.assertNotEqual(state['cases']['status'], 'none_active')
        active = summarize(rows({'incident': [dict(id='same', state='ACTIVE'), dict(id='same', state='ACTIVE')]}))
        self.assertEqual(active['cases']['known_active_count'], 1)

    def test_malformed_report_keeps_valid_known_active(self):
        state = summarize(rows({'incident': [dict(id='attack-1', state='ACTIVE'), {}]}))
        self.assertFalse(state['reliable'])
        self.assertEqual(state['cases']['status'], 'active')

    def test_pending_approval_and_execution_are_not_case_counts(self):
        state = summarize(rows({'approval': [dict(id='approval-1', state='REQUEST_APPROVAL')],
                                'execution': [dict(id='execution-1', state='RUNNING')]}))
        self.assertEqual(len(state['blockers']), 2)
        self.assertEqual(state['cases']['known_active_count'], 0)
        self.assertEqual(state['cases']['status'], 'none_active')

    def test_existing_pending_execution_states_are_blockers(self):
        for status in ('AUTHORIZED', 'QUEUED', 'APPLYING', 'COMMAND_ACCEPTED', 'UNKNOWN_OUTCOME',
                       'EXPIRING', 'REVERSING', 'REVERSAL_FAILED'):
            with self.subTest(status=status):
                state = summarize(rows({'execution': [dict(id='execution-1', state=status)]}))
                self.assertEqual(len(state['blockers']), 1)
                if status == 'UNKNOWN_OUTCOME': self.assertFalse(state['reliable'])


@unittest.skipUnless(os.getenv('TEST_DATABASE_URL'), 'Isolated native PostgreSQL not configured')
class NativeAuthorityTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        from delivery.control_store import PostgresControls
        self.dsn = os.environ['TEST_DATABASE_URL']
        with psycopg.connect(self.dsn) as conn:
            conn.execute((ROOT/'backend/delivery/001_local.sql').read_text(encoding='utf-8'))
            conn.execute((ROOT/'backend/delivery/002_operational_authority.sql').read_text(encoding='utf-8'))
            conn.execute('TRUNCATE hs_operational_authority,hs_control_audit,hs_simulation')
            from psycopg.types.json import Jsonb
            conn.execute('UPDATE hs_control SET value=%s,revision=1,emergency_stopped=false',
                         (Jsonb(dict(operation='IDS', execution_enabled=False, autonomy_mode=1)),))
        self.queue = OperationalQueue()
        self.controls = Controls(PostgresControls(self.dsn), self.queue)
        with self.controls.decision_transaction(1) as (tx, _):
            for source in SOURCES: self.queue.report(tx, source, 1, [])

    def apply(self):
        return self.controls.change(value=dict(operation='IDS', execution_enabled=False, autonomy_mode=3),
                                    expected_revision=1, actor='native-test', reason='native test Apply')

    def test_active_survives_stale_connection_and_requires_explicit_closure(self):
        with self.controls.decision_transaction(1) as (tx, _):
            self.queue.report(tx, 'incident', 2, [dict(id='native-case', state='ACTIVE', revision=1)])
            tx.conn.execute("UPDATE hs_operational_authority SET observed_at=clock_timestamp()-interval '1 minute'")
        self.assertEqual(self.controls.get()['cases']['status'], 'active')
        with self.assertRaises(Rejected): self.apply()
        with self.assertRaisesRegex(ValueError, 'ACTIVE_ITEM_REQUIRES_CLOSURE'):
            with self.controls.decision_transaction(1) as (tx, _): self.queue.report(tx, 'incident', 3, [])
        with self.controls.decision_transaction(1) as (tx, _):
            for source in SOURCES:
                self.queue.report(tx, source, 3, [dict(id='native-case', state='CLOSED', revision=2)] if source == 'incident' else [])
        self.assertEqual(self.apply()['effective_state']['applied_profile'], 'M3')

    def test_concurrent_activity_admission_blocks_apply(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        admitted, release = threading.Event(), threading.Event()
        def admit():
            with self.controls.decision_transaction(1) as (tx, _):
                self.queue.report(tx, 'approval', 2, [dict(id='native-approval', state='REQUEST_APPROVAL')])
                admitted.set()
                if not release.wait(5): raise RuntimeError('test timeout')
        with ThreadPoolExecutor(2) as pool:
            writer = pool.submit(admit)
            self.assertTrue(admitted.wait(5))
            applying = pool.submit(self.apply)
            release.set(); writer.result()
            with self.assertRaises(Rejected): applying.result()
        self.assertEqual(self.controls.get()['revision'], 1)

    def test_unknown_refusal_does_not_prevent_emergency(self):
        with self.controls.decision_transaction(1) as (tx, _):
            tx.conn.execute("DELETE FROM hs_operational_authority WHERE source='execution'")
        with self.assertRaises(Rejected): self.apply()
        state = self.controls.stop(actor='native-test', reason='native emergency')
        self.assertTrue(state['emergency_stopped'])
        self.assertFalse(state['value']['execution_enabled'])

    def test_authenticated_api_exposes_cases_and_keeps_current_on_refusal(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from delivery.app import build_app
        with patch.dict(os.environ, DATABASE_URL=self.dsn, HARPISENSE_ADMIN_USER='controls-test',
                        HARPISENSE_ADMIN_PASSWORD='isolated-controls-test'):
            client = TestClient(build_app())
        root = '/api/v1/security'
        auth = ('controls-test', 'isolated-controls-test')
        self.assertEqual(client.get(root+'/settings/mode/default').status_code, 401)
        initial = client.get(root+'/settings/mode/default', auth=auth).json()
        self.assertEqual(initial['cases']['status'], 'none_active')
        with self.controls.decision_transaction(1) as (tx, _):
            self.queue.report(tx, 'incident', 2, [dict(id='native-active', state='ACTIVE')])
        response = client.put(root+'/settings/mode/default', auth=auth,
                              json=dict(value=initial['value'] | {'autonomy_mode': 3},
                                        expected_revision=1, reason='native concurrent Apply'))
        self.assertEqual(response.status_code, 409)
        current = response.json()['detail']['current']
        self.assertEqual(current['revision'], 1)
        self.assertEqual(current['effective_state']['applied_profile'], 'M1')
        self.assertEqual(current['cases']['status'], 'active')
        stopped = client.post(root+'/emergency-stop', auth=auth, json={'reason': 'native emergency'})
        self.assertEqual(stopped.status_code, 200)
        self.assertTrue(stopped.json()['emergency_stopped'])
        self.assertEqual(stopped.json()['cases']['status'], 'unknown')
        self.assertEqual(client.get(root+'/settings/mode/default', auth=auth).json()['cases']['status'], 'active')


if __name__ == '__main__': unittest.main()
