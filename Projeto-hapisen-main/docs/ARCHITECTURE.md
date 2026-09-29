# Arquitetura experimental — HarpiSense cases A03–A09

Data: 2026-09-23

A unidade física é o poste-base: ESP32 DevKit C v4, LDR no GPIO34, LED no GPIO2 e resistor de 1 kΩ. O MQTT usa Mosquitto local em TCP/1883. O Wokwi acessa o host por `host.wokwi.internal`.

O fluxo experimental separa **ground truth** da telemetria: o firmware não envia o label do ataque. O `mqtt_observer.py` recebe `--case A0X` e registra o rótulo externamente. Isso evita vazamento direto da classe para o futuro modelo.

```text
ESP32/Wokwi -> Mosquitto -> logs/payloads -> agregação em janelas -> dataset -> RF/Isolation Forest
                                                        |
                                                        -> SHAP -> Risk/Policy -> nftables
```

## Modos operacionais

- LOW: A03–A09 ficam fora da autonomia A01–A02; portanto exigem revisão humana.
- MEDIUM: A03–A05 entram na autonomia automática; A06–A09 exigem revisão.
- HARD: A03–A09 entram na autonomia automática conforme política, whitelist e thresholds.
