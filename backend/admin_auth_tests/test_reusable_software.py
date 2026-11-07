import json
import multiprocessing
import os
import socket
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import psycopg
import uvicorn

import test_mfa
from config_manager.assets import AssetStore, install_assets_api
from config_manager.schema import Capabilities, ConfigError
from config_manager.store import ConfigStore, Conflict, migrate
from delivery.control_store import PostgresControls
from delivery.controls import Controls, Rejected
from delivery.operational_queue import AuthorityQueue
from delivery.interface import InterfaceStore, install_interface_api
from delivery.postgres_store import PostgresStore
from delivery.projections import Record
from harpia.p11 import install_deterministic_harpia


def serve_persisted_candidate(dsn, key, port):
    from delivery.app import build_candidate_app
    os.environ['DATABASE_URL'] = dsn
    os.environ['HARPISENSE_ADMIN_USER'] = 'fixture-service'
    os.environ['HARPISENSE_ADMIN_PASSWORD'] = 'fixture-technical-only'
    app = build_candidate_app(installation_id='fixture', capabilities=Capabilities(revision='isolated-test'),
        allowed_origins=['https://dashboard.example'], protection_key=key,
        asset_catalog={('device', 'lighting'): set()})
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='critical', access_log=False)


@unittest.skipUnless(os.getenv('ADMIN_MFA_TEST_DATABASE_URL'), 'Disposable PostgreSQL required')
class ReusableTests(unittest.TestCase):
    setUpClass = classmethod(test_mfa.MFATests.setUpClass.__func__)
    sql = test_mfa.MFATests.sql
    setUp = test_mfa.MFATests.setUp
    bootstrap = test_mfa.MFATests.bootstrap
    now = test_mfa.MFATests.now
    enroll = test_mfa.MFATests.enroll

    def compose(self):
        connect = lambda: psycopg.connect(self.dsn)
        migrate(connect)
        root = Path(__file__).resolve().parents[2]
        self.sql((root/'backend/config_manager/003_assets.sql').read_text())
        self.sql((root/'backend/delivery/003_interface.sql').read_text())
        config = ConfigStore(connect, Capabilities(revision='isolated-test'))
        config.provision_registry('fixture')
        self.sql('TRUNCATE hs_config.asset,hs_config.asset_audit,hs_harpia_explanation,projections')
        assets = install_assets_api(self.app, config, 'fixture', {
            ('device', 'lighting'): {('gateway', 'gateway-1'), ('sensor', 'ldr-1')},
            ('gateway', 'capture'): set()})
        store = PostgresStore(self.dsn)
        install_deterministic_harpia(self.app, store)
        interface = install_interface_api(self.app, store)
        return assets, store, interface

    def test_assets_persistence_compatibility_concurrency_audit(self):
        assets, store, _ = self.compose()
        original = {'device_id': 'poste-1', 'topic': 'harpisense/v1/telemetry/poste-1/ldr'}
        store.insert('asset', Record(id='poste-1', source='trusted-service', data=original))
        doc = dict(display_name='Poste da entrada', asset_type='device', profile='lighting',
                   bindings={'gateway': 'gateway-1', 'sensor': 'ldr-1'}, location='Entrada', group='Iluminação')
        created = assets.save('fixture', 'poste-1', {'expected_revision': 0, 'document': doc})
        self.assertEqual(created['revision'], 1)
        self.assertEqual(created['connectivity'], 'unknown')
        self.assertEqual(created['capture'], 'unknown')
        with self.assertRaises(ConfigError):
            assets.save('fixture', 'invalid', {'expected_revision': 0, 'document': {**doc, 'bindings': {'gateway': 'unapproved'}}})
        def update(name):
            try:
                assets.save('fixture', 'poste-1', {'expected_revision': 1, 'document': {**doc, 'display_name': name}})
                return 'OK'
            except Conflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(update, ['Entrada A', 'Entrada B'])), ['OK', 'CONFLICT'])
        restored = AssetStore(assets.config, assets.catalog)
        self.assertEqual(restored.list('fixture')[0]['revision'], 2)
        self.assertEqual(len(restored.audit('fixture')), 2)
        self.assertEqual(store.history('asset', 'poste-1')[0]['data'], original)

    def test_incident_exact_links_and_durable_latest_three_explanations(self):
        _, store, interface = self.compose()
        for kind, id, data in [
            ('incident', 'incident-1', {'status': 'CLOSED', 'revision': 1, 'detection_refs': ['rf-1', 'if-1'],
                                      'evidence_refs': ['ev-1'], 'network_event_refs': ['log-1']}),
            ('detection', 'rf-1', {'model': {'detector': 'random_forest'}, 'classification': {'attack_probability': .8}}),
            ('detection', 'if-1', {'model': {'detector': 'isolation_forest'}, 'anomaly': {'anomaly_score': -.3}}),
            ('evidence', 'ev-1', {'source_ref': {'source_file': 'fixture.jsonl', 'line': 1}}),
            ('network_event', 'log-1', {'status': 'OBSERVED'}),
            ('decision', 'decision-1', {'incident_id': 'incident-1', 'incident_revision': 1, 'status': 'REQUEST_APPROVAL'}),
            ('approval', 'approval-1', {'decision_id': 'decision-1', 'status': 'PENDING'}),
            ('execution', 'execution-1', {'decision_id': 'decision-1', 'status': 'QUEUED'}),
            ('verification', 'verification-1', {'execution_id': 'execution-1', 'status': 'INCONCLUSIVE'})]:
            store.insert(kind, Record(id=id, source='trusted-service', data=data))
        bundle = interface.incident('incident-1')
        self.assertEqual(len(bundle['related']['detection']), 2)
        self.assertEqual(bundle['related']['approval'][0]['data']['status'], 'PENDING')
        self.assertEqual(bundle['related']['verification'][0]['data']['status'], 'INCONCLUSIVE')
        self.assertFalse(bundle['commands']['approval_available'])
        self.assertEqual(bundle['log_references'][0]['line'], 1)
        for revision in range(1, 5):
            interface.remember('incident-1', revision, {'revision': revision, 'text': 'fixture'})
        restored = InterfaceStore(PostgresStore(self.dsn))
        self.assertEqual([r['incident_revision'] for r in restored.history('incident-1', 3)], [4, 3, 2])
        restored.remember('incident-1', 4, {'revision': 4, 'text': 'fixture'})
        self.assertEqual(len(restored.history('incident-1')), 4)
        # Multiple unpinned revisions cannot silently become a different RF result.
        store.insert('detection', Record(id='rf-1', revision=2, source='trusted-service', data={'status': 'changed'}))
        self.assertIn({'kind': 'detection', 'id': 'rf-1', 'reason': 'MISSING_OR_UNPINNED'}, interface.incident('incident-1')['unresolved'])

    def test_authoritative_operational_checks_real_pg_lock_and_closed_history(self):
        self.sql('CREATE TABLE IF NOT EXISTS hs_fixture_lifecycle(domain text,id text,state text)')
        self.sql('TRUNCATE hs_fixture_lifecycle,hs_control_audit')
        self.sql("UPDATE hs_control SET value='{}', revision=1,emergency_stopped=false".format(
            json.dumps(dict(operation='IDS', execution_enabled=False, autonomy_mode=1))))
        def source(domain):
            def read(conn):
                rows = conn.execute('SELECT id,state FROM hs_fixture_lifecycle WHERE domain=%s', (domain,)).fetchall()
                return {'reliable': True, 'items': [dict(id=r[0], state=r[1]) for r in rows]}
            return read
        controls = Controls(PostgresControls(self.dsn), AuthorityQueue({d: source(d) for d in ('anomaly','incident','approval','execution')}))
        def change(revision=1, mode=2):
            return controls.change(value=dict(operation='IDS', execution_enabled=False, autonomy_mode=mode),
                                   expected_revision=revision, reason='fixture', actor='fixture')
        self.sql("INSERT INTO hs_fixture_lifecycle VALUES('incident','old','CLOSED')")
        self.assertTrue(controls.get()['change_allowed'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            def attempt(mode):
                try:
                    change(mode=mode)
                    return 'OK'
                except Rejected:
                    return 'CONFLICT'
            self.assertCountEqual(list(pool.map(attempt, [2,3])), ['OK','CONFLICT'])
        for domain, state in [('anomaly','ACTIVE'),('incident','SUSPECTED'),('approval','PENDING'),('execution','VERIFYING'),('execution','UNKNOWN_OUTCOME')]:
            self.sql('TRUNCATE hs_fixture_lifecycle')
            with controls.decision_transaction(2) as (tx, _):
                tx.conn.execute('INSERT INTO hs_fixture_lifecycle VALUES(%s,%s,%s)', (domain,'active',state))
            with self.assertRaises(Rejected) as exc:
                change(2)
            self.assertEqual(exc.exception.detail['code'], 'OPERATIONAL_PENDING')
        self.sql("UPDATE hs_fixture_lifecycle SET state='UNRECOGNIZED'")
        with self.assertRaises(Rejected) as exc:
            change(2)
        self.assertEqual(exc.exception.detail['code'], 'QUEUE_UNVERIFIED')
        stopped = controls.stop(actor='fixture', reason='fixture')
        self.assertTrue(stopped['emergency_stopped'])
        self.assertFalse(stopped['value']['execution_enabled'])

    def test_real_http_assets_harpia_history_and_permissions(self):
        assets, store, _ = self.compose()
        _, _, _, session = self.enroll()
        store.insert('incident', Record(id='incident-http', source='trusted-service', data={'status':'CLOSED','revision':1}))
        sock = socket.socket(); sock.bind(('127.0.0.1', 0))
        server = uvicorn.Server(uvicorn.Config(self.app, log_level='critical', access_log=False))
        thread = threading.Thread(target=server.run, kwargs={'sockets':[sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic()+10
            while not server.started and time.monotonic()<deadline:
                time.sleep(.01)
            self.assertTrue(server.started)
            with httpx.Client(base_url=f'http://127.0.0.1:{sock.getsockname()[1]}') as client:
                path = '/api/v1/config/assets'
                self.assertEqual(client.get(path).status_code, 401)
                client.headers['Authorization'] = 'Bearer '+session['access_token']
                payload = {'expected_revision':0, 'document':dict(display_name='Entrada', asset_type='device', profile='lighting', bindings={})}
                response = client.put(path+'/poste-1', json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(client.put(path+'/poste-1', json=payload).status_code, 409)
                self.assertEqual(client.get(path).json()[0]['document']['display_name'], 'Entrada')
                self.assertEqual(client.get(path+'/audit').json()[0]['actor'], 'admin-account-1')
                response = client.get('/api/v1/p11/explain/incident-http')
                self.assertEqual(response.status_code, 200, response.text)
                result = client.get('/api/v1/interface/incidents/incident-http/harpia')
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(len(result.json()['latest_three']), 1)
                self.assertEqual(result.headers['cache-control'], 'no-store')
                self.assertEqual(client.get('/api/v1/interface/incidents/incident-http').status_code, 200)
                self.assertEqual(client.get('/api/v1/admin-auth/session').json()['username'], 'owner')
        finally:
            server.should_exit = True
            thread.join(10)
            sock.close()

    def test_process_restart_preserves_session_assets_and_explanation_history(self):
        _, store, _ = self.compose()
        _, _, _, session = self.enroll()
        store.insert('incident', Record(id='restart-incident', source='trusted-service', data={'status':'CLOSED','revision':1}))
        context = multiprocessing.get_context('spawn')
        for iteration in range(2):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            process = context.Process(target=serve_persisted_candidate, args=(self.dsn, self.key, port))
            process.start()
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}',
                                  headers={'Authorization':'Bearer '+session['access_token']}) as client:
                    deadline = time.monotonic()+20
                    while True:
                        try:
                            response = client.get('/api/v1/admin-auth/session')
                            break
                        except httpx.ConnectError:
                            if time.monotonic()>=deadline or not process.is_alive():
                                raise
                            time.sleep(.05)
                    self.assertEqual(response.status_code, 200)
                    if iteration == 0:
                        response = client.put('/api/v1/config/assets/poste-1', json={'expected_revision':0,
                            'document':dict(display_name='Persistente', asset_type='device',profile='lighting',bindings={})})
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(client.get('/api/v1/p11/explain/restart-incident').status_code, 200)
                    else:
                        self.assertEqual(client.get('/api/v1/config/assets').json()[0]['document']['display_name'], 'Persistente')
                        self.assertEqual(len(client.get('/api/v1/interface/incidents/restart-incident/harpia').json()['latest_three']), 1)
            finally:
                process.terminate()
                process.join(10)
