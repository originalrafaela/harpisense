"""HTTP composition tests; generated text is explicitly synthetic/unverified."""
import os
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from delivery.projections import create_app
from harpia.client import Client
from harpia.p11 import install_deterministic_harpia
from harpia.server import LocalServer


class Store:
    def history(self, kind, identifier):
        return ([{'revision': 2, 'data': {'incident_id': identifier, 'revision': 2,
                  'status': 'OPEN', 'risk': {'status': 'unknown'}}}]
                if kind == 'incident' and identifier == 'fixture-incident' else [])

    def list(self, *args, **kwargs):
        return []


class Runtime:
    loaded = True

    def ready(self):
        return self.loaded

    def complete(self, text, tokens):
        return 'Texto sintético não verificado; dados insuficientes.'


class P11BitNetTests(unittest.TestCase):
    def setUp(self):
        self.runtime = Runtime()
        self.server = LocalServer(('127.0.0.1', 0), self.runtime, 'fixture-token')
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .02})
        self.thread.start()
        self.adapter = Client('http://127.0.0.1:' + str(self.server.server_port), 'fixture-token', timeout=2)
        self.app = create_app(Store(), username='technical', password='fixture-password', service_token='fixture-service')
        install_deterministic_harpia(self.app, Store(), bitnet_client=self.adapter)
        self.http = TestClient(self.app)
        self.auth = ('technical', 'fixture-password')

    def tearDown(self):
        self.http.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def test_loaded_model_is_reported_and_text_is_bound_to_revision(self):
        health = self.http.get('/api/v1/p11/health', auth=self.auth).json()['harpia']
        self.assertEqual(health['mode'], 'bitnet_optional')
        self.assertTrue(health['generation_enabled'])
        self.assertTrue(health['model_ready'])
        value = self.http.get('/api/v1/p11/explain/fixture-incident', auth=self.auth).json()
        self.assertEqual((value['incident_id'], value['revision']), ('fixture-incident', 2))
        self.assertEqual(value['source'], 'bitnet_unverified_text')
        self.assertIn('Explicação determinística', value['deterministic_text'])

    def test_live_http_without_loaded_model_reports_not_ready_and_falls_back(self):
        self.runtime.loaded = False
        health = self.http.get('/api/v1/p11/health', auth=self.auth).json()['harpia']
        self.assertFalse(health['model_ready'])
        value = self.http.get('/api/v1/p11/explain/fixture-incident', auth=self.auth).json()
        self.assertEqual(value['source'], 'deterministic_fallback')
        self.assertEqual(value['bitnet_status'], 'unavailable_or_timeout')
        self.assertIn('Risk Engine', value['text'])

    def test_missing_incident_and_unauthenticated_requests_never_generate(self):
        self.assertEqual(self.http.get('/api/v1/p11/explain/fixture-incident').status_code, 401)
        self.assertEqual(self.http.get('/api/v1/p11/explain/missing', auth=self.auth).status_code, 404)
        self.assertEqual(len(self.server.engine.cache), 0)

    def test_generic_composition_includes_mfa_xai_and_dossier_with_authentication(self):
        from delivery.app import build_candidate_app
        from config_manager.schema import Capabilities
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://unused/fixture',
                'HARPISENSE_ADMIN_USER': 'technical', 'HARPISENSE_ADMIN_PASSWORD': 'fixture-password',
                'HARPISENSE_PROJECTION_SERVICE_TOKEN': 'fixture-service', 'HARPISENSE_BITNET_ENABLED': '0'}):
            app = build_candidate_app(installation_id='fixture-installation', capabilities=Capabilities(revision='fixture'),
                allowed_origins=['http://127.0.0.1:4174'], protection_key=Fernet.generate_key())
        routes = app.openapi()['paths']
        self.assertIn('/api/v1/admin-auth/mfa/verify', routes)
        self.assertIn('/api/v1/p11/incidents/{incident_id}/explanations', routes)
        self.assertIn('/api/v1/p11/incidents/{incident_id}/dossier', routes)
        with TestClient(app) as client:
            for path in ('/api/v1/p11/incidents/fixture/explanations', '/api/v1/p11/incidents/fixture/dossier'):
                self.assertEqual(client.get(path).status_code, 401)
                self.assertEqual(client.get(path, auth=self.auth).status_code, 401)
            self.assertEqual(client.post('/api/v1/admin-auth/mfa/verify', json={}).status_code, 422)

    def test_enabled_composition_refuses_external_model_url(self):
        from delivery.app import build_app
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://unused/fixture',
                'HARPISENSE_ADMIN_USER': 'technical', 'HARPISENSE_ADMIN_PASSWORD': 'fixture-password',
                'HARPISENSE_BITNET_ENABLED': '1', 'HARPIA_URL': 'https://external.invalid'}):
            with self.assertRaisesRegex(ValueError, 'loopback'):
                build_app()


if __name__ == '__main__':
    unittest.main()
