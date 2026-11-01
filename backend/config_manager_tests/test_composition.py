"""Candidate bootstrap acceptance, exclusively on a disposable shared DB."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from admin_auth import AdminAuth
from config_manager.schema import Capabilities
from config_manager.store import ConfigStore, migrate
from config_manager.setup import migrate_setup
from delivery.app import build_candidate_app
from delivery.postgres_store import PostgresStore
from delivery.mqtt_consumer import bind_consumer
from delivery.mqtt_input import POSTE2_TOPIC, POSTE1_TOPIC
from unittest.mock import Mock
from test_config_manager import request


@unittest.skipUnless(os.getenv('HARPISENSE_CONFIG_TEST_DSN'), 'Isolated PostgreSQL required')
class CompositionTests(unittest.TestCase):
    def test_login_setup_proposal_validate_restart_and_existing_services(self):
        dsn = os.environ['HARPISENSE_CONFIG_TEST_DSN']
        connect = lambda: psycopg.connect(dsn)
        with connect() as conn:
            if conn.info.dbname != 'config_fixture':
                raise RuntimeError('Disposable fixture only')
            root = Path(__file__).parents[1]
            conn.execute((root / 'delivery/001_local.sql').read_text())
            if not conn.execute("SELECT to_regclass('hs_admin_account')").fetchone()[0]:
                conn.execute((root / 'admin_auth/001_admin_auth.sql').read_text())
        migrate(connect)
        migrate_setup(connect)
        auth = AdminAuth(dsn)
        with connect() as conn:
            present = conn.execute('SELECT 1 FROM hs_admin_account').fetchone()
        if not present:
            auth.provision('fixture-admin', 'isolated-config-fixture-password')
        installation = 'composition-' + uuid4().hex
        capabilities = Capabilities(revision='composition-fixture')
        ConfigStore(connect, capabilities).provision_registry(installation)
        with patch.dict(os.environ, DATABASE_URL=dsn, HARPISENSE_ADMIN_USER='technical-fixture',
                        HARPISENSE_ADMIN_PASSWORD='technical-password',
                        HARPISENSE_PROJECTION_SERVICE_TOKEN='fixture-service-token'):
            def boot():
                return TestClient(build_candidate_app(installation_id=installation,
                    capabilities=capabilities, allowed_origins=['http://localhost']))
            client = boot()
            self.assertEqual(client.get('/api/v1/config/current').status_code, 401)
            self.assertEqual(client.get('/api/v1/config/current',
                auth=('technical-fixture', 'technical-password')).status_code, 401)
            login = client.post('/api/v1/admin-auth/login', json={
                'username': 'fixture-admin', 'password': 'isolated-config-fixture-password'})
            self.assertEqual(login.status_code, 200)
            headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
            self.assertEqual(client.get('/api/v1/p11/health', headers=headers).status_code, 200)
            ingest = client.post('/api/v1/p11/ingest/telemetry',
                auth=('technical-fixture', 'technical-password'),
                headers={'X-Service-Token': 'fixture-service-token'},
                json={'id': installation, 'revision': 1, 'source': 'trusted-service',
                      'data': {'device_id': 'poste2'}})
            self.assertEqual(ingest.status_code, 201, ingest.text)
            progress = {'expected_version': 0, 'idempotency_key': uuid4().hex,
                'document': {'step': 'review', 'parameters': {'display_name': 'Fixture'}}}
            saved = client.put('/api/v1/config/setup', headers=headers, json=progress)
            self.assertEqual(saved.status_code, 200, saved.text)
            proposed = client.post('/api/v1/config/proposals', headers=headers, json=request())
            self.assertEqual(proposed.status_code, 200, proposed.text)
            operation = proposed.json()['operation_id']
            validated = client.post(f'/api/v1/config/proposals/{operation}/validate',
                headers=headers, json={'expected_revision': 1})
            self.assertEqual(validated.json()['status'], 'VALIDATED', validated.text)
            restarted = boot()
            resumed = restarted.get('/api/v1/config/setup', headers=headers).json()
            for key in ('version', 'document'):
                self.assertEqual(resumed[key], saved.json()[key])
            self.assertFalse(resumed['operational'])
            current = restarted.get('/api/v1/config/current', headers=headers).json()
            self.assertEqual(current['state'], 'validated')
            self.assertIsNone(current['effective_revision'])
            self.assertFalse(current['operational'])
            self.assertEqual(restarted.post('/api/v1/config/apply', headers=headers).status_code, 404)
            self.assertEqual(restarted.get('/api/v1/security/settings/mode/default', headers=headers).status_code, 200)
            self.assertEqual(restarted.get('/api/v1/p11/explain/missing', headers=headers).status_code, 404)
            mqtt = Mock()
            bind_consumer(mqtt, PostgresStore(dsn), Mock(), log=Mock())
            raw = ('{"device_id":"poste2","fixture":"' + installation + '"}').encode()
            self.assertEqual(mqtt.on_message(mqtt, None, Mock(topic=POSTE2_TOPIC, payload=raw)), 'inserted')
            self.assertEqual(mqtt.on_message(mqtt, None, Mock(topic=POSTE2_TOPIC, payload=raw)), 'duplicate')
            self.assertEqual(mqtt.on_message(mqtt, None, Mock(topic=POSTE1_TOPIC, payload=raw)), 'disabled')
            self.assertEqual(client.post('/api/v1/admin-auth/logout', headers=headers).status_code, 204)
            self.assertEqual(restarted.get('/api/v1/config/setup', headers=headers).status_code, 401)
