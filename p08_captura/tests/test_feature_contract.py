import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integracao"))
from audit_feature_contract import audit


class FeatureContractTests(unittest.TestCase):
    def setUp(self):
        self.session = dict(session_id="s", sensor_id="sensor", traffic_profile="tcp-observacao",
                            source_ip="192.0.2.2", destination_ip="192.0.2.1",
                            capture_effective_started_at="2026-10-31T00:00:00Z",
                            capture_effective_ended_at="2026-10-31T00:00:20Z")
        self.schema = dict(version="harpisense.if.window.v1", window_seconds_default=10,
                           metadata_required=["window_id"], metadata_required_operational=[],
                           group_by=["sensor_id", "src_ip", "dst_ip"], features_default=["packet_count"])
        self.row = dict(window_id="w", collection_session_id="s", sensor_id="sensor",
                        traffic_profile="tcp-observacao", src_ip="192.0.2.2", dst_ip="192.0.2.1",
                        window_start="2026-10-31T00:00:00Z", window_end="2026-10-31T00:00:10Z",
                        window_seconds=10, feature_schema_version=self.schema["version"], packet_count=0)

    def check(self, row=None, metadata=None):
        return audit({"aggregation": {"windows": [row or self.row]}}, self.session, self.schema, metadata)

    def test_schema_pass_does_not_claim_model_or_inference(self):
        result = self.check()
        self.assertEqual(result["structural_compatibility"], "PASS")
        self.assertEqual(result["model_compatibility"], "NOT_VERIFIED")
        self.assertFalse(result["authorized_for_inference"])

    def test_missing_optional_model_feature_never_becomes_zero(self):
        result = self.check(metadata=dict(features=["mqtt_publish_count"], profile="tcp-observacao", window_seconds=10))
        self.assertEqual(result["model_compatibility"], "BLOCKED")
        self.assertNotIn("mqtt_publish_count", self.row)

    def test_partial_wrong_identity_and_nonfinite_rejected(self):
        for key, value in (("collection_session_id", "other"), ("packet_count", float("nan")),
                           ("window_start", "2026-10-30T23:59:59Z"), ("packet_count", True)):
            row = copy.deepcopy(self.row)
            row[key] = value
            self.assertEqual(self.check(row)["structural_compatibility"], "BLOCKED")
