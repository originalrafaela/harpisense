# A08 — Device Impersonation

**Data:** 2026-09-23  
**Nível:** HARD  
**Categoria:** IoT / identidade

## Objetivo experimental
Tentativa de se apresentar como um poste/dispositivo legítimo.

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
- `wokwi.toml`: firmware PlatformIO + serial RFC2217 na porta 4108
- `case.json`: metadados do experimento
- `RESULT_TEMPLATE.md`: registro da rodada

## Pré-condições
1. Broker local ativo em `localhost:1883`.
2. `.env` criado na raiz a partir de `.env.example`.
3. Wokwi Private IoT Gateway funcionando; o firmware usa exclusivamente `host.wokwi.internal`.
4. Baseline NORMAL validado antes deste caso.

### Execução
1. Inicie broker e observador: `python tools/mqtt_observer.py --case A08 --duration 60`.
2. Build + Start Simulator.
3. O cliente autentica como principal `poste02`, usa client ID `harpisense-poste-01-clone` e declara no payload `device_id=poste-01`.
4. O tópico continua sendo o permitido a `poste02`: `.../poste-02/telemetry`.
5. Correlacione broker log + tópico + payload.

### Evidência esperada
Mismatch verificável entre principal autenticado/tópico e identidade declarada. Para demonstração mais forte, rode o baseline NORMAL em outra instância como poste-01 legítimo.

## Features para o ML
**Indicadas/derivadas do cenário no documento:** `origem, client_id, histórico, frequência, perfil esperado`.

**Features de implementação propostas neste pacote:** `authenticated_principal, mqtt_client_id, declared_device_id, topic_device_id, identity_mismatch`. As propostas adicionais devem ser documentadas como engenharia de features do grupo, não como texto literal da fonte.

## Comportamento esperado por modo operacional
- LOW: `REVIEW_REQUIRED`
- MEDIUM: `REVIEW_REQUIRED`
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
