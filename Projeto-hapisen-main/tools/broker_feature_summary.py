#!/usr/bin/env python3
"""Resumo simples de evidências do log Mosquitto para sessões de laboratório."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument('--log', default='broker/log/mosquitto.log'); p.add_argument('--tail', type=int, default=5000); a=p.parse_args()
    lines=Path(a.log).read_text(encoding='utf-8',errors='replace').splitlines()[-a.tail:]
    keys={
      'new_connections':'New connection from',
      'not_authorised':'not authorised',
      'denied_publish':'Denied PUBLISH',
      'denied_subscribe':'Denied SUBSCRIBE',
      'client_disconnects':'disconnected',
    }
    out={k:sum(1 for line in lines if needle.lower() in line.lower()) for k,needle in keys.items()}
    print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
