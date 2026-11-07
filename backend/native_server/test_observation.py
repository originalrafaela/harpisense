import unittest
from datetime import datetime, timedelta, timezone

from config_manager.mqtt import mqtt_status
from native_server.observation import project_observation


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
        self.state = {'mqtt': {'mode': 'external'}}
        self.row = dict(now=self.now, observed_at=self.now, connected=True,
                        subscribed=True, last_message_at=self.now,
                        last_message_id='message-1', last_projection_id='projection-1')

    def observe(self):
        return project_observation(self.state, self.row, mqtt_status())

    def test_connection_without_message_is_unknown(self):
        self.row['last_message_at'] = None
        result = self.observe()
        self.assertEqual(result['consumer']['state'], 'connected')
        self.assertEqual(result['device_observation'], 'not_verified')
        self.assertEqual(result['coverage']['state'], 'unknown')
        self.assertEqual(result['reason_code'], 'AWAITING_FIRST_MESSAGE')

    def test_fresh_message_only_covers_mqtt_scope(self):
        result = self.observe()
        self.assertEqual(result['coverage']['scope'], 'mqtt_telemetry')
        self.assertEqual(result['coverage']['state'], 'complete')
        self.assertEqual(result['coverage']['incident_state'], 'unknown')
        self.assertEqual(result['devices'][0]['source_origin'], 'unknown')
        self.assertEqual(result['devices'][0]['projection_revision'], 1)

    def test_stale_telemetry_is_preserved_while_consumer_connected(self):
        self.row['last_message_at'] -= timedelta(seconds=121)
        result = self.observe()
        self.assertEqual(result['reason_code'], 'TELEMETRY_STALE')
        self.assertEqual(result['coverage']['state'], 'partial')
        self.assertEqual(result['devices'][0]['projection_id'], 'projection-1')
        self.assertEqual(result['devices'][0]['availability'], 'unknown')

    def test_disconnect_reconnect_preserves_identity(self):
        before = self.observe()['devices'][0]
        self.row['connected'] = False
        lost = self.observe()
        self.assertEqual(lost['coverage']['state'], 'partial')
        self.assertEqual(lost['devices'][0]['message_id'], before['message_id'])
        self.row['connected'] = True
        self.assertEqual(self.observe()['devices'][0], before)

    def test_heartbeat_expiry_and_future_clock_fail_closed(self):
        for seconds in (-46, 1):
            self.row['observed_at'] = self.now + timedelta(seconds=seconds)
            self.assertEqual(self.observe()['device_observation'], 'not_verified')

    def test_future_telemetry_cannot_claim_freshness(self):
        self.row['last_message_at'] += timedelta(seconds=1)
        result = self.observe()
        self.assertEqual(result['devices'][0]['freshness'], 'unknown')
        self.assertEqual(result['reason_code'], 'TELEMETRY_TIMESTAMP_IN_FUTURE')

    def test_missing_observation_and_invalid_policy(self):
        result = project_observation(self.state, None, mqtt_status())
        self.assertEqual(result['coverage']['state'], 'unknown')
        for ttl in (True, 0, -1, '120'):
            self.state['mqtt']['telemetry_max_age_seconds'] = ttl
            with self.assertRaises(ValueError):
                self.observe()


if __name__ == '__main__':
    unittest.main()
