import unittest
from context_adapter import attach_context


class TestContextSecurity(unittest.TestCase):

    def setUp(self):
        self.event = {
            "evidence_id": "e1",
            "event_type": "mqtt_auth_failure",
            "observed_at": "2026-10-15T12:00:05Z",
            "coverage": "COMPLETE",
        }

        self.binding = {
            "evidence_id": "e1",
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }

    def test_duplicate_evidence_rejected(self):
        with self.assertRaises(ValueError):
            attach_context(
                [self.event, dict(self.event)],
                [self.binding]
            )

    def test_unexpected_binding_rejected(self):
        extra = {
            **self.binding,
            "evidence_id": "unknown"
        }

        with self.assertRaises(ValueError):
            attach_context(
                [self.event],
                [self.binding, extra]
            )

    def test_empty_evidence_id_rejected(self):
        event = {
            **self.event,
            "evidence_id": "   "
        }

        with self.assertRaises(ValueError):
            attach_context([event], [self.binding])


if __name__ == "__main__":
    unittest.main()
