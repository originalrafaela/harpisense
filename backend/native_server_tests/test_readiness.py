"""Deterministic regression of broker start race, without services or databases."""
from pathlib import Path
import ssl
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for name in ('backend', 'backend/domain', 'genai'):
    sys.path.insert(0, str(ROOT/name))
from native_server.runtime import wait_for_broker


class ReadinessTests(unittest.TestCase):
    def test_delayed_listener_is_accepted(self):
        ready = {'connected': True, 'subscribed': True}
        with patch('native_server.runtime.probe_broker', side_effect=[
                ConnectionRefusedError(), ConnectionRefusedError(), ready]) as probe, \
                patch('native_server.runtime.time.sleep') as sleep:
            self.assertEqual(wait_for_broker({}), ready)
            self.assertEqual(probe.call_count, 3)
            self.assertEqual(sleep.call_count, 2)

    def test_refusal_has_deadline(self):
        with patch('native_server.runtime.probe_broker', side_effect=ConnectionRefusedError()) as probe, \
                patch('native_server.runtime.time.monotonic', side_effect=[0, 0, 0, 1, 2]), \
                patch('native_server.runtime.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, '^MQTT_BROKER_START_TIMEOUT$'):
                wait_for_broker({}, timeout=1)
            self.assertEqual(probe.call_count, 2)

    def test_tls_and_auth_fail_without_retry(self):
        for error in (ssl.SSLCertVerificationError('invalid certificate'),
                      RuntimeError('MQTT_CONNECT_OR_SUBSCRIBE_REJECTED')):
            with self.subTest(error=type(error).__name__), \
                    patch('native_server.runtime.probe_broker', side_effect=error) as probe, \
                    patch('native_server.runtime.time.sleep') as sleep:
                with self.assertRaises(type(error)):
                    wait_for_broker({})
                self.assertEqual(probe.call_count, 1)
                sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
