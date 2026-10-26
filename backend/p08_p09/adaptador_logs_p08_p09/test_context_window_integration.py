import unittest

from context_adapter import attach_context
from log_window_adapter import prepare_log_counts


class TestContextWindowIntegration(unittest.TestCase):

    def test_context_to_window(self):
        evidence = {
            "evidence_id": "e1",
            "event_type": "mqtt_auth_failure",
            "observed_at": "2026-10-15T12:00:05Z",
            "coverage": "COMPLETE",
        }

        binding = {
            "evidence_id": "e1",
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }

        window = {
            "window_id": "w1",
            "window_start": "2026-10-15T12:00:00Z",
            "window_end": "2026-10-15T12:00:10Z",
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }

        enriched = attach_context([evidence], [binding])
        counts = prepare_log_counts(enriched, [window])

        self.assertEqual(counts["w1"]["auth_failures"], 1)
        self.assertNotIn("target_ref", evidence)


if __name__ == "__main__":
    unittest.main()
