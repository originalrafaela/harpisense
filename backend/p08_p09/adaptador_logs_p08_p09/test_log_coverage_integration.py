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

    def test_signed_coverage_proof_is_recorded_but_counts_stay_blocked(self):
        window = {
            "window_id": "w1",
            "window_start": "2026-10-15T12:00:00Z",
            "window_end": "2026-10-15T12:00:10Z",
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
        }
        proof = [{
            "source": "mosquitto",
            "start": window["window_start"],
            "end": window["window_end"],
            "collection_session_id": "session-A",
            "sensor_id": "sensor-A",
            "target_ref": "device-A",
            "verified": True,
            "verification_method": "ed25519_signed_manifest_and_interval_chain",
            "evidence_refs": [{"manifest_sha256": "a" * 64, "signature_verified": True}],
        }]
        result = prepare_verified_log_counts(
            events=[], windows=[window], coverage_records=proof,
            required_sources=["mosquitto"], coverage_provenance_verified=True,
        )
        self.assertTrue(result["coverage_provenance_verified"])
        self.assertFalse(result["authorized_for_inference"])
        self.assertEqual(result["log_counts"], {})
        self.assertIn("Contagens permanecem bloqueadas", result["reasons"][-1])


if __name__ == "__main__":
    unittest.main()
