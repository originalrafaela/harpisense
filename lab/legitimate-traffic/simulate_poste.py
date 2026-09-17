from __future__ import annotations

import argparse
import json
import os
import random
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import paho.mqtt.client as mqtt

from mqtt_contract import (
    DEFAULT_POSTE_IDS,
    build_environment_payload,
    device_label_to_id,
    dumps_payload,
    topic_for_device_id,
)


@dataclass
class SimulatedPoste:
    label: str
    sequence: int
    temperature_c: float
    humidity_pct: float
    rssi_dbm: int

    @property
    def device_id(self) -> str:
        return device_label_to_id(self.label)

    @property
    def topic(self) -> str:
        return topic_for_device_id(self.device_id)


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def configured_devices(args: argparse.Namespace) -> list[str]:
    if args.post_count is not None and args.post_count < 1:
        raise ValueError("--post-count must be at least 1")

    if args.devices:
        devices = parse_csv(args.devices)
    elif args.device:
        devices = [args.device]
    elif args.post_count is not None:
        devices = [f"{args.device_prefix}{number}" for number in range(args.start_post_number, args.start_post_number + args.post_count)]
    else:
        devices = list(DEFAULT_POSTE_IDS)

    if args.post_count is not None and args.devices:
        devices = devices[: args.post_count]

    if not devices:
        raise ValueError("at least one device must be configured")

    duplicates = sorted({device for device in devices if devices.count(device) > 1})
    if duplicates:
        raise ValueError(f"duplicated device identifiers: {', '.join(duplicates)}")

    for device in devices:
        if not device.startswith("poste-") and not device.startswith("harpisense.poste.poste-"):
            raise ValueError(f"device identifier must be poste-* or harpisense.poste.poste-*: {device}")

    return devices


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish or generate synthetic HarpiSense poste telemetry.")
    parser.add_argument("--device", help="Legacy single poste identifier, for example poste-2.")
    parser.add_argument("--devices", help="Comma-separated poste identifiers, for example poste-2,poste-3.")
    parser.add_argument("--post-count", type=int, help="Number of synthetic postes to simulate.")
    parser.add_argument("--device-prefix", default="poste-", help="Prefix used with --post-count when --devices is omitted.")
    parser.add_argument("--start-post-number", type=int, default=2)
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME", "iot_device_lab"))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD"))
    parser.add_argument("--count", type=int, default=0, help="Number of publication cycles. 0 means run until interrupted, or one cycle in --jsonl mode without --duration.")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between publication cycles.")
    parser.add_argument("--duration", type=float, default=0.0, help="Maximum run duration in seconds. 0 disables duration limit.")
    parser.add_argument("--start-sequence", type=int, default=1)
    parser.add_argument("--seed", type=int, help="Random seed for reproducible synthetic readings.")
    parser.add_argument("--jsonl", help="Write local JSONL instead of connecting to MQTT. Use '-' for stdout.")
    parser.add_argument("--exercise-reconnect", action="store_true")
    parser.add_argument("--publish-retries", type=int, default=1, help="Retries for the same MQTT message after publish failure.")
    return parser.parse_args()


def make_postes(device_labels: list[str], start_sequence: int, rng: random.Random) -> list[SimulatedPoste]:
    return [
        SimulatedPoste(
            label=device,
            sequence=start_sequence,
            temperature_c=round(rng.uniform(22.0, 31.5), 1),
            humidity_pct=round(rng.uniform(45.0, 78.0), 1),
            rssi_dbm=rng.randint(-72, -48),
        )
        for device in device_labels
    ]


def next_payload(poste: SimulatedPoste, rng: random.Random) -> dict[str, object]:
    poste.temperature_c = round(min(35.0, max(18.0, poste.temperature_c + rng.uniform(-0.5, 0.5))), 1)
    poste.humidity_pct = round(min(85.0, max(35.0, poste.humidity_pct + rng.uniform(-1.8, 1.8))), 1)
    poste.rssi_dbm = int(min(-40, max(-85, poste.rssi_dbm + rng.choice([-2, -1, 0, 1, 2]))))

    payload = build_environment_payload(
        poste.label,
        poste.sequence,
        temperature_c=poste.temperature_c,
        humidity_pct=poste.humidity_pct,
        rssi_dbm=poste.rssi_dbm,
    )
    poste.sequence += 1
    return payload


def session_metadata(args: argparse.Namespace, postes: list[SimulatedPoste], mode: str) -> dict[str, object]:
    return {
        "record_type": "session_metadata",
        "mode": mode,
        "synthetic": True,
        "contract": "harpisense/v1/telemetry/<device_id>/environment",
        "post_count": len(postes),
        "devices": [poste.device_id for poste in postes],
        "interval_seconds": args.interval,
        "duration_seconds": args.duration,
        "seed": args.seed,
        "note": "Dados sinteticos gerados pelo simulador; o payload de telemetria permanece no contrato compartilhado.",
    }


