from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from edge.capture.aggregator import WindowAggregator
from edge.capture.events import EDGE_CAPTURE_FORMAT_VERSION, PacketObservation, build_network_event
from edge.capture.scapy_gateway import CaptureConfig, config_from_args, packet_to_observation


@dataclass(frozen=True)
class OfflinePcapSource:
    path: Path
    interface: str


@dataclass(frozen=True)
class OfflineExportConfig:
    sensor_id: str
    window_seconds: int
    expected_interfaces: list[str]
    collection_session_id: str
    raw_events_jsonl: Path
    windows_jsonl: Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process HarpiSense gateway PCAP files without replaying capture timing")
    parser.add_argument("--sensor-id", default="harpisense.gateway.edge-1")
    parser.add_argument("--pcap", action="append", required=True, help="PCAP file to process. Repeat for multiple interfaces.")
    parser.add_argument(
        "--pcap-interface",
        action="append",
        default=[],
        help="Interface name for the corresponding --pcap when the file does not carry interface metadata.",
    )
    parser.add_argument("--iface", action="append", default=[], help="Expected gateway interface for traversal evidence. Repeat for both sides.")
    parser.add_argument("--iot-cidr", action="append", default=[], help="IoT-side CIDR, for example 192.168.20.0/24")
    parser.add_argument("--test-cidr", action="append", default=[], help="Test/broker-side CIDR, for example 192.168.30.0/24")
    parser.add_argument("--broker-host", help="Broker IP or hostname used for capture filtering context")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--window-seconds", type=int, default=30)
    parser.add_argument("--collection-session-id", help="Stable id to stamp every exported raw event and aggregate window.")
    parser.add_argument("--raw-events-jsonl", default="edge/capture/offline-raw-events.jsonl")
    parser.add_argument("--windows-jsonl", default="edge/capture/offline-windows.jsonl")
    return parser.parse_args(argv)


def sources_from_args(args: argparse.Namespace) -> list[OfflinePcapSource]:
    interfaces = args.pcap_interface or []
    if interfaces and len(interfaces) != len(args.pcap):
        raise ValueError("--pcap-interface must be repeated once for each --pcap, or omitted")
    return [
        OfflinePcapSource(path=Path(path), interface=interfaces[index] if interfaces else "offline-pcap")
        for index, path in enumerate(args.pcap)
    ]


def capture_config_from_args(args: argparse.Namespace) -> CaptureConfig:
    capture_args = argparse.Namespace(
        sensor_id=args.sensor_id,
        iface=args.iface or args.pcap_interface or ["offline-pcap"],
        iot_cidr=args.iot_cidr,
        test_cidr=args.test_cidr,
        broker_host=args.broker_host,
        mqtt_port=args.mqtt_port,
        window_seconds=args.window_seconds,
        backend_url=None,
        backend_timeout_seconds=5.0,
        backend_username_env="HARPISENSE_BACKEND_USERNAME",
        backend_password_env="HARPISENSE_BACKEND_PASSWORD",
        output_jsonl="",
        delivery_jsonl=None,
        bpf_filter=None,
    )
    return config_from_args(capture_args)


def export_config_from_args(args: argparse.Namespace) -> OfflineExportConfig:
    session_id = args.collection_session_id or f"pcap-{uuid4().hex}"
    return OfflineExportConfig(
        sensor_id=args.sensor_id,
        window_seconds=args.window_seconds,
        expected_interfaces=args.iface or args.pcap_interface or ["offline-pcap"],
        collection_session_id=session_id,
        raw_events_jsonl=Path(args.raw_events_jsonl),
        windows_jsonl=Path(args.windows_jsonl),
    )


def load_pcap_observations(sources: Iterable[OfflinePcapSource], capture_config: CaptureConfig) -> list[PacketObservation]:
    from scapy.utils import PcapReader

    observations: list[PacketObservation] = []
    for source in sources:
        with PcapReader(str(source.path)) as packets:
            for packet in packets:
                observation = packet_to_observation(packet, capture_config)
                if observation is None:
                    continue
                interface = observation.interface if observation.interface != "unknown" else source.interface
                observations.append(
                    replace(
                        observation,
                        interface=interface,
                        metadata={**observation.metadata, "source_pcap": str(source.path)},
                    )
                )
    return observations


def export_offline_observations(observations: Iterable[PacketObservation], config: OfflineExportConfig) -> dict[str, Any]:
    ordered = sorted(observations, key=lambda item: item.observed_at)
    raw_events = [_with_offline_context(build_network_event(item, config.sensor_id), config, "raw_event") for item in ordered]

    aggregator = WindowAggregator(
        sensor_id=config.sensor_id,
        window_seconds=config.window_seconds,
        expected_interfaces=config.expected_interfaces,
    )
    windows = [
        _with_offline_context(_as_window_event(event), config, "aggregate_window")
        for event in aggregator.aggregate(ordered)
    ]

    _write_jsonl(config.raw_events_jsonl, raw_events)
    _write_jsonl(config.windows_jsonl, windows)

    return {
        "collection_session_id": config.collection_session_id,
        "format_version": EDGE_CAPTURE_FORMAT_VERSION,
        "raw_event_count": len(raw_events),
        "window_count": len(windows),
        "raw_events_jsonl": str(config.raw_events_jsonl),
        "windows_jsonl": str(config.windows_jsonl),
    }


def _with_offline_context(event: dict[str, Any], config: OfflineExportConfig, record_kind: str) -> dict[str, Any]:
    event["format_version"] = EDGE_CAPTURE_FORMAT_VERSION
    event["collection_session_id"] = config.collection_session_id
    event["collection_mode"] = "offline_pcap"
    event["record_kind"] = record_kind
    event.setdefault("mqtt", {})["auth_result"] = "unknown"
    event["mqtt"]["auth_failure_count"] = None
    return event


def _as_window_event(event: dict[str, Any]) -> dict[str, Any]:
    event = dict(event)
    event["event_type"] = "network_window"
    event["classification"] = {
        "stage": "window_aggregation",
        "label": "unknown",
        "confidence": None,
    }
    return event


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")


def run_offline_pcap(args: argparse.Namespace) -> int:
    sources = sources_from_args(args)
    capture_config = capture_config_from_args(args)
    export_config = export_config_from_args(args)
    observations = load_pcap_observations(sources, capture_config)
    summary = export_offline_observations(observations, export_config)
    print(json.dumps(summary, separators=(",", ":"), ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_offline_pcap(args)
    except ImportError as exc:
        print(f"Scapy is required to read PCAP files: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
