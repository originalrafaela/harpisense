#!/usr/bin/env python3
"""Observador MQTT do HarpiSense: captura payloads e acrescenta ground truth fora do dispositivo."""
from __future__ import annotations
import argparse, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import paho.mqtt.client as mqtt

def args():
    p=argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--duration', type=int, default=60)
    p.add_argument('--host', default='localhost')
    p.add_argument('--port', type=int, default=1883)
    p.add_argument('--user', default='collector')
    p.add_argument('--password', default=os.getenv('COLLECTOR_PASSWORD','collector-lab-pass'))
    p.add_argument('--topic', default='harpisense/#')
    p.add_argument('--output')
    return p.parse_args()

def main():
    a=args(); date=datetime.now().strftime('%Y-%m-%d')
    out=Path(a.output or f'evidence/{a.case}/{date}/observer.jsonl'); out.parent.mkdir(parents=True, exist_ok=True)
    def on_connect(client, userdata, flags, reason_code, properties):
        print(f'[observer] connected reason={reason_code}; subscribe={a.topic}')
        client.subscribe(a.topic)
    def on_message(client, userdata, msg):
        raw=msg.payload.decode('utf-8','replace')
        try: payload=json.loads(raw)
        except Exception: payload={'raw':raw}
        rec={'received_at':datetime.now(timezone.utc).isoformat(),'ground_truth':a.case,'topic':msg.topic,'qos':msg.qos,'payload':payload}
        with out.open('a',encoding='utf-8') as f: f.write(json.dumps(rec,ensure_ascii=False)+'\n')
        print(json.dumps(rec,ensure_ascii=False))
    c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f'collector-{a.case}-{int(time.time())}')
    c.username_pw_set(a.user,a.password); c.on_connect=on_connect; c.on_message=on_message
    c.connect(a.host,a.port,60); c.loop_start()
    try: time.sleep(a.duration)
    finally: c.loop_stop(); c.disconnect(); print(f'[observer] saved {out}')
if __name__=='__main__': main()
