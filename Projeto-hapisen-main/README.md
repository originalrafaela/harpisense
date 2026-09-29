# HarpiSense — Pacote Experimental Wokwi/VS Code

**Versão:** 1.0  
**Data de consolidação:** 2026-09-23  
**Objetivo:** disponibilizar uma base versionável para GitHub com um cenário NORMAL e sete cenários A03–A09 do HarpiSense, cada um com firmware, circuito Wokwi, configuração PlatformIO, roteiro de execução, critérios de aceite e evidências esperadas.

## Escopo deste pacote

O pacote prioriza os cenários do documento que podem ser reproduzidos de forma consistente usando **ESP32 simulado + MQTT/Mosquitto local + VS Code/Wokwi**, sem depender de varredura de rede externa. Todos os firmwares apontam exclusivamente para `host.wokwi.internal:1883`, ou seja, o broker local acessado pelo Wokwi Private IoT Gateway.

Casos incluídos:

| Pasta | Cenário | Nível | Hardware |
|---|---|---|---|
| `00_BASELINE_NORMAL` | Operação legítima | referência | ESP32 + LDR + LED |
| `A03_CONNECTION_FLOOD` | MQTT Connection Flood | MEDIUM | mesmo hardware |
| `A04_PUBLISH_FLOOD` | MQTT Publish Flood | MEDIUM | mesmo hardware |
| `A05_AUTH_BRUTE_FORCE` | MQTT Authentication Brute Force | MEDIUM | mesmo hardware |
| `A06_UNAUTHORIZED_TOPIC` | Unauthorized Topic Access | HARD | mesmo hardware |
| `A07_WILDCARD_ABUSE` | MQTT Topic/Wildcard Abuse | HARD | mesmo hardware |
| `A08_DEVICE_IMPERSONATION` | Device Impersonation | HARD | mesmo hardware; segundo cliente legítimo opcional |
| `A09_TELEMETRY_ANOMALY` | IoT Behavioral/Telemetry Anomaly | HARD | mesmo hardware |

## Arquitetura do laboratório

```text
Wokwi/ESP32
   |
   | Wi-Fi virtual
   v
Wokwi Private IoT Gateway
   |
   v
host.wokwi.internal:1883
   |
   v
Mosquitto local (Docker/host)
   |
   +--> broker/log/mosquitto.log
   +--> tools/mqtt_observer.py
   |
   v
futuro HarpiSense Edge
features -> RF/Isolation Forest -> SHAP -> Risk/Policy -> nftables
```

## Pré-requisitos no VS Code

1. VS Code.
2. Extensão **PlatformIO IDE**.
3. Extensão **Wokwi Simulator** com licença ativada.
4. Docker Desktop **ou** Mosquitto 2.x instalado localmente.
5. Python 3.10+ para ferramentas auxiliares.
6. Wokwi Private IoT Gateway habilitado para acesso a `host.wokwi.internal`.

## Inicialização do broker local

1. Copie `.env.example` para `.env`.
2. Mantenha as senhas apenas como credenciais de laboratório.
3. Execute:

```bash
docker compose up -d
```

4. Verifique:

```bash
docker compose logs -f mosquitto
```

## Como executar qualquer caso

1. Abra **a pasta do caso** como workspace no VS Code.
2. Execute `PlatformIO: Build` ou `pio run`.
3. Confirme a geração de `.pio/build/esp32dev/firmware.bin` e `.elf`.
4. Abra `diagram.json`.
5. Inicie `Wokwi: Start Simulator`.
6. Confirme no Serial: Wi-Fi conectado e broker em `host.wokwi.internal:1883`.
7. Execute o observador na raiz do repositório:

```bash
python tools/mqtt_observer.py --case A04 --duration 60
```

8. Salve prints/terminal/logs em `evidence/<CASE>/<YYYY-MM-DD>/`.
9. Após o teste, preencha `RESULT_TEMPLATE.md` dentro da pasta do caso.

## Importante sobre "testado"

Este repositório contém **testes automatizados de estrutura/configuração**, executáveis com `python -m unittest discover -s tests -v`. A execução gráfica do Wokwi/VS Code depende da extensão e do toolchain instalados na sua máquina. O arquivo `VALIDATION_REPORT.md` separa explicitamente o que foi validado automaticamente do que deve receber evidência runtime no seu laboratório antes de marcar o caso como `PASS` no GitHub.

## Organização de evidências

Nunca sobrescreva uma evidência antiga. Use:

```text
evidence/A04/2026-09-23/
  serial.txt
  mosquitto.log
  observer.jsonl
  screenshot-wokwi.png
  RESULT.md
```

## Segurança experimental

Os cenários são deliberadamente limitados e apontam para um broker local. Não substitua `host.wokwi.internal` por infraestrutura de terceiros para ensaios de flood, autenticação ou autorização.
