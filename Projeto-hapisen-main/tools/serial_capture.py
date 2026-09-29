#!/usr/bin/env python3
"""Captura serial do Wokwi por RFC2217. Requer pyserial."""
from __future__ import annotations
import argparse
from pathlib import Path
import serial

def main():
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,required=True); p.add_argument('--output',required=True); p.add_argument('--lines',type=int,default=100); a=p.parse_args()
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    ser=serial.serial_for_url(f'rfc2217://localhost:{a.port}',baudrate=115200,timeout=3)
    with out.open('w',encoding='utf-8') as f:
      for _ in range(a.lines):
        line=ser.readline().decode('utf-8','replace').rstrip(); print(line); f.write(line+'\n')
    ser.close()
if __name__=='__main__': main()
