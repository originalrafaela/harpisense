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
- A ingestao HTTP nao deve ficar desprotegida para resolver incompatibilidade entre areas.

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
- `message_id` e chave de idempotencia para telemetria; reenvios com o mesmo valor nao devem criar novo registro.
- `sequence` deve ser monotonico por dispositivo quando o produtor conseguir manter estado.
- `measurements` varia por `sensor_type`.
- Valores desconhecidos podem ser `null` ou omitidos; nao usar strings como `"N/A"`.
- `measurements` nao pode ser objeto vazio.
- Para o firmware atual do Poste 1, `temperature_c` e `humidity_pct` podem ser `null` ate sensor e pinagem serem aprovados.

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
  },
  "aggregation": {
    "window_seconds": 30,
    "window_start": "2026-09-15T22:30:00.000Z",
    "window_end": "2026-09-15T22:30:30.000Z",
    "first_observed_at": "2026-09-15T22:30:01.125Z",
    "last_observed_at": "2026-09-15T22:30:02.431Z",
    "packet_count": 4,
    "total_packet_size_bytes": 512,
    "interfaces_observed": ["eth-iot", "eth-test"],
    "expected_interfaces": ["eth-iot", "eth-test"],
    "traversal_verified": true,
    "traversal_reason": "same flow key observed on all configured gateway interfaces",
    "traversal_evidence": {
      "observed_interfaces": ["eth-iot", "eth-test"],
      "required_interfaces": ["eth-iot", "eth-test"],
      "flow_key": {
        "protocol": "tcp",
        "src_ip": "192.168.20.31",
        "src_port": 49152,
        "dst_ip": "192.168.30.20",
        "dst_port": 1883,
        "direction": "iot_to_test",
        "mqtt_message_type": "PUBLISH",
        "mqtt_topic": "harpisense/v1/telemetry/harpisense.poste.poste-1/environment"
      }
    }
  }
}
```

Regras:

- `event_id` deve ser unico.
- `event_id` e chave de idempotencia para eventos de rede; reenvios com o mesmo valor nao devem criar novo registro.
- `classification.stage` na primeira entrega deve ser `raw_capture`.
- `label` deve ser `unknown` enquanto nao houver ML treinado ou regra IDS validada.
- O gateway nao deve alterar payload de telemetria; ele registra metadados do trafego observado.
- Campos de metadados MQTT que nao estiverem visiveis na captura podem ser `null`.
- `classification.confidence` deve ser `null` na primeira entrega.
- A implementacao `edge-security` inclui um objeto adicional `aggregation` nos eventos agregados por janela.
- Decisao desta entrega: `aggregation` deve ser aceito, validado e persistido pelo backend como parte do `network_event`.
- O backend nao pode descartar `aggregation` silenciosamente. Se o objeto estiver presente e invalido, deve responder `422 Unprocessable Entity`.
- `aggregation` e opcional para eventos brutos sem agregacao. Quando presente, deve conter os campos do exemplo acima.
- `aggregation.packet_count`, `aggregation.total_packet_size_bytes` e `aggregation.window_seconds` devem ser inteiros positivos.
- `aggregation.window_start`, `aggregation.window_end`, `aggregation.first_observed_at` e `aggregation.last_observed_at` devem usar ISO 8601 UTC com sufixo `Z`.
- `aggregation.interfaces_observed` e `aggregation.expected_interfaces` devem ser listas de strings.
- `aggregation.traversal_verified` deve ser booleano.
- `aggregation.traversal_evidence.flow_key` deve refletir a chave usada pela Edge para agrupar o fluxo, sem incluir segredos.
- A exportacao offline `network_window` produzida por `edge.capture.offline_pcap` permanece artefato JSONL offline nesta entrega. Nao criar endpoint de ingestao de janelas nem persistir `network_window` na API enquanto nao houver contrato novo.

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
- Sucesso de ingestao deve responder `202 Accepted`.
- Reenvio idempotente deve responder `202 Accepted` com `duplicate: true`.
- Reutilizacao de identificador com conteudo diferente deve responder `409 Conflict` com `error.code = "identifier_conflict"`.
- Payload invalido deve responder `422 Unprocessable Entity`.
- Credencial ausente ou invalida deve responder `401 Unauthorized`.
- Senha administrativa nao configurada deve responder `503 Service Unavailable`.

### Idempotencia

Telemetria:

- Primeira persistencia valida: `202 Accepted`, `duplicate: false`.
- Reenvio do mesmo `message_id` com conteudo identico: `202 Accepted`, `duplicate: true`, sem criar novo registro.
- Reenvio do mesmo `message_id` com conteudo diferente: `409 Conflict`, `error.code = "identifier_conflict"`.
- Comparacao canonica de conteudo para `message_id`: `schema_version`, `message_id`, `device_id`, `observed_at`, `sensor_type`, `sequence`, `measurements` e `status`.
- Campos gerados pelo servidor ficam fora da comparacao: `id`, `received_at`, colunas derivadas, ordem fisica de armazenamento e metadados de banco.

Eventos de rede:

- Primeira persistencia valida: `202 Accepted`, `duplicate: false`.
- Reenvio do mesmo `event_id` com conteudo identico: `202 Accepted`, `duplicate: true`, sem criar novo registro.
- Reenvio do mesmo `event_id` com conteudo diferente: `409 Conflict`, `error.code = "identifier_conflict"`.
- Comparacao canonica de conteudo para `event_id`: `schema_version`, `event_id`, `event_type`, `observed_at`, `sensor_id`, `capture`, `mqtt`, `classification` e `aggregation` quando presente.
- Campos gerados pelo servidor ficam fora da comparacao: `id`, `received_at`, colunas de consulta derivadas de `capture` ou `mqtt`, ordem fisica de armazenamento e metadados de banco.
- Objetos JSON devem ser comparados apos validacao de schema, sem depender da ordem textual das chaves. Campo opcional omitido e campo opcional `null` devem ser normalizados de modo consistente pela implementacao antes da comparacao.

Exemplo de conflito:

```json
{
  "error": {
    "code": "identifier_conflict",
    "message": "event_id already exists with different content",
    "details": [
      {
        "field": "event_id"
      }
    ]
  }
}
```

## Autenticacao HTTP

Ha duas autenticacoes separadas:

- Autenticacao do administrador: protege consultas operacionais e futuras acoes administrativas.
- Autenticacao do gateway: protege ingestao HTTP feita pelo Edge Security.

Nao usar ingestao sem autenticacao como compatibilidade temporaria.

Estado das implementacoes lidas nas branches em 2026-09-17:

- `backend-data` implementa HTTP Basic administrativo em `backend/app/core/security.py`, com configuracao `HARPI_ADMIN_USERNAME` e `HARPI_ADMIN_PASSWORD`.
- `backend-data` ainda nao possui credencial separada para o gateway em `backend/app/core/config.py` ou dependencia especifica para `POST /api/v1/ingest/network-events`.
- `edge-security` implementa Bearer opcional em `edge/capture/backend_client.py`, carregado por `--backend-token-env` ou `--backend-token-file`.
- O Bearer da Edge nao e compativel com o backend atual e nao deve ser usado na integracao da primeira entrega sem contrato novo.
- A compatibilidade deve ser resolvida com HTTP Basic separado para o gateway, mantendo a ingestao protegida.

### Administrador unico

Implementacao existente em `backend-data`:

- `backend/app/core/security.py` usa HTTP Basic.
- `HARPI_ADMIN_USERNAME` define o usuario.
- `HARPI_ADMIN_PASSWORD` define a senha.
- `GET /api/v1/health` e publico.
- Os demais endpoints atuais exigem HTTP Basic.

Header:

```text
Authorization: Basic <base64(usuario:senha)>
```

Configuracao:

```text
HARPI_ADMIN_USERNAME=admin
HARPI_ADMIN_PASSWORD=<senha-local-nao-versionada>
```

Respostas esperadas:

| Situacao | Status | Observacao |
| --- | --- | --- |
| Credencial valida | `200`, `202` | Conforme endpoint |
| Credencial ausente ou invalida | `401` | Deve incluir `WWW-Authenticate: Basic` |
| Configuracao administrativa incompleta | `503` | `HARPI_ADMIN_PASSWORD` ausente ou invalido para endpoint protegido |
| Credencial de gateway em endpoint administrativo | `401` ou `403` | Gateway nao tem permissao administrativa |

### Gateway Edge Security

Contrato decidido para compatibilidade segura com a implementacao existente:

- O gateway deve usar credencial propria, separada da senha do administrador.
- O header contratado para o gateway sera HTTP Basic na primeira integracao, porque o backend existente so aceita Basic.
- Bearer opcional implementado em `edge-security` nao deve ser usado contra o backend atual ate haver suporte explicito no backend.
- A senha do gateway nao deve ser igual a `HARPI_ADMIN_PASSWORD`.

Header contratado:

```text
Authorization: Basic <base64(gateway_id:gateway_secret)>
```

Configuracao alvo no backend:

```text
HARPI_GATEWAY_USERNAME=harpisense.gateway.edge-1
HARPI_GATEWAY_PASSWORD=<senha-local-nao-versionada>
```

Configuracao alvo no Edge:

```text
HARPISENSE_BACKEND_USERNAME=harpisense.gateway.edge-1
HARPISENSE_BACKEND_PASSWORD=<senha-local-nao-versionada>
```

Endpoints autorizados para a credencial do gateway nesta entrega:

- `POST /api/v1/ingest/network-events`

Endpoints que continuam administrativos:

- `POST /api/v1/ingest/telemetry`
- `GET /api/v1/telemetry`
- `GET /api/v1/network-events`

Respostas esperadas para ingestao do gateway:

| Situacao | Status | Corpo esperado |
| --- | --- | --- |
| Evento aceito | `202` | `accepted: true`, `duplicate: false`, `id`, `received_at` |
| Evento repetido por `event_id` | `202` | `accepted: true`, `duplicate: true`, `id`, `received_at` |
| Mesmo `event_id` com conteudo diferente | `409` | `error.code: identifier_conflict` |
| Credencial ausente ou invalida | `401` | Erro de autenticacao |
| Payload invalido | `422` | Erro de validacao |
| Configuracao de gateway incompleta | `503` | `HARPI_GATEWAY_USERNAME` ou `HARPI_GATEWAY_PASSWORD` ausente/invalido |
| Gateway tentando consulta administrativa | `401` ou `403` | Acesso negado, sem dados operacionais |

Alteracoes necessarias por area:

- `backend-data`: adicionar configuracao `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`; aceitar Basic do gateway em `POST /api/v1/ingest/network-events`; manter Basic administrativo nos demais endpoints; nao aceitar Bearer sem contrato novo; manter `GET /api/v1/health` publico.
- `edge-security`: adicionar envio de HTTP Basic com usuario/senha do gateway; manter Bearer apenas como capacidade nao usada nesta integracao; atualizar exemplo de execucao para nao enviar sem credencial.
- `iot-mqtt`: sem mudanca HTTP; manter credenciais MQTT separadas de qualquer credencial HTTP.

Permissoes por endpoint:

| Metodo | Caminho | Publico | Administrador | Gateway |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/health` | Sim | Sim | Sim |
| `POST` | `/api/v1/ingest/telemetry` | Nao | Sim | Nao |
| `POST` | `/api/v1/ingest/network-events` | Nao | Opcional para teste local controlado | Sim |
| `GET` | `/api/v1/telemetry` | Nao | Sim | Nao |
| `GET` | `/api/v1/network-events` | Nao | Sim | Nao |

