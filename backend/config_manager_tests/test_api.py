"""HTTP acceptance with real shared PostgreSQL; existing AuthService sessions."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from admin_auth.api import install_admin_auth
from admin_auth.service import AdminAuth
from config_manager.api import install_config_api
from config_manager.schema import Capabilities
from config_manager.store import ConfigStore, migrate
from config_manager.store import Conflict
from config_manager.setup import SetupStore, migrate_setup
from test_config_manager import request


@unittest.skipUnless(os.getenv('HARPISENSE_CONFIG_TEST_DSN'), 'Isolated PostgreSQL required')
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['HARPISENSE_CONFIG_TEST_DSN']
        with psycopg.connect(cls.dsn) as conn:
            if conn.info.dbname != 'config_fixture':
                raise RuntimeError('Isolated fixture only')
            # Dedicated fixture container, never an operational account/database.
            from pathlib import Path
            if not conn.execute("SELECT to_regclass('hs_admin_account')").fetchone()[0]:
                conn.execute((Path(__file__).parents[1] / 'admin_auth/001_admin_auth.sql').read_text())
        cls.connect = staticmethod(lambda: psycopg.connect(cls.dsn))
        migrate(cls.connect)
        migrate_setup(cls.connect)
        migrate_setup(cls.connect)
        cls.auth = AdminAuth(cls.dsn)
        with cls.connect() as conn:
            present = conn.execute('SELECT 1 FROM hs_admin_account').fetchone()
        if not present:
            cls.auth.provision('fixture-admin', 'isolated-config-fixture-password')

    def setUp(self):
        self.store = ConfigStore(self.connect, Capabilities(revision='fixture'))
        self.installation = 'test-' + uuid4().hex
        self.store.provision_registry(self.installation)
        app = FastAPI()
        def old_admin(): return 'technical'
        @app.get('/api/v1/p11/health', dependencies=[Depends(old_admin)])
        def health(): return {}
        install_admin_auth(app, self.auth, allowed_origins=['http://localhost'])
        install_config_api(app, self.store, installation_id=self.installation)
        self.client = TestClient(app)
        token = self.auth.login('fixture-admin', 'isolated-config-fixture-password')['access_token']
        self.headers = {'Authorization': 'Bearer ' + token}

    def test_auth_all_routes(self):
        routes = [('GET', '/current'), ('GET', '/history'), ('GET', '/catalog'),
                  ('GET', '/setup'), ('PUT', '/setup'), ('POST', '/proposals'),
                  ('GET', '/proposals/' + str(uuid4())), ('POST', '/proposals/' + str(uuid4()) + '/validate')]
        for method, path in routes:
            for headers in ({}, {'Authorization': 'Bearer invalid'}):
                r = self.client.request(method, '/api/v1/config' + path, headers=headers, json={})
                self.assertEqual(r.status_code, 401, r.text)
        r = self.client.get('/api/v1/config/current', headers={**self.headers, 'Origin': 'https://denied.invalid'})
        self.assertEqual(r.status_code, 403)

    def test_proposal_validation_conflict_history(self):
        req = request()
        r = self.client.post('/api/v1/config/proposals', headers=self.headers, json=req)
        self.assertEqual(r.status_code, 200, r.text)
        op = r.json()['operation_id']
        self.assertEqual(self.client.post('/api/v1/config/proposals', headers=self.headers, json=req).json()['operation_id'], op)
        conflict = self.client.post('/api/v1/config/proposals', headers=self.headers, json=request())
        self.assertEqual(conflict.status_code, 409)
        r = self.client.post(f'/api/v1/config/proposals/{op}/validate', headers=self.headers, json={'expected_revision': 1})
        self.assertEqual(r.json()['status'], 'VALIDATED', r.text)
        result = self.client.get('/api/v1/config/current', headers=self.headers).json()
        self.assertEqual(result['state'], 'validated')
        self.assertFalse(result['operational'])
        self.assertIsNone(result['effective_revision'])
        self.assertEqual(len(self.client.get('/api/v1/config/history', headers=self.headers).json()), 2)
        self.assertEqual(self.client.get(f'/api/v1/config/proposals/{op}', headers=self.headers).status_code, 200)

    def test_sanitized_errors(self):
        req = request()
        req['document']['parameters'] = {'mqtt_broker_port': 99999, 'secret-password': 'do-not-echo'}
        r = self.client.post('/api/v1/config/proposals', headers=self.headers, json=req)
        self.assertEqual(r.status_code, 422)
        self.assertNotIn('do-not-echo', r.text)
        self.assertNotIn('secret-password', r.text)
        self.assertIn('document.parameters.mqtt_broker_port', r.text)

    def test_resume_persistence_and_idempotency(self):
        req = {'expected_version': 0, 'idempotency_key': 'setup-key-1',
               'document': {'step': 'mqtt', 'parameters': {'mqtt_broker_host': 'broker.invalid'}}}
        r = self.client.put('/api/v1/config/setup', headers=self.headers, json=req)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.client.put('/api/v1/config/setup', headers=self.headers, json=req).json(), r.json())
        self.assertEqual(SetupStore(ConfigStore(self.connect, self.store.capabilities)).get(self.installation)['document'], req['document'])
        req['idempotency_key'] = 'setup-key-2'
        self.assertEqual(self.client.put('/api/v1/config/setup', headers=self.headers, json=req).status_code, 409)
        current = self.store.current(self.installation)
        self.assertEqual(current['desired_revision'], 0)
        self.assertIsNone(current['effective_revision'])

    def test_setup_concurrent_writers(self):
        setup = SetupStore(self.store)
        def save(key):
            try:
                setup.save(self.installation, 'admin-account-1', {
                    'expected_version': 0, 'idempotency_key': key,
                    'document': {'step': 'installation', 'parameters': {}}})
                return 'saved'
            except Conflict:
                return 'conflict'
        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(save, ['concurrent-1', 'concurrent-2'])), ['saved', 'conflict'])

    def test_scope_and_reference_rejection(self):
        other = 'test-' + uuid4().hex
        self.store.provision_registry(other)
        foreign = self.store.propose(other, 'admin-account-1', request())
        op = foreign['operation_id']
        self.assertEqual(self.client.get(f'/api/v1/config/proposals/{op}', headers=self.headers).status_code, 404)
        req = request()
        req['document']['parameters'] = {'capture_filter_profile': 'unknown'}
        r = self.client.post('/api/v1/config/proposals', headers=self.headers, json=req)
        op = r.json()['operation_id']
        r = self.client.post(f'/api/v1/config/proposals/{op}/validate', headers=self.headers, json={'expected_revision': 1})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertIn('parameters.capture_filter_profile', r.text)
        self.assertEqual(self.client.get(f'/api/v1/config/proposals/{op}', headers=self.headers).json()['status'], 'REJECTED')

    def test_setup_rejects_bootstrap_and_secrets_without_persistence(self):
        for field in ['postgres_dsn', 'password', 'command']:
            req = {'expected_version': 0, 'idempotency_key': 'invalid-request',
                   'document': {'step': 'review', 'parameters': {field: 'never-echo'}}}
            r = self.client.put('/api/v1/config/setup', headers=self.headers, json=req)
            self.assertEqual(r.status_code, 422)
            self.assertNotIn('never-echo', r.text)
        result = self.client.get('/api/v1/config/setup', headers=self.headers).json()
        self.assertEqual(result['version'], 0)
        self.assertEqual(result['state'], 'not_started')
        self.assertFalse(result['operational'])
