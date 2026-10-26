import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from p08_artifact_validator import validate_p08_artifacts


class TestP08ArtifactValidator(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.base = Path(self.temp.name)
        self.name = "test-session"

        self.pcap = self.base / f"{self.name}.pcap"
        self.session_path = self.base / f"{self.name}.session.json"
        self.coverage_path = self.base / f"{self.name}.coverage.json"

        self.pcap.write_bytes(b"synthetic-pcap-content")

        self.session = {
            "pcap_path": str(self.pcap),
            "pcap_size_bytes": self.pcap.stat().st_size,
            "pcap_sha256": hashlib.sha256(
                self.pcap.read_bytes()
            ).hexdigest(),
            "collection_complete": False,
            "ready_for_inference": False,
        }

        self.coverage = {
            "session": self.name,
            "collection_complete": False,
            "ready_for_inference": False,
        }

        self.save()

    def save(self):
        self.session_path.write_text(
            json.dumps(self.session), encoding="utf-8"
        )
        self.coverage_path.write_text(
            json.dumps(self.coverage), encoding="utf-8"
        )

    def validate(self):
        return validate_p08_artifacts(self.base, self.name)

    def test_consistent_artifacts(self):
        result = self.validate()
        self.assertTrue(result["consistent"])
        self.assertFalse(result["authorized_for_inference"])
        self.assertFalse(result["authorized_for_ips"])

    def test_modified_pcap(self):
        self.pcap.write_bytes(b"modified-pcap-content")
        result = self.validate()
        self.assertFalse(result["consistent"])
        self.assertFalse(result["checks"]["pcap_sha256_matches"])

    def test_wrong_session(self):
        self.coverage["session"] = "another-session"
        self.save()
        self.assertFalse(self.validate()["consistent"])

    def test_conflicting_collection_state(self):
        self.coverage["collection_complete"] = True
        self.save()
        self.assertFalse(self.validate()["consistent"])

    def test_inference_enabled_rejected(self):
        self.session["ready_for_inference"] = True
        self.coverage["ready_for_inference"] = True
        self.save()

        result = self.validate()
        self.assertFalse(result["consistent"])
        self.assertFalse(result["authorized_for_inference"])

    def test_invalid_session_name(self):
        with self.assertRaises(ValueError):
            validate_p08_artifacts(self.base, "../invalid")


if __name__ == "__main__":
    unittest.main()
