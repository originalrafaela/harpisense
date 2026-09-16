from __future__ import annotations

import argparse
import os
import signal
import sys
import time

import paho.mqtt.client as mqtt

from mqtt_contract import ENVIRONMENT_TOPICS, build_environment_payload, dumps_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish HarpiSense poste telemetry.")
    parser.add_argument("--device", choices=sorted(ENVIRONMENT_TOPICS), default="poste-2")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME", "iot_device_lab"))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD"))
    parser.add_argument("--count", type=int, default=0, help="0 means publish until interrupted.")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--start-sequence", type=int, default=1)
    parser.add_argument("--exercise-reconnect", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.password:
        print("MQTT password is required via --password or MQTT_PASSWORD.", file=sys.stderr)
        return 2

    stop = False

    def handle_stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.device)
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

    topic = ENVIRONMENT_TOPICS[args.device]
    sequence = args.start_sequence
    published = 0

    try:
        while not stop and (args.count == 0 or published < args.count):
            payload = build_environment_payload(args.device, sequence)
            result = client.publish(topic, dumps_payload(payload), qos=1)
            result.wait_for_publish()
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"publish failed with rc={result.rc}")
            print(f"published topic={topic} sequence={sequence} message_id={payload['message_id']}")

            published += 1
            sequence += 1

            if args.exercise_reconnect and published == 1 and (args.count == 0 or args.count > 1):
                print("forcing client reconnect after first publish")
                client.disconnect()
                time.sleep(1.0)
                client.reconnect()

            if args.count == 0 or published < args.count:
                time.sleep(args.interval)
    finally:
        client.loop_stop()
        client.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
