from __future__ import annotations

import argparse
import ipaddress
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edge.capture.aggregator import WindowAggregator
from edge.capture.backend_client import BackendClient, BackendClientConfig
from edge.capture.events import PacketObservation, parse_mqtt_from_tcp_payload


@dataclass(frozen=True)
class CaptureConfig:
    sensor_id: str
    interfaces: list[str]
    iot_networks: list[ipaddress._BaseNetwork]
    test_networks: list[ipaddress._BaseNetwork]
    broker_host: str | None
    mqtt_port: int
    window_seconds: int
    backend_url: str | None
    backend_timeout_seconds: float
    backend_token_env: str | None
    backend_token_file: Path | None
    output_jsonl: Path
    delivery_jsonl: Path | None
    bpf_filter: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture legitimate MQTT traffic metadata on the HarpiSense gateway")
    parser.add_argument("--sensor-id", default="harpisense.gateway.edge-1")
    parser.add_argument("--iface", action="append", required=True, help="Gateway interface to capture. Repeat for both sides.")
    parser.add_argument("--iot-cidr", action="append", default=[], help="IoT-side CIDR, for example 192.168.20.0/24")
    parser.add_argument("--test-cidr", action="append", default=[], help="Test/broker-side CIDR, for example 192.168.30.0/24")
    parser.add_argument("--broker-host", help="Broker IP or hostname used for capture filtering context")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--window-seconds", type=int, default=30)
    parser.add_argument("--backend-url", help="Backend endpoint, for example http://localhost:8000/api/v1/ingest/network-events")
    parser.add_argument("--backend-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--backend-token-env", help="Optional environment variable containing a backend bearer token if agreed")
    parser.add_argument("--backend-token-file", help="Optional local file containing a backend bearer token if agreed")
    parser.add_argument("--output-jsonl", default="edge/capture/network-events.jsonl")
    parser.add_argument("--delivery-jsonl", default="edge/capture/network-event-delivery.jsonl")
    parser.add_argument("--duration-seconds", type=int, default=0, help="0 means run until interrupted")
    parser.add_argument("--bpf-filter", help="Override BPF filter. Default captures tcp port --mqtt-port.")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> CaptureConfig:
    return CaptureConfig(
        sensor_id=args.sensor_id,
        interfaces=args.iface,
        iot_networks=[ipaddress.ip_network(value, strict=False) for value in args.iot_cidr],
        test_networks=[ipaddress.ip_network(value, strict=False) for value in args.test_cidr],
        broker_host=args.broker_host,
        mqtt_port=args.mqtt_port,
        window_seconds=args.window_seconds,
        backend_url=args.backend_url,
        backend_timeout_seconds=args.backend_timeout_seconds,
        backend_token_env=args.backend_token_env,
        backend_token_file=Path(args.backend_token_file) if args.backend_token_file else None,
        output_jsonl=Path(args.output_jsonl),
        delivery_jsonl=Path(args.delivery_jsonl) if args.delivery_jsonl else None,
        bpf_filter=args.bpf_filter or f"tcp port {args.mqtt_port}",
    )


def packet_to_observation(packet: object, config: CaptureConfig) -> PacketObservation | None:
    from scapy.layers.inet import IP, TCP, UDP
    from scapy.packet import Raw

    if IP not in packet:
        return None

    ip_layer = packet[IP]
    protocol = "tcp" if TCP in packet else "udp" if UDP in packet else str(ip_layer.proto)
    transport = packet[TCP] if TCP in packet else packet[UDP] if UDP in packet else None
    src_port = int(transport.sport) if transport else None
    dst_port = int(transport.dport) if transport else None
    payload = bytes(packet[Raw].load) if Raw in packet else b""
    mqtt = parse_mqtt_from_tcp_payload(payload) if protocol == "tcp" and config.mqtt_port in {src_port, dst_port} else {}

    observed_at = datetime.fromtimestamp(float(getattr(packet, "time", time.time())), tz=timezone.utc)
    interface = getattr(packet, "sniffed_on", None) or "unknown"

    return PacketObservation(
        observed_at=observed_at,
        interface=str(interface),
        direction=direction_for(str(ip_layer.src), str(ip_layer.dst), config),
        protocol=protocol,
        src_ip=str(ip_layer.src),
        src_port=src_port,
        dst_ip=str(ip_layer.dst),
        dst_port=dst_port,
        packet_size_bytes=len(bytes(packet)),
        tcp_flags=str(packet[TCP].flags) if TCP in packet else None,
        mqtt_present=bool(mqtt.get("present")),
        mqtt_message_type=mqtt.get("message_type"),
        mqtt_topic=mqtt.get("topic"),
        mqtt_client_id=mqtt.get("client_id"),
    )


def direction_for(src_ip: str, dst_ip: str, config: CaptureConfig) -> str:
    src = ipaddress.ip_address(src_ip)
    dst = ipaddress.ip_address(dst_ip)
    src_iot = any(src in network for network in config.iot_networks)
    dst_iot = any(dst in network for network in config.iot_networks)
    src_test = any(src in network for network in config.test_networks)
    dst_test = any(dst in network for network in config.test_networks)

    if src_iot and dst_test:
        return "iot_to_test"
    if src_test and dst_iot:
        return "test_to_iot"
    if src_iot or dst_iot:
        return "iot_boundary"
    return "unknown"


def flush_events(
    observations: list[PacketObservation],
    aggregator: WindowAggregator,
    output_jsonl: Path,
    backend_client: BackendClient | None,
    delivery_jsonl: Path | None,
) -> int:
    events = aggregator.aggregate(observations)
    if not events:
        return 0

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("a", encoding="utf-8") as output:
        for event in events:
            output.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n")
            if backend_client:
                delivery = backend_client.post_network_event(event)
                write_delivery_record(delivery_jsonl, event, delivery.delivered, delivery.status_code, delivery.error)
    return len(events)


def write_delivery_record(
    delivery_jsonl: Path | None,
    event: dict[str, Any],
    delivered: bool,
    status_code: int | None,
    error: str | None,
) -> None:
    if delivery_jsonl is None:
        return
    delivery_jsonl.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event_id": event.get("event_id"),
        "backend_delivered": delivered,
        "backend_status_code": status_code,
        "backend_error": error,
    }
    with delivery_jsonl.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")


def run_capture(config: CaptureConfig, duration_seconds: int) -> int:
    from scapy.sendrecv import sniff

    observations: list[PacketObservation] = []
    aggregator = WindowAggregator(
        sensor_id=config.sensor_id,
        window_seconds=config.window_seconds,
        expected_interfaces=config.interfaces,
    )
    backend_client = (
        BackendClient(
            BackendClientConfig(
                url=config.backend_url,
                timeout_seconds=config.backend_timeout_seconds,
                token_env=config.backend_token_env,
                token_file=config.backend_token_file,
            )
        )
        if config.backend_url
        else None
    )

    def handle_packet(packet: object) -> None:
        observation = packet_to_observation(packet, config)
        if observation:
            observations.append(observation)

    sniff(iface=config.interfaces, filter=config.bpf_filter, prn=handle_packet, store=False, timeout=duration_seconds or None)
    emitted = flush_events(observations, aggregator, config.output_jsonl, backend_client, config.delivery_jsonl)
    print(f"captured_observations={len(observations)} emitted_events={emitted} output={config.output_jsonl}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = config_from_args(args)
    try:
        return run_capture(config, args.duration_seconds)
    except ImportError as exc:
        print(f"Scapy is required on the gateway host: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
