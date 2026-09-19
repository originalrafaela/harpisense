from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from edge.capture.events import PacketObservation
from edge.capture.offline_pcap import OfflineExportConfig, export_offline_observations


class OfflinePcapExportTests(unittest.TestCase):
    def test_exports_raw_events_in_temporal_order_and_windows_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "raw.jsonl"
            windows_path = Path(tmpdir) / "windows.jsonl"
            config = OfflineExportConfig(
                sensor_id="harpisense.gateway.edge-1",
                window_seconds=30,
                expected_interfaces=["eth-iot", "eth-test"],
                collection_session_id="session-known",
                raw_events_jsonl=raw_path,
                windows_jsonl=windows_path,
            )
            later = _observation(datetime(2026, 9, 15, 22, 30, 30, tzinfo=timezone.utc), "eth-iot", 300)
            earlier = _observation(datetime(2026, 9, 15, 22, 30, 1, tzinfo=timezone.utc), "eth-iot", 100)

            summary = export_offline_observations([later, earlier], config)

            raw_events = _read_jsonl(raw_path)
            windows = _read_jsonl(windows_path)
            self.assertEqual(summary["raw_event_count"], 2)
            self.assertEqual(summary["window_count"], 2)
            self.assertEqual([event["observed_at"] for event in raw_events], ["2026-09-15T22:30:01.000Z", "2026-09-15T22:30:30.000Z"])
            self.assertTrue(all(event["collection_session_id"] == "session-known" for event in raw_events + windows))
            self.assertTrue(all(event["format_version"] == "edge.capture.v1" for event in raw_events + windows))
            self.assertEqual({event["record_kind"] for event in raw_events}, {"raw_event"})
            self.assertEqual({event["record_kind"] for event in windows}, {"aggregate_window"})
            self.assertEqual({event["event_type"] for event in raw_events}, {"network_event"})
            self.assertEqual({event["event_type"] for event in windows}, {"network_window"})
            self.assertEqual(raw_events[0]["mqtt"]["auth_result"], "unknown")
            self.assertIsNone(raw_events[0]["mqtt"]["auth_failure_count"])

    def test_offline_window_counts_and_does_not_claim_missing_interface_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = OfflineExportConfig(
                sensor_id="harpisense.gateway.edge-1",
                window_seconds=30,
                expected_interfaces=["eth-iot", "eth-test"],
                collection_session_id="session-counts",
                raw_events_jsonl=Path(tmpdir) / "raw.jsonl",
                windows_jsonl=Path(tmpdir) / "windows.jsonl",
            )
            observations = [
                _observation(datetime(2026, 9, 15, 22, 30, 1, tzinfo=timezone.utc), "eth-iot", 100),
                _observation(datetime(2026, 9, 15, 22, 30, 5, tzinfo=timezone.utc), "eth-iot", 125),
            ]

            export_offline_observations(observations, config)

            windows = _read_jsonl(config.windows_jsonl)
            self.assertEqual(len(windows), 1)
            self.assertEqual(windows[0]["aggregation"]["packet_count"], 2)
            self.assertEqual(windows[0]["aggregation"]["total_packet_size_bytes"], 225)
            self.assertFalse(windows[0]["aggregation"]["traversal_verified"])
            self.assertIn("missing configured gateway interface", windows[0]["aggregation"]["traversal_reason"])


def _observation(observed_at: datetime, interface: str, packet_size_bytes: int) -> PacketObservation:
    return PacketObservation(
        observed_at=observed_at,
        interface=interface,
        direction="iot_to_test",
        protocol="tcp",
        src_ip="192.168.20.31",
        src_port=49152,
        dst_ip="192.168.30.20",
        dst_port=1883,
        packet_size_bytes=packet_size_bytes,
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
