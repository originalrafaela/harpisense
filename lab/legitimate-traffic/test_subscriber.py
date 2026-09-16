from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import time

import paho.mqtt.client as mqtt

from mqtt_contract import validate_environment_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Subscribe and validate HarpiSense telemetry.")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME", "mqtt_test_subscriber"))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD"))
    parser.add_argument("--topic", default="harpisense/v1/telemetry/#")
    parser.add_argument("--expected-count", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.password:
        print("MQTT password is required via --password or MQTT_PASSWORD.", file=sys.stderr)
        return 2

    messages: queue.Queue[tuple[str, dict[str, object], list[str]]] = queue.Queue()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="mqtt-test-subscriber")
    client.username_pw_set(args.username, args.password)
    client.reconnect_delay_set(min_delay=1, max_delay=10)

    def on_connect(mqtt_client: mqtt.Client, _userdata: object, _flags: mqtt.ConnectFlags, reason_code: mqtt.ReasonCode, _properties: mqtt.Properties | None) -> None:
        print(f"connected reason_code={reason_code}")
        mqtt_client.subscribe(args.topic, qos=1)

    def on_message(_client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception as exc:
            messages.put((message.topic, {}, [f"invalid JSON UTF-8: {exc}"]))
            return

        errors = validate_environment_payload(message.topic, payload)
        messages.put((message.topic, payload, errors))

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()

    deadline = time.monotonic() + args.timeout
    received = 0
    failed = False

    try:
        while received < args.expected_count and time.monotonic() < deadline:
            try:
                topic, payload, errors = messages.get(timeout=0.5)
            except queue.Empty:
                continue

            received += 1
            print(json.dumps({"topic": topic, "payload": payload, "errors": errors}, ensure_ascii=False))
            if errors:
                failed = True
    finally:
        client.loop_stop()
        client.disconnect()

    if received < args.expected_count:
        print(f"timeout waiting for messages: received={received} expected={args.expected_count}", file=sys.stderr)
        return 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
