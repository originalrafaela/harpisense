import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from p08_p09_pipeline import run_pipeline


class SignedCoveragePipelineTests(unittest.TestCase):
    def test_signed_source_records_reach_p09_gate_without_releasing_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            session_name = "synthetic-p08-session"
            pcap = base / f"{session_name}.pcap"
            pcap.write_bytes(b"synthetic-pcap-content")
            coverage_path = base / f"{session_name}.coverage.json"
            session = {
                "pcap_path": str(pcap),
                "pcap_size_bytes": pcap.stat().st_size,
                "pcap_sha256": hashlib.sha256(pcap.read_bytes()).hexdigest(),
                "collection_complete": False,
                "ready_for_inference": False,
            }
            coverage_doc = {
                "session": session_name,
                "collection_complete": False,
                "ready_for_inference": False,
            }
            (base / f"{session_name}.session.json").write_text(json.dumps(session), encoding="utf-8")
            coverage_path.write_text(json.dumps(coverage_doc), encoding="utf-8")
            start = "2026-10-27T00:00:00Z"
            end = "2026-10-27T00:00:10Z"
            proof = [{
                "source": "mqtt_broker", "start": start, "end": end,
                "collection_session_id": session_name,
                "sensor_id": "sensor-test", "target_ref": "target-test",
                "verified": True,
                "verification_method": "ed25519_signed_manifest_and_interval_chain",
                "evidence_refs": [{"manifest_sha256": "b" * 64, "signature_verified": True}],
            }]
            result = run_pipeline(
                base_dir=base,
                session_name=session_name,
                events=[],
                windows=[{
                    "window_id": "w-1", "window_start": start, "window_end": end,
                    "collection_session_id": session_name,
                    "sensor_id": "sensor-test", "target_ref": "target-test",
                }],
                coverage_records=proof,
                required_sources=["mqtt_broker"],
                coverage_provenance_verified=True,
            )
            self.assertTrue(result["artifact_consistent"])
            self.assertTrue(result["coverage_provenance_verified"])
            self.assertFalse(result["authorized_for_inference"])
            self.assertFalse(result["authorized_for_ips"])
            self.assertEqual(result["log_counts"], {})


if __name__ == "__main__":
    unittest.main()
