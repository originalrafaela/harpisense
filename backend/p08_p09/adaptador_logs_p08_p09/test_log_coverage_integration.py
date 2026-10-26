import unittest

from log_coverage_integration import prepare_verified_log_counts


class TestLogCoverageIntegration(unittest.TestCase):

    def test_untrusted_coverage_must_not_release_counts(self):
        window = {
            "window_id": "w1",
            "window_start": "2026-10-15T12:00:00Z",
            "window_end": "2026-10-15T12:00:10Z",
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }

        evidence = {
            "evidence_id": "e1",
            "event_type": "mqtt_auth_failure",
            "observed_at": "2026-10-15T12:00:05Z",
            "coverage": "COMPLETE",
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }

        coverage = {
            "source": "mosquitto",
            "start": "2026-10-15T12:00:00Z",
            "end": "2026-10-15T12:00:10Z",
            "verified": True,
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }

        result = prepare_verified_log_counts(
            events=[evidence],
            windows=[window],
            coverage_records=[coverage],
            required_sources=("mosquitto",),
        )

        self.assertFalse(result["authorized_for_inference"])
        self.assertEqual(result["log_counts"], {})
        self.assertTrue(result["reasons"])


if __name__ == "__main__":
    unittest.main()
