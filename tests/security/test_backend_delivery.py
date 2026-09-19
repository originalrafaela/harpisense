from __future__ import annotations

import base64
import json
import os
import tempfile
import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Iterator

from edge.capture.aggregator import WindowAggregator
from edge.capture.backend_client import BackendClient, BackendClientConfig
from edge.capture.events import PacketObservation
from edge.capture.scapy_gateway import flush_events


class _BackendHandler(BaseHTTPRequestHandler):
    status_code = 202
    response_body: dict[str, object] = {"accepted": True, "duplicate": False, "id": "evt-db-1", "received_at": "2026-09-15T22:30:02.000Z"}
    received: list[dict[str, object]] = []
    auth_headers: list[str | None] = []

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.__class__.received.append(json.loads(body.decode("utf-8")))
        self.__class__.auth_headers.append(self.headers.get("Authorization"))
        self.send_response(self.__class__.status_code)
        if self.__class__.status_code == 401:
            self.send_header("WWW-Authenticate", "Basic")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.__class__.response_body).encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:
        return


class SimulatedBackend:
    def __init__(self, status_code: int = 202, response_body: dict[str, object] | None = None) -> None:
        _BackendHandler.status_code = status_code
        _BackendHandler.response_body = response_body or {
            "accepted": True,
            "duplicate": False,
            "id": "evt-db-1",
            "received_at": "2026-09-15T22:30:02.000Z",
        }
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
    def test_simulated_backend_202_marks_delivery_confirmed_with_basic_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, _gateway_credentials(), SimulatedBackend(status_code=202) as backend:
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
            self.assertIn("aggregation", backend.received[0])
            self.assertEqual(backend.auth_headers, [_basic_header("edge-gateway", "edge-secret")])
            delivery = json.loads(delivery_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue(delivery["backend_delivered"])
            self.assertEqual(delivery["backend_status_code"], 202)
            self.assertFalse(delivery["backend_duplicate"])
            self.assertIsNone(delivery["backend_error"])

    def test_simulated_backend_202_duplicate_marks_delivery_confirmed(self) -> None:
        with _gateway_credentials(), SimulatedBackend(
            status_code=202,
            response_body={"accepted": True, "duplicate": True, "id": "evt-db-1", "received_at": "2026-09-15T22:30:02.000Z"},
        ) as backend:
            result = BackendClient(BackendClientConfig(url=backend.url, timeout_seconds=2)).post_network_event(
                _contract_network_event()
            )

            self.assertTrue(result.delivered)
            self.assertEqual(result.status_code, 202)
            self.assertTrue(result.duplicate)

    def test_missing_basic_credentials_do_not_send_without_authentication(self) -> None:
        with _without_gateway_credentials(), SimulatedBackend(status_code=202) as backend:
            result = BackendClient(BackendClientConfig(url=backend.url, timeout_seconds=2)).post_network_event(
                _contract_network_event()
            )

            self.assertFalse(result.delivered)
            self.assertIsNone(result.status_code)
            self.assertIn("missing backend Basic credentials", result.error or "")
            self.assertIn("HARPISENSE_BACKEND_USERNAME", result.error or "")
            self.assertIn("HARPISENSE_BACKEND_PASSWORD", result.error or "")
            self.assertNotIn("edge-secret", result.error or "")
            self.assertEqual(backend.received, [])

    def test_network_window_is_not_sent_to_network_events_endpoint(self) -> None:
        with _gateway_credentials(), SimulatedBackend(status_code=202) as backend:
            result = BackendClient(BackendClientConfig(url=backend.url, timeout_seconds=2)).post_network_event(
                {"event_type": "network_window"}
            )

            self.assertFalse(result.delivered)
            self.assertIsNone(result.status_code)
            self.assertIn("event_type=network_event", result.error or "")
            self.assertEqual(backend.received, [])

    def test_simulated_auth_and_contract_failures_are_not_marked_delivered(self) -> None:
        cases = [
            (401, {"error": {"code": "unauthorized", "message": "invalid gateway credentials"}}),
            (403, {"error": {"code": "forbidden", "message": "gateway cannot access this endpoint"}}),
            (409, {"error": {"code": "identifier_conflict", "message": "event_id already exists with different content"}}),
            (503, {"error": {"code": "gateway_credentials_unconfigured", "message": "gateway credentials are not configured"}}),
        ]
        for status_code, body in cases:
            with self.subTest(status_code=status_code), _gateway_credentials(), SimulatedBackend(status_code=status_code, response_body=body) as backend:
                result = BackendClient(BackendClientConfig(url=backend.url, timeout_seconds=2)).post_network_event(
                    _contract_network_event()
                )

                self.assertFalse(result.delivered)
                self.assertEqual(result.status_code, status_code)
                self.assertIn(f"HTTP {status_code}", result.error or "")
                self.assertIn(str(body["error"]["code"]), result.error or "")
                self.assertEqual(len(backend.received), 1)
                self.assertEqual(backend.received[0]["event_id"], "evt-known")

    def test_simulated_connection_failure_is_not_marked_delivered(self) -> None:
        with _gateway_credentials():
            client = BackendClient(BackendClientConfig(url="http://127.0.0.1:9/api/v1/ingest/network-events", timeout_seconds=0.2))

            result = client.post_network_event(_contract_network_event())

            self.assertFalse(result.delivered)
            self.assertIsNone(result.status_code)
            self.assertIsNotNone(result.error)


def _contract_network_event() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "event_id": "evt-known",
        "event_type": "network_event",
        "observed_at": "2026-09-15T22:30:01.000Z",
        "sensor_id": "harpisense.gateway.edge-1",
        "capture": {
            "interface": "eth-iot",
            "direction": "iot_to_test",
            "protocol": "tcp",
            "src_ip": "192.168.20.31",
            "src_port": 49152,
            "dst_ip": "192.168.30.20",
            "dst_port": 1883,
            "packet_size_bytes": 100,
            "tcp_flags": None,
        },
        "mqtt": {
            "present": False,
            "message_type": None,
            "topic": None,
            "client_id": None,
        },
        "classification": {
            "stage": "raw_capture",
            "label": "unknown",
            "confidence": None,
        },
    }


def _basic_header(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


@contextmanager
def _gateway_credentials() -> Iterator[None]:
    with _temporary_env(
        HARPISENSE_BACKEND_USERNAME="edge-gateway",
        HARPISENSE_BACKEND_PASSWORD="edge-secret",
    ):
        yield


@contextmanager
def _without_gateway_credentials() -> Iterator[None]:
    with _temporary_env(HARPISENSE_BACKEND_USERNAME=None, HARPISENSE_BACKEND_PASSWORD=None):
        yield


@contextmanager
def _temporary_env(**values: str | None) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