HTTP Basic codifica usuario e senha em Base64, mas nao cifra credenciais. Em laboratorio isolado pode ser usado sobre HTTP local/controlado; fora desse laboratorio, ou em qualquer rede compartilhada, deve rodar sobre HTTPS/TLS ou tunel equivalente. Senhas administrativas, de gateway e MQTT nao devem ser iguais entre si.

Checklist minimo antes da validacao integrada:

- Backend deve responder `401 Unauthorized` quando `POST /api/v1/ingest/network-events` chegar sem `Authorization`.
- Backend deve responder `401 Unauthorized` quando o Basic do gateway estiver incorreto.
- Backend deve responder `503 Service Unavailable` se `HARPI_GATEWAY_USERNAME` ou `HARPI_GATEWAY_PASSWORD` nao estiver configurado.
- Backend deve responder `202 Accepted` para evento valido com Basic do gateway.
- Backend deve responder `409 Conflict` para mesmo `event_id` ou `message_id` com conteudo diferente.
- Edge deve enviar `Authorization: Basic ...` quando receber usuario/senha do gateway.
- Edge nao deve enviar `Authorization: Bearer ...` contra o backend atual.

## Consumidor MQTT para persistencia

A area `backend-data` possui o consumidor responsavel por alimentar o banco a partir do broker:

```text
backend/app/mqtt/consumer.py
```

Execucao:

```powershell
$env:HARPI_MQTT_ENABLED="true"
python -m app.mqtt_worker
```

Regras de operacao:

- O consumidor assina `HARPI_MQTT_TELEMETRY_TOPIC`, padrao `harpisense/v1/telemetry/+/+`.
- O consumidor valida o payload com o mesmo schema de `POST /api/v1/ingest/telemetry`.
- O consumidor rejeita mensagem cujo topico nao combine com `device_id` e `sensor_type`.
- O consumidor persiste telemetria diretamente pelo servico backend, sem HTTP.
- Credenciais MQTT do consumidor devem usar usuario dedicado de leitura `harpisense_backend_consumer`.
- `harpisense_backend_consumer` deve ter permissao apenas de leitura/assinatura nos topicos de telemetria necessarios: `harpisense/v1/telemetry/#`.
- `harpisense_backend_consumer` nao deve publicar telemetria, nao deve ler topicos de seguranca e nao deve escrever em `harpisense/v1/security/#`.

Detalhes confirmados na implementacao:

- `backend/app/mqtt/consumer.py` cria cliente com `client_id="harpisense-backend-telemetry"`.
- Se `HARPI_MQTT_USERNAME` estiver configurado, o worker usa `username_pw_set(settings.mqtt_username, settings.mqtt_password)`.
- A persistencia chama `ingest_telemetry`, portanto a idempotencia por `message_id` tambem vale para mensagens consumidas do MQTT.
- A ACL atual de `iot-mqtt` possui `mqtt_test_subscriber` com leitura em `harpisense/v1/telemetry/#`; a area `iot-mqtt` deve adicionar `harpisense_backend_consumer` com a mesma leitura minima e sem permissao de escrita.

Correspondencia de configuracao MQTT:

| Uso | Variavel/arquivo | Valor de exemplo sem segredo real |
| --- | --- | --- |
| Usuario do consumidor backend | `HARPI_MQTT_USERNAME` | `harpisense_backend_consumer` |
| Senha do consumidor backend | `HARPI_MQTT_PASSWORD` | `<senha-mqtt-backend-consumer>` |
| Host do broker para o backend | `HARPI_MQTT_HOST` | `localhost` |
| Porta do broker para o backend | `HARPI_MQTT_PORT` | `1883` |
| Topico assinado pelo backend | `HARPI_MQTT_TELEMETRY_TOPIC` | `harpisense/v1/telemetry/+/+` |
| Provisionamento de usuario no broker | `mqtt/config/lab-users.example` ou arquivo local equivalente | `harpisense_backend_consumer:<senha-mqtt-backend-consumer>` |
| ACL do usuario no broker | `mqtt/config/aclfile` | `user harpisense_backend_consumer` + `topic read harpisense/v1/telemetry/#` |
| Geracao do password file | `mqtt/config/create-password-file.sh` | Entrada `username:password`; saida `mqtt/config/passwords` |

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