def cycle_limit(args: argparse.Namespace) -> int | None:
    if args.count > 0:
        return args.count
    if args.duration > 0:
        return None
    if args.jsonl:
        return 1
    return None


def should_continue(started_at: float, completed_cycles: int, args: argparse.Namespace, stop: bool) -> bool:
    if stop:
        return False
    limit = cycle_limit(args)
    if limit is not None and completed_cycles >= limit:
        return False
    if args.duration > 0 and time.monotonic() - started_at >= args.duration:
        return False
    return True


def write_jsonl(args: argparse.Namespace, postes: list[SimulatedPoste], rng: random.Random) -> int:
    output: TextIO
    close_output = False
    if args.jsonl == "-":
        output = sys.stdout
    else:
        output_path = Path(args.jsonl)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output = output_path.open("w", encoding="utf-8", newline="\n")
        close_output = True

    started_at = time.monotonic()
    completed_cycles = 0

    try:
        output.write(json.dumps(session_metadata(args, postes, "jsonl"), ensure_ascii=False) + "\n")
        while should_continue(started_at, completed_cycles, args, False):
            for poste in postes:
                payload = next_payload(poste, rng)
                record = {
                    "record_type": "telemetry",
                    "synthetic": True,
                    "topic": poste.topic,
                    "payload": payload,
                }
                output.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
            output.flush()
            completed_cycles += 1
            if should_continue(started_at, completed_cycles, args, False):
                time.sleep(args.interval)
    finally:
        if close_output:
            output.close()

    return 0


def publish_payload(client: mqtt.Client, topic: str, payload: dict[str, object], retries: int) -> None:
    encoded = dumps_payload(payload)
    attempts = 0

    while True:
        result = client.publish(topic, encoded, qos=1)
        result.wait_for_publish()
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            return

        attempts += 1
        if attempts > retries:
            raise RuntimeError(f"publish failed with rc={result.rc}")

        print(f"retransmitting topic={topic} message_id={payload['message_id']} attempt={attempts}")
        client.reconnect()


def publish_mqtt(args: argparse.Namespace, postes: list[SimulatedPoste], rng: random.Random) -> int:
    if not args.password:
        print("MQTT password is required via --password or MQTT_PASSWORD.", file=sys.stderr)
        return 2

    stop = False

    def handle_stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="synthetic-poste-simulator")
    client.username_pw_set(args.username, args.password)
    client.reconnect_delay_set(min_delay=1, max_delay=10)

    def on_connect(_client: mqtt.Client, _userdata: object, _flags: mqtt.ConnectFlags, reason_code: mqtt.ReasonCode, _properties: mqtt.Properties | None) -> None:
        print(f"connected reason_code={reason_code}")

    def on_disconnect(_client: mqtt.Client, _userdata: object, _flags: mqtt.DisconnectFlags, reason_code: mqtt.ReasonCode, _properties: mqtt.Properties | None) -> None:
        print(f"disconnected reason_code={reason_code}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()

    started_at = time.monotonic()
    completed_cycles = 0

    print(json.dumps(session_metadata(args, postes, "mqtt"), ensure_ascii=False))

    try:
        while should_continue(started_at, completed_cycles, args, stop):
            for poste in postes:
                payload = next_payload(poste, rng)
                publish_payload(client, poste.topic, payload, args.publish_retries)
                print(f"published topic={poste.topic} sequence={payload['sequence']} message_id={payload['message_id']}")

            completed_cycles += 1

            if args.exercise_reconnect and completed_cycles == 1 and should_continue(started_at, completed_cycles, args, stop):
                print("forcing client reconnect after first publication cycle")
                client.disconnect()
                time.sleep(1.0)
                client.reconnect()

            if should_continue(started_at, completed_cycles, args, stop):
                time.sleep(args.interval)
    finally:
        client.loop_stop()
        client.disconnect()

    return 0


def main() -> int:
    args = parse_args()

    if args.count < 0:
        print("--count must be zero or greater", file=sys.stderr)
        return 2
    if args.interval < 0:
        print("--interval must be zero or greater", file=sys.stderr)
        return 2
    if args.duration < 0:
        print("--duration must be zero or greater", file=sys.stderr)
        return 2
    if args.publish_retries < 0:
        print("--publish-retries must be zero or greater", file=sys.stderr)
        return 2

    try:
        device_labels = configured_devices(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    postes = make_postes(device_labels, args.start_sequence, rng)

    if args.jsonl:
        return write_jsonl(args, postes, rng)
    return publish_mqtt(args, postes, rng)


if __name__ == "__main__":
    raise SystemExit(main())
