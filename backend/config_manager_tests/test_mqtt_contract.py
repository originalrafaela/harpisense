"""Contract tests without OS services, live brokers or a database."""
import unittest
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from config_manager.api import install_config_api
from config_manager.mqtt import mqtt_capabilities, mqtt_status
from config_manager.schema import Capabilities, ConfigError, checked, validate_document
from config_manager.setup import SETUP_SCHEMA


class MqttContractTests(unittest.TestCase):
    def setUp(self):
        self.capabilities = Capabilities(revision='policy-1',
            mqtt_hosts=frozenset({'broker.example'}),
            mqtt_topics=frozenset({'harpisense/telemetry'}))

    def test_allowlist_is_not_connectivity_evidence(self):
        result = mqtt_capabilities(self.capabilities)
        self.assertEqual(result['default_mode'], 'local_managed')
        self.assertEqual(result['constraints']['hosts'], ['broker.example'])
        self.assertFalse(result['operations']['verify_connection'])
        self.assertFalse(result['operations']['apply'])
        self.assertFalse(result['operations']['register_device'])
        self.assertFalse(result['external_server_mutation'])
        self.assertEqual(mqtt_status()['broker']['state'], 'not_verified')

    def test_component_broker_consumer_and_devices_are_independent_unknowns(self):
        result = mqtt_status()
        for key in ('component', 'broker', 'consumer'):
            self.assertEqual(result[key], {'state': 'not_verified', 'observed_at': None})
        self.assertEqual(result['devices'], [])
        self.assertEqual(result['device_observation'], 'not_verified')

    def test_modes_persist_as_partial_draft_but_require_complete_proposal(self):
        for mode in ('local_managed', 'external'):
            draft = {'step': 'mqtt', 'parameters': {'mqtt_broker_mode': mode}}
            self.assertEqual(checked(draft, SETUP_SCHEMA), draft)
            with self.assertRaisesRegex(ConfigError, 'INCOMPLETE_MQTT_CONFIG'):
                validate_document({'schema_version': '1.0.0',
                    'record_type': 'config.document', 'parameters': draft['parameters']})
        with self.assertRaises(ConfigError):
            checked({'step': 'mqtt', 'parameters': {'mqtt_broker_mode': 'shell'}}, SETUP_SCHEMA)

    def test_discovery_uses_existing_auth_and_performs_no_database_or_service_operations(self):
        app = FastAPI()
        def admin(request: Request):
            if request.headers.get('Authorization') != 'Bearer test-session':
                raise HTTPException(401)
        app.state.require_admin_session = admin
        # No connect/propose/apply methods: discovery cannot invoke side effects.
        install_config_api(app, SimpleNamespace(capabilities=self.capabilities), installation_id='test')
        client = TestClient(app)
        for path in ('/api/v1/config/catalog', '/api/v1/config/mqtt/status'):
            self.assertEqual(client.get(path).status_code, 401)
            response = client.get(path, headers={'Authorization': 'Bearer test-session'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        response = client.get('/api/v1/config/catalog', headers={'Authorization': 'Bearer test-session'})
        self.assertEqual(response.json()['mqtt'], mqtt_capabilities(self.capabilities))


if __name__ == '__main__':
    unittest.main()
