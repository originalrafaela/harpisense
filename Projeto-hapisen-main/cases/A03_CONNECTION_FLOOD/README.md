# A03 — MQTT Connection Flood

**Data:** 2026-09-23  
**Nível:** MEDIUM  
**Categoria:** MQTT / disponibilidade

## Objetivo experimental
Volume anormal de conexões ao broker.

## Estrutura física no Wokwi
Este caso reutiliza o poste-base:

- ESP32 DevKit C v4
- Photoresistor Sensor/LDR: VCC -> 3V3, GND -> GND, AO -> GPIO34
- LED: GPIO2 -> resistor 1 kΩ -> anodo; catodo -> GND
- Serial Monitor ligado a TX/RX

Não adicione componentes quando o comportamento é de rede/MQTT. A diferença deste caso está no firmware, credenciais/ACL e padrão temporal.

## Arquivos
- `src/main.cpp`: firmware específico do caso
- `diagram.json`: circuito físico
- `platformio.ini`: build ESP32/Arduino + PubSubClient
- `wokwi.toml`: firmware PlatformIO + serial RFC2217 na porta 4103
- `case.json`: metadados do experimento
- `RESULT_TEMPLATE.md`: registro da rodada

## Pré-condições
1. Broker local ativo em `localhost:1883`.
2. `.env` criado na raiz a partir de `.env.example`.
3. Wokwi Private IoT Gateway funcionando; o firmware usa exclusivamente `host.wokwi.internal`.
4. Baseline NORMAL validado antes deste caso.

### Execução
1. Inicie o broker e, opcionalmente, zere/arquive o log anterior.
2. Build + Start Simulator.
3. O firmware executa **30 ciclos** de conexão/desconexão, com intervalo de 250 ms.
4. Observe `broker/log/mosquitto.log`.
5. Rode `python tools/broker_feature_summary.py`.

### Evidência esperada
Aumento concentrado de novas conexões e desconexões, sem necessidade de grande volume de publish.

## Features para o ML
**Indicadas/derivadas do cenário no documento:** `connections_per_second, packet_count, bytes_total, connection_failures`.

**Features de implementação propostas neste pacote:** `mqtt_connect_attempts, mqtt_connect_successes, mqtt_connect_failures`. As propostas adicionais devem ser documentadas como engenharia de features do grupo, não como texto literal da fonte.

## Comportamento esperado por modo operacional
- LOW: `REVIEW_REQUIRED`
- MEDIUM: `AUTO_POLICY`
- HARD: `AUTO_POLICY`

A decisão final deve continuar passando por confiança/anomaly score, histórico, whitelist e Risk/Policy Engine; o firmware do caso não executa firewall.

## Critérios de aceite
- Build sem erro no PlatformIO.
- Wokwi inicia e conecta ao Wi-Fi virtual.
- Conexão/alvo restritos ao broker local.
- Evidência no Serial e/ou `mosquitto.log` compatível com o objetivo do caso.
- Nenhum segredo real versionado.
- Evidência salva em diretório datado.
- Resultado registrado no `RESULT_TEMPLATE.md` (copiado para a pasta de evidência).

## Limites
Este caso é uma simulação acadêmica controlada. Os parâmetros têm limites explícitos para gerar padrão detectável sem transformar o laboratório em uma ferramenta de carga genérica.
