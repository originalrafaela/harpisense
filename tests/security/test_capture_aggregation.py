from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from edge.capture.aggregator import WindowAggregator
from edge.capture.events import PacketObservation, parse_mqtt_from_tcp_payload


class CaptureAggregationTests(unittest.TestCase):
    def test_aggregates_known_packets_and_verifies_gateway_traversal(self) -> None:
        base = datetime(2026, 9, 15, 22, 30, 1, 125000, tzinfo=timezone.utc)
        observations = [
            PacketObservation(
                observed_at=base,
                interface="eth-iot",
                direction="iot_to_test",
                protocol="tcp",
                src_ip="192.168.20.31",
                src_port=49152,
                dst_ip="192.168.30.20",
                dst_port=1883,
                packet_size_bytes=100,
                tcp_flags="PA",
                mqtt_present=True,
                mqtt_message_type="PUBLISH",
                mqtt_topic="harpisense/v1/telemetry/harpisense.poste.poste-1/environment",
                mqtt_client_id=None,
            ),
            PacketObservation(
                observed_at=base.replace(second=5),
                interface="eth-test",
                direction="iot_to_test",
                protocol="tcp",
                src_ip="192.168.20.31",
                src_port=49152,
                dst_ip="192.168.30.20",
                dst_port=1883,
                packet_size_bytes=130,
                tcp_flags="PA",
                mqtt_present=True,
                mqtt_message_type="PUBLISH",
                mqtt_topic="harpisense/v1/telemetry/harpisense.poste.poste-1/environment",
                mqtt_client_id=None,
            ),
        ]

        events = WindowAggregator(
            sensor_id="harpisense.gateway.edge-1",
            window_seconds=30,
            expected_interfaces=["eth-iot", "eth-test"],
        ).aggregate(observations)

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event_type"], "network_event")
        self.assertEqual(event["classification"]["stage"], "raw_capture")
        self.assertEqual(event["classification"]["label"], "unknown")
        self.assertIsNone(event["classification"]["confidence"])
        self.assertEqual(event["capture"]["packet_size_bytes"], 230)
        self.assertEqual(event["aggregation"]["packet_count"], 2)
        self.assertEqual(event["aggregation"]["total_packet_size_bytes"], 230)
        self.assertTrue(event["aggregation"]["traversal_verified"])
        self.assertEqual(event["aggregation"]["traversal_evidence"]["observed_interfaces"], ["eth-iot", "eth-test"])
        self.assertEqual(event["mqtt"]["message_type"], "PUBLISH")
        self.assertIsNone(event["mqtt"]["client_id"])

    def test_single_interface_does_not_claim_traversal(self) -> None:
        observation = PacketObservation(
            observed_at=datetime(2026, 9, 15, 22, 30, 1, tzinfo=timezone.utc),
            interface="eth-iot",
            direction="iot_to_test",
            protocol="tcp",
            src_ip="192.168.20.31",
            src_port=49152,
            dst_ip="192.168.30.20",
            dst_port=1883,
            packet_size_bytes=100,
        )

        event = WindowAggregator(
            sensor_id="harpisense.gateway.edge-1",
            window_seconds=30,
            expected_interfaces=["eth-iot", "eth-test"],
        ).aggregate([observation])[0]

        self.assertFalse(event["aggregation"]["traversal_verified"])
        self.assertIn("missing configured gateway interface", event["aggregation"]["traversal_reason"])

    def test_window_boundaries_use_packet_timestamps(self) -> None:
        base = datetime(2026, 9, 15, 22, 30, 0, tzinfo=timezone.utc)
        observations = [
            _observation(base + timedelta(seconds=30), packet_size_bytes=300),
            _observation(base + timedelta(seconds=29, milliseconds=999), packet_size_bytes=200),
            _observation(base, packet_size_bytes=100),
        ]

        events = WindowAggregator(
            sensor_id="harpisense.gateway.edge-1",
            window_seconds=30,
            expected_interfaces=["eth-iot", "eth-test"],
        ).aggregate(observations)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["aggregation"]["window_start"], "2026-09-15T22:30:00.000Z")
        self.assertEqual(events[0]["aggregation"]["packet_count"], 2)
        self.assertEqual(events[0]["aggregation"]["total_packet_size_bytes"], 300)
        self.assertEqual(events[1]["aggregation"]["window_start"], "2026-09-15T22:30:30.000Z")
        self.assertEqual(events[1]["aggregation"]["packet_count"], 1)
        self.assertEqual(events[1]["aggregation"]["total_packet_size_bytes"], 300)

    def test_mqtt_publish_parser_extracts_topic_without_auth_result(self) -> None:
        topic = b"harpisense/v1/telemetry/harpisense.poste.poste-1/environment"
        payload = bytes([0x30, len(topic) + 2 + 2]) + len(topic).to_bytes(2, "big") + topic + b"{}"

        mqtt = parse_mqtt_from_tcp_payload(payload)

        self.assertTrue(mqtt["present"])
        self.assertEqual(mqtt["message_type"], "PUBLISH")
        self.assertEqual(mqtt["topic"], topic.decode("utf-8"))
        self.assertIsNone(mqtt["client_id"])
        self.assertNotIn("result", mqtt)


def _observation(observed_at: datetime, packet_size_bytes: int) -> PacketObservation:
    return PacketObservation(
        observed_at=observed_at,
        interface="eth-iot",
        direction="iot_to_test",
        protocol="tcp",
        src_ip="192.168.20.31",
        src_port=49152,
        dst_ip="192.168.30.20",
        dst_port=1883,
        packet_size_bytes=packet_size_bytes,
    )


if __name__ == "__main__":
    unittest.main()
