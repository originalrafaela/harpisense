# 00 — Baseline NORMAL

**Data:** 2026-09-23

## Objetivo
Validar circuito, Wi-Fi, autenticação MQTT e telemetria legítima antes dos ataques.

## Hardware
ESP32 DevKit C v4 + LDR (AO -> GPIO34) + LED (GPIO2 através de 1 kΩ) + GND/3V3 conforme `diagram.json`.

## Procedimento
1. Suba o Mosquitto local pela raiz do repositório.
2. Abra esta pasta no VS Code.
3. Build com PlatformIO.
4. Abra `diagram.json` e inicie Wokwi.
5. Mude o LDR e confirme mudança de `luminosity` e LED.
6. Em outro terminal, execute `python tools/mqtt_observer.py --case NORMAL --duration 60` a partir da raiz.

## Aceite
- Conexão MQTT persistente.
- Aproximadamente 1 publish/s.
- `device_id=poste-01`.
- luminosidade acompanha LDR.
- nenhuma negação de ACL no broker.
