# A05 — MQTT Authentication Brute Force

**Data:** 2026-09-23  
**Nível:** MEDIUM  
**Categoria:** Autenticação

## Objetivo experimental
Múltiplas falhas de autenticação em janela curta.

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
- `wokwi.toml`: firmware PlatformIO + serial RFC2217 na porta 4105
- `case.json`: metadados do experimento
- `RESULT_TEMPLATE.md`: registro da rodada

## Pré-condições
1. Broker local ativo em `localhost:1883`.
2. `.env` criado na raiz a partir de `.env.example`.
3. Wokwi Private IoT Gateway funcionando; o firmware usa exclusivamente `host.wokwi.internal`.
4. Baseline NORMAL validado antes deste caso.

### Execução
1. Inicie o broker.
2. Build + Start Simulator.
3. O firmware realiza **6 autenticações inválidas**, espaçadas em 700 ms, contra a conta `test_auth`.
4. Em seguida realiza **1 autenticação válida de controle**.
5. Confira o log do broker; não persista as senhas tentadas no dataset.

### Evidência esperada
Falhas de autenticação concentradas e um sucesso final de controle.

## Features para o ML
**Indicadas/derivadas do cenário no documento:** `auth_failures, auth_successes, mean_interarrival_ms`.

**Features de implementação propostas neste pacote:** `auth_failures, auth_successes, attempt_interval_ms`. As propostas adicionais devem ser documentadas como engenharia de features do grupo, não como texto literal da fonte.

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
