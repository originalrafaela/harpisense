import unittest
from unittest.mock import Mock

from delivery.mqtt_consumer import bind_consumer
from delivery.mqtt_input import POSTE1_TOPIC, POSTE2_TOPIC
import test_mqtt_input as fixtures
from test_mqtt_input import sample, wire


class CallbackTests(unittest.TestCase):
    def test_closed_reconnect_and_client_configuration_preserved(self):
        client, store = Mock(), Mock()
        adapter = bind_consumer(client, store, Mock(), log=Mock())
        client.on_connect(client, None, None, Mock(is_failure=True), None)
        client.subscribe.assert_not_called()
        for _ in range(2):
            client.on_connect(client, None, None, Mock(is_failure=False), None)
        self.assertEqual(client.subscribe.call_count, 2)
        client.subscribe.assert_called_with(POSTE2_TOPIC, qos=1)
        self.assertEqual(client.on_message(client, None, Mock(
            topic=POSTE1_TOPIC, payload=wire(sample()))), "disabled")
        store.insert.assert_not_called()
        for method in (client.connect, client.username_pw_set, client.tls_set,
                       client.loop_forever):
            method.assert_not_called()
        self.assertFalse(adapter.poste1_enabled)

    def test_operational_failure_is_sanitized(self):
        client, store, log, audit = Mock(), Mock(), Mock(), Mock()
        store.insert.side_effect = RuntimeError("secret-value")
        bind_consumer(client, store, audit, log=log)
        self.assertEqual(client.on_message(client, None, Mock(
            topic=POSTE2_TOPIC, payload=b'{"device_id":"poste2"}')),
            "operational_error")
        audit.assert_not_called()
        self.assertNotIn("secret-value", str(log.call_args))


class CallbackPostgreSQLTests(fixtures.PostgreSQLTests):
    # Run all persistence/concurrency and Poste 2 regressions through the bound
    # callback, rather than calling the input adapter directly.
    def setUp(self):
        super().setUp()
        client = Mock()
        bind_consumer(client, self.store, lambda event: None,
                      poste1_enabled=True, log=Mock())
        self.adapter.handle = lambda topic, raw: client.on_message(
            client, None, Mock(topic=topic, payload=raw))
