from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from edge.capture.aggregator import WindowAggregator
from edge.capture.backend_client import BackendClient, BackendClientConfig
from edge.capture.events import PacketObservation
from edge.capture.scapy_gateway import flush_events


class _BackendHandler(BaseHTTPRequestHandler):
    status_code = 202
    received: list[dict[str, object]] = []
    auth_headers: list[str | None] = []

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.__class__.received.append(json.loads(body.decode("utf-8")))
        self.__class__.auth_headers.append(self.headers.get("Authorization"))
        self.send_response(self.__class__.status_code)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class SimulatedBackend:
    def __init__(self, status_code: int = 202) -> None:
        _BackendHandler.status_code = status_code
        _BackendHandler.received = []
        _BackendHandler.auth_headers = []
        self.server = HTTPServer(("127.0.0.1", 0), _BackendHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/api/v1/ingest/network-events"

    @property
    def received(self) -> list[dict[str, object]]:
        return _BackendHandler.received

    @property
    def auth_headers(self) -> list[str | None]:
        return _BackendHandler.auth_headers

    def __enter__(self) -> "SimulatedBackend":
        self.thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def known_observation() -> PacketObservation:
    return PacketObservation(
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


class BackendDeliverySimulationTests(unittest.TestCase):
    def test_simulated_backend_202_marks_delivery_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, SimulatedBackend(status_code=202) as backend:
            event_path = Path(tmpdir) / "events.jsonl"
            delivery_path = Path(tmpdir) / "delivery.jsonl"
            client = BackendClient(BackendClientConfig(url=backend.url, timeout_seconds=2))

            emitted = flush_events(
                [known_observation()],
                WindowAggregator(sensor_id="harpisense.gateway.edge-1", window_seconds=30, expected_interfaces=["eth-iot", "eth-test"]),
                event_path,
                client,
                delivery_path,
            )

            self.assertEqual(emitted, 1)
            self.assertEqual(len(backend.received), 1)
            self.assertEqual(backend.received[0]["event_type"], "network_event")
            delivery = json.loads(delivery_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue(delivery["backend_delivered"])
            self.assertEqual(delivery["backend_status_code"], 202)
            self.assertIsNone(delivery["backend_error"])

    def test_simulated_backend_failure_is_not_marked_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, SimulatedBackend(status_code=500) as backend:
            delivery_path = Path(tmpdir) / "delivery.jsonl"
            client = BackendClient(BackendClientConfig(url=backend.url, timeout_seconds=2))

            flush_events(
                [known_observation()],
                WindowAggregator(sensor_id="harpisense.gateway.edge-1", window_seconds=30, expected_interfaces=["eth-iot", "eth-test"]),
                Path(tmpdir) / "events.jsonl",
                client,
                delivery_path,
            )

            delivery = json.loads(delivery_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertFalse(delivery["backend_delivered"])
            self.assertEqual(delivery["backend_status_code"], 500)
            self.assertIn("HTTP 500", delivery["backend_error"])

    def test_simulated_connection_failure_is_not_marked_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            delivery_path = Path(tmpdir) / "delivery.jsonl"
            client = BackendClient(BackendClientConfig(url="http://127.0.0.1:9/api/v1/ingest/network-events", timeout_seconds=0.2))

            flush_events(
                [known_observation()],
                WindowAggregator(sensor_id="harpisense.gateway.edge-1", window_seconds=30, expected_interfaces=["eth-iot", "eth-test"]),
                Path(tmpdir) / "events.jsonl",
                client,
                delivery_path,
            )

            delivery = json.loads(delivery_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertFalse(delivery["backend_delivered"])
            self.assertIsNone(delivery["backend_status_code"])
            self.assertIsNotNone(delivery["backend_error"])

    def test_optional_bearer_token_file_is_sent_to_simulated_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, SimulatedBackend(status_code=202) as backend:
            token_path = Path(tmpdir) / ".env.edge-backend-token"
            token_path.write_text("local-test-token\n", encoding="utf-8")
            client = BackendClient(
                BackendClientConfig(url=backend.url, timeout_seconds=2, token_file=token_path)
            )

            result = client.post_network_event({"event_type": "network_event"})

            self.assertTrue(result.delivered)
            self.assertEqual(backend.auth_headers, ["Bearer local-test-token"])


if __name__ == "__main__":
    unittest.main()
