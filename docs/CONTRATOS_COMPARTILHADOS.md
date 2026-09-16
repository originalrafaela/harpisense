# HarpiSense - Contratos compartilhados

Este documento define os contratos iniciais entre `iot-mqtt`, `edge-security` e `backend-data`. Alteracoes nestes contratos devem ser centralizadas pelo responsavel de integracao antes de serem aplicadas nas worktrees.

## Convencoes gerais

- Todos os timestamps devem usar ISO 8601 em UTC, com sufixo `Z`.
- Campo canonico: `observed_at`.
- Timestamps gerados por produtores devem representar o momento da observacao.
- Timestamps gerados pelo backend devem usar `received_at`.
- Identificadores devem ser estaveis, em ASCII minusculo, com hifen quando necessario.
- Payloads MQTT e payloads HTTP devem ser JSON UTF-8.
- Payloads nao devem incluir senhas, tokens, chaves privadas ou conteudo sensivel desnecessario.
- Telemetria de sensores e eventos de seguranca sao fluxos separados.

## Identificacao de dispositivos

Formato canonico:

```text
harpisense.<tipo>.<id>
```

Tipos iniciais:

- `poste`: poste fisico ou simulado.
- `gateway`: gateway IDS/IPS.
- `broker`: broker MQTT.

Dispositivos iniciais:

| device_id | Tipo | Origem | Descricao |
| --- | --- | --- | --- |
| `harpisense.poste.poste-1` | `poste` | ESP32 fisico | Poste 1 da demonstracao inicial |
| `harpisense.poste.poste-2` | `poste` | Simulado | Poste simulado |
| `harpisense.poste.poste-3` | `poste` | Simulado | Poste simulado |
| `harpisense.gateway.edge-1` | `gateway` | VM ou host gateway | Gateway de captura entre zonas |
| `harpisense.broker.mqtt-1` | `broker` | Mosquitto | Broker MQTT do laboratorio |

## Topicos MQTT de telemetria

Base:

```text
harpisense/v1/telemetry/<device_id>/<sensor_type>
```

Topicos iniciais:

| Topico | Produtor | Uso |
| --- | --- | --- |
| `harpisense/v1/telemetry/harpisense.poste.poste-1/environment` | ESP32 | Temperatura e umidade do poste fisico |
| `harpisense/v1/telemetry/harpisense.poste.poste-1/power` | ESP32 | Tensao, corrente e potencia quando disponivel |
| `harpisense/v1/telemetry/harpisense.poste.poste-2/environment` | Simulador | Temperatura e umidade simuladas |
| `harpisense/v1/telemetry/harpisense.poste.poste-3/environment` | Simulador | Temperatura e umidade simuladas |

Payload de telemetria:

```json
{
  "schema_version": "1.0",
  "message_id": "01J00000000000000000000000",
  "device_id": "harpisense.poste.poste-1",
  "observed_at": "2026-09-15T22:30:00.000Z",
  "sensor_type": "environment",
  "sequence": 42,
  "measurements": {
    "temperature_c": 24.6,
    "humidity_pct": 62.1
  },
  "status": {
    "battery_pct": null,
    "rssi_dbm": -61
  }
}
```

Regras:

- `message_id` deve ser unico por mensagem.
- `sequence` deve ser monotonico por dispositivo quando o produtor conseguir manter estado.
- `measurements` varia por `sensor_type`.
- Valores desconhecidos devem ser `null` ou omitidos; nao usar strings como `"N/A"`.

## Topicos MQTT de eventos de seguranca

Eventos de seguranca nao devem ser publicados nos topicos de telemetria.

Base:

```text
harpisense/v1/security/<event_type>
```

Topicos iniciais:

| Topico | Produtor | Uso |
| --- | --- | --- |
| `harpisense/v1/security/network-event` | Gateway | Evento de rede capturado ou agregado |
| `harpisense/v1/security/mqtt-auth-event` | Broker/exportador | Resultado de autenticacao MQTT sem senha |
| `harpisense/v1/security/ids-alert` | Edge Security | Alerta IDS sem bloqueio |
| `harpisense/v1/security/block-request` | Edge Security | Recomendacao futura de bloqueio supervisionado |
| `harpisense/v1/security/block-decision` | Backend/Admin | Aprovacao, rejeicao ou expiracao futura |

