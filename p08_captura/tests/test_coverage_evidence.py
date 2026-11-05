import base64
import hashlib
import json
import os
import struct
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integracao"))
from coverage_evidence import (
    SOURCE_SCHEMA,
    _pcap_counts,
    build_coverage_report,
    canonical_json,
    link_auxiliary_events,
    load_profile,
    public_key_fingerprint,
    sign_payload,
)
from build_source_manifest import build_source_bundle


def utc(offset):
    return (datetime(2026, 10, 27, tzinfo=timezone.utc) + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")


def pcap_empty():
    return b"\xd4\xc3\xb2\xa1" + struct.pack("<HHIIII", 2, 4, 0, 0, 65535, 1)


class SignedCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.keydir = self.root / "keys"
        self.keydir.mkdir()
        self.private = {}
        self.public = {}
        for name in ("gateway", "broker"):
            private = self.keydir / f"{name}.pem"
            public = self.keydir / f"{name}.pub"
            subprocess.run(["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private)], check=True, capture_output=True)
            os.chmod(private, 0o600)
            subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], check=True, capture_output=True)
            self.private[name] = private
            self.public[name] = public
        self.profile = {
            "schema_version": "harpisense.p08.capture-profile.v1",
            "profile_id": "synthetic-profile",
            "traffic_profile": "tcp-observacao",
            "sensor_id": "synthetic-sensor",
            "target_ref": "synthetic-target",
            "interface": "eth0",
            "source_ip": "192.0.2.10",
            "destination_ip": "192.0.2.1",
            "required_sources": [
                {
                    "source": "gateway_capture", "kind": "gateway_capture",
                    "host_id": "gateway", "public_key": str(self.public["gateway"]),
                    "public_key_sha256": public_key_fingerprint(self.public["gateway"]),
                },
                {
                    "source": "mqtt_broker", "kind": "signed_log_bundle",
                    "host_id": "broker-test", "auxiliary_mqtt": True,
                    "public_key": str(self.public["broker"]),
                    "public_key_sha256": public_key_fingerprint(self.public["broker"]),
                },
            ],
        }
        self.profile_path = self.root / "profile.json"
        self.profile_path.write_text(json.dumps(self.profile), encoding="utf-8")
        self.profile["_sha256"] = hashlib.sha256(self.profile_path.read_bytes()).hexdigest()
        self.session_id = "p08-synthetic-001"
        self.pcap = self.root / f"{self.session_id}.pcap"
        self.pcap.write_bytes(pcap_empty())
        self.session_path = self.root / f"{self.session_id}.session.json"
        self.signature_path = Path(str(self.session_path) + ".sig")
        self.session = {
            "schema_version": "harpisense.capture.session.v1",
            "session_id": self.session_id,
            "profile_id": self.profile["profile_id"],
            "profile_sha256": self.profile["_sha256"],
            "traffic_profile": self.profile["traffic_profile"],
            "sensor_id": self.profile["sensor_id"],
            "target_ref": self.profile["target_ref"],
            "interface": self.profile["interface"],
            "source_ip": self.profile["source_ip"],
            "required_sources": ["gateway_capture", "mqtt_broker"],
            "started_at": utc(-2),
            "capture_effective_started_at": utc(0),
            "capture_effective_ended_at": utc(20),
            "finished_at": utc(20),
            "duration_requested_seconds": 20,
            "effective_duration_seconds": 20,
            "termination_reason": "duration_elapsed",
            "interruption": None,
            "capture_errors": [],
            "session_basic_checks_passed": True,
            "pcap_path": str(self.pcap),
            "pcap_size_bytes": self.pcap.stat().st_size,
            "pcap_sha256": hashlib.sha256(self.pcap.read_bytes()).hexdigest(),
            "tcpdump_stats": {
                "packets_captured": 0,
                "packets_received_by_filter": 0,
                "packets_dropped_by_kernel": 0,
            },
            "process_monitoring": {
                "heartbeat_interval_seconds": 1,
                "observations": [
                    {"timestamp": utc(i), "phase": "capturing", "tcpdump_active": True,
                     "process_active": True, "monitor_scan_complete": True}
                    for i in range(1, 20)
                ],
            },
            "collection_complete": False,
            "ready_for_inference": False,
        }
        self.session_path.write_text(json.dumps(self.session), encoding="utf-8")
        self.signature_path.write_text(sign_payload(canonical_json(self.session), self.private["gateway"]), encoding="ascii")
        self.evidence_dir = self.root / "evidence"
        self.broker_dir = self.evidence_dir / "mqtt_broker"
        self.broker_dir.mkdir(parents=True)

    def write_broker_bundle(self, records=None, *, interval_start=-1, interval_end=21):
        records = records or []
        records_path = self.broker_dir / "records.jsonl"
        records_path.write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in records), encoding="utf-8")
        manifest = {
            "schema_version": SOURCE_SCHEMA,
            "evidence_id": "synthetic-broker-evidence-1",
            "collection_session_id": self.session_id,
            "profile_id": self.profile["profile_id"],
            "traffic_profile": self.profile["traffic_profile"],
            "session_report_sha256": hashlib.sha256(self.session_path.read_bytes()).hexdigest(),
            "pcap_sha256": hashlib.sha256(self.pcap.read_bytes()).hexdigest(),
            "source": "mqtt_broker",
            "host_id": "broker-test",
            "sensor_id": self.profile["sensor_id"],
            "target_ref": self.profile["target_ref"],
            "boot_id": "broker-boot-synthetic",
            "interval_start": utc(interval_start),
            "interval_end": utc(interval_end),
            "cursor_start": "cursor-000",
            "cursor_end": "cursor-999",
            "coverage_status": "COMPLETE",
            "continuity_verified": True,
            "records_file": "records.jsonl",
            "records_sha256": hashlib.sha256(records_path.read_bytes()).hexdigest(),
            "record_count": len(records),
        }
        manifest["signature_ed25519"] = sign_payload(canonical_json(manifest), self.private["broker"])
        manifest_path = self.broker_dir / "001.manifest.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        return manifest_path, records_path

    def build(self):
        return build_coverage_report(
            self.session, self.session_path, self.signature_path,
            {"aggregation": {"windows": []}}, self.profile,
            self.evidence_dir, self.pcap,
        )

    def test_proven_empty_interval_is_distinct_from_unknown(self):
        startup_ts = int(datetime.fromisoformat(utc(-1).replace("Z", "+00:00")).timestamp())
        self.pcap.write_bytes(pcap_empty() + struct.pack("<IIII", startup_ts, 0, 0, 0))
        self.session["pcap_size_bytes"] = self.pcap.stat().st_size
        self.session["pcap_sha256"] = hashlib.sha256(self.pcap.read_bytes()).hexdigest()
        self.session_path.write_text(json.dumps(self.session), encoding="utf-8")
        self.signature_path.write_text(sign_payload(canonical_json(self.session), self.private["gateway"]), encoding="ascii")
        self.write_broker_bundle()
        report = self.build()
        self.assertEqual(report["source_coverage_status"], "COMPLETE")
        self.assertEqual(len(report["intervals"]), 2)
        self.assertTrue(all(item["observation_status"] == "OBSERVED_NO_EVENTS" for item in report["intervals"]))
        self.assertTrue(all(item["coverage_status"] == "COMPLETE" for item in report["intervals"]))
        self.assertFalse(report["collection_complete"])
        self.assertFalse(report["ready_for_inference"])
        self.assertEqual(report["pcap_startup_packets_excluded_from_effective_windows"], 1)

    def test_missing_required_source_stays_unknown(self):
        report = self.build()
        self.assertEqual(report["source_coverage"]["mqtt_broker"]["status"], "UNKNOWN")
        self.assertEqual(report["source_coverage_status"], "UNKNOWN")
        self.assertTrue(all(item["observation_status"] == "UNKNOWN" for item in report["intervals"]))
        self.assertEqual(report["coverage_records"], [])

    def test_signed_source_event_is_observed_in_its_window(self):
        self.write_broker_bundle([{"event_id": "e1", "observed_at": utc(5), "journal_cursor": "j-5", "journal_boot_id": "broker-boot-synthetic"}])
        report = self.build()
        self.assertEqual(report["intervals"][0]["observation_status"], "OBSERVED_WITH_EVENTS")
        self.assertEqual(report["intervals"][0]["source_event_records"], 1)

    def test_auxiliary_mqtt_requires_matching_signed_cursor_boot_and_time(self):
        cursor = "journal-cursor-5"
        boot = "broker-boot-synthetic"
        observed = utc(5)
        self.write_broker_bundle([{
            "event_id": "e1", "observed_at": observed,
            "journal_cursor": cursor, "journal_boot_id": boot,
        }])
        report = self.build()
        from datetime import datetime
        identity = {
            "collection_session_id": self.session_id,
            "sensor_id": self.profile["sensor_id"],
            "target_ref": self.profile["target_ref"],
            "profile_id": self.profile["profile_id"],
            "traffic_profile": self.profile["traffic_profile"],
            "session_report_sha256": hashlib.sha256(self.session_path.read_bytes()).hexdigest(),
            "pcap_sha256": hashlib.sha256(self.pcap.read_bytes()).hexdigest(),
            "start": datetime.fromisoformat(utc(0).replace("Z", "+00:00")),
            "end": datetime.fromisoformat(utc(20).replace("Z", "+00:00")),
        }
        batch = {"auxiliary_evidence": [{
            "event_type": "telemetry_validation_failure",
            "observed_at": observed,
            "journal_cursor": cursor,
            "journal_boot_id": boot,
        }]}
        linked = link_auxiliary_events(batch, self.evidence_dir, self.profile, identity, report["intervals"])
        self.assertEqual(linked["status"], "SESSION_LINKED")
        self.assertEqual(linked["events"][0]["status"], "SESSION_LINKED")
        batch["auxiliary_evidence"][0]["journal_cursor"] = "unmatched"
        unbound = link_auxiliary_events(batch, self.evidence_dir, self.profile, identity, report["intervals"])
        self.assertEqual(unbound["status"], "UNBOUND")

    def test_evidence_outside_effective_session_is_rejected(self):
        self.write_broker_bundle([{"event_id": "late", "observed_at": utc(20.5)}])
        report = self.build()
        self.assertEqual(report["source_coverage"]["mqtt_broker"]["status"], "INCOMPLETE")
        self.assertTrue(any("fora do período efetivo" in reason for reason in report["source_coverage"]["mqtt_broker"]["reasons"]))

    def test_tampered_source_records_fail_hash_validation(self):
        _manifest, records = self.write_broker_bundle()
        records.write_text('{"event_id":"tampered","observed_at":"2026-10-27T00:00:01Z"}\n', encoding="utf-8")
        report = self.build()
        self.assertEqual(report["source_coverage"]["mqtt_broker"]["status"], "INCOMPLETE")
        self.assertTrue(any("Hash dos registros" in reason for reason in report["source_coverage"]["mqtt_broker"]["reasons"]))

    def test_tampered_pcap_fails_local_source_verification(self):
        self.write_broker_bundle()
        self.pcap.write_bytes(pcap_empty()[:-1] + b"\x02")
        report = self.build()
        self.assertEqual(report["source_coverage"]["gateway_capture"]["status"], "INCOMPLETE")
        self.assertEqual(report["source_coverage_status"], "INCOMPLETE")

    def test_source_bundle_builder_signs_sanitized_export_and_imports_it(self):
        raw = self.root / "raw-records.jsonl"
        raw.write_text(json.dumps({
            "event_id": "event-sanitized", "observed_at": utc(7),
            "journal_cursor": "j-7", "journal_boot_id": "broker-boot-synthetic",
            "payload": "sensitive-data-that-must-not-be-exported",
        }) + "\n", encoding="utf-8")
        out = self.root / "built-bundle"
        out.mkdir()
        manifest, records = build_source_bundle(
            profile_path=self.profile_path,
            session_report_path=self.session_path,
            source_id="mqtt_broker",
            input_records=raw,
            output_dir=out,
            signing_key=self.private["broker"],
            boot_id="broker-boot-synthetic",
            cursor_start="cursor-000",
            cursor_end="cursor-999",
            interval_start=utc(-1),
            interval_end=utc(21),
            continuity_verified=True,
            coverage_status="COMPLETE",
        )
        exported = records.read_text(encoding="utf-8")
        self.assertNotIn("sensitive-data", exported)
        self.assertIn("event-sanitized", exported)
        self.broker_dir.mkdir(parents=True, exist_ok=True)
        (self.broker_dir / manifest.name).write_bytes(manifest.read_bytes())
        (self.broker_dir / records.name).write_bytes(records.read_bytes())
        report = self.build()
        self.assertEqual(report["source_coverage"]["mqtt_broker"]["status"], "COMPLETE")
        self.assertEqual(report["intervals"][0]["observation_status"], "OBSERVED_WITH_EVENTS")

    def test_pcap_shutdown_tail_is_not_counted_in_effective_window(self):
        path = self.root / "tail.pcap"
        base = datetime(2026, 10, 27, tzinfo=timezone.utc)
        packet = b"synthetic"
        raw = bytearray(pcap_empty())
        for offset in (5, 11):
            raw.extend(struct.pack("<IIII", int((base + timedelta(seconds=offset)).timestamp()), 0, len(packet), len(packet)))
            raw.extend(packet)
        path.write_bytes(raw)
        counts, startup, tail = _pcap_counts(
            path, base, base + timedelta(seconds=10),
            base - timedelta(seconds=2), base + timedelta(seconds=12),
        )
        self.assertEqual(sum(counts.values()), 1)
        self.assertEqual(startup, 0)
        self.assertEqual(tail, 1)


if __name__ == "__main__":
    unittest.main()