Na primeira entrega, apenas `network-event` precisa ser produzido pelo gateway e persistido pelo backend. `ids-alert`, `block-request` e `block-decision` ficam contratados para etapas posteriores.

## Evento de rede

Payload canonico para ingestao e persistencia:

```json
{
  "schema_version": "1.0",
  "event_id": "01J00000000000000000000001",
  "event_type": "network_event",
  "observed_at": "2026-09-15T22:30:01.125Z",
  "sensor_id": "harpisense.gateway.edge-1",
  "capture": {
    "interface": "eth1",
    "direction": "iot_to_test",
    "protocol": "tcp",
    "src_ip": "192.168.20.31",
    "src_port": 49152,
    "dst_ip": "192.168.20.20",
    "dst_port": 1883,
    "packet_size_bytes": 128,
    "tcp_flags": "PA"
  },
  "mqtt": {
    "present": true,
    "message_type": "PUBLISH",
    "topic": "harpisense/v1/telemetry/harpisense.poste.poste-1/environment",
    "client_id": "poste-1"
  },
  "classification": {
    "stage": "raw_capture",
    "label": "unknown",
    "confidence": null
  }
}
```

Regras:

- `event_id` deve ser unico.
- `classification.stage` na primeira entrega deve ser `raw_capture`.
- `label` deve ser `unknown` enquanto nao houver ML treinado ou regra IDS validada.
- O gateway nao deve alterar payload de telemetria; ele registra metadados do trafego observado.

## Evento de autenticacao MQTT

Contrato para etapa posterior:

```json
{
  "schema_version": "1.0",
  "event_id": "01J00000000000000000000002",
  "event_type": "mqtt_auth_event",
  "observed_at": "2026-09-15T22:31:00.000Z",
  "broker_id": "harpisense.broker.mqtt-1",
  "client_id": "poste-1",
  "username": "iot_device_lab",
  "src_ip": "192.168.20.31",
  "result": "success",
  "reason": null
}
```

Regras:

- Nunca registrar senha tentada.
- `result` deve ser `success` ou `failure`.
- `reason` deve usar texto tecnico curto quando disponivel, sem segredo.

## Interface de ingestao do backend

Base HTTP inicial:

```text
/api/v1/ingest
```

Endpoints contratados:

| Metodo | Caminho | Produtor | Status esperado |
| --- | --- | --- | --- |
| `POST` | `/api/v1/ingest/telemetry` | MQTT subscriber ou simulador autorizado | `202 Accepted` |
| `POST` | `/api/v1/ingest/network-events` | Gateway Edge Security | `202 Accepted` |
| `GET` | `/api/v1/telemetry` | Cliente/API test | `200 OK` |
| `GET` | `/api/v1/network-events` | Cliente/API test | `200 OK` |
| `GET` | `/api/v1/health` | Operacao/testes | `200 OK` |

Envelope de erro:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid payload",
    "details": []
  }
}
```

Regras:

- Ingestao deve validar `schema_version`, identificadores obrigatorios e timestamps.
- O backend deve adicionar `received_at`.
- Persistencia inicial pode ser banco local ou armazenamento simples definido pela area `backend-data`, desde que a API consiga persistir e consultar.
- Contratos devem permanecer independentes do dashboard.

## Consulta minima da primeira entrega

`GET /api/v1/telemetry` deve permitir, no minimo:

- filtrar por `device_id`;
- filtrar por intervalo `observed_from` e `observed_to`;
- limitar quantidade com `limit`.

`GET /api/v1/network-events` deve permitir, no minimo:

- filtrar por `src_ip`;
- filtrar por `dst_ip`;
- filtrar por `dst_port`;
- filtrar por intervalo `observed_from` e `observed_to`;
- limitar quantidade com `limit`.
