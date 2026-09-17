# HarpiSense - Roteiro unico de integracao da primeira entrega

Este roteiro consolida as implementacoes encontradas nas branches `iot-mqtt`, `edge-security` e `backend-data`. Ele prepara a integracao, mas nao declara validacao real. Nao fazer merge das branches nem editar arquivos das areas durante esta rodada.

## Branches lidas

| Area | Branch | Commit lido | Observacao |
| --- | --- | --- | --- |
| `iot-mqtt` | `iot-mqtt` | `5cf116f` | Mosquitto, simulador, firmware ESP32, smoke test MQTT e progresso da area |
| `edge-security` | `edge-security` | `97c4e5a` | Captura Scapy, agregacao, envio HTTP de `network_event` e progresso da area |
| `backend-data` | `backend-data` | `1607ff8` | FastAPI, PostgreSQL, Alembic, schemas, API, consumidor MQTT e progresso da area |

Commits de implementacao base lidos:

- `iot-mqtt`: `c7aa9e0 Add IoT MQTT lab delivery`.
- `edge-security`: `7af8360 Implement edge traffic capture pipeline` e `dd2f074 Add backend delivery handling for network events`.
- `backend-data`: `5a05547 Implement backend ingestion base`.

## Premissas mantidas

- BitNet local fica fora do caminho critico e sera usado apenas para explicar incidentes em etapa posterior.
- O sistema tem administrador unico.
- Modos IDS, IPS supervisionado e IPS autonomo continuam definidos em `docs/DECISOES_ARQUITETURAIS.md`.
- Esta entrega nao valida ML, bloqueio real, dashboard completo, AWS ou BitNet.
- Ingestao HTTP nao deve ficar sem autenticacao.
- Telemetria MQTT e eventos de seguranca continuam fluxos separados.
- `observed_at` vem do produtor ou da observacao; `received_at` vem do backend.
- `message_id` e chave de idempotencia para telemetria; `event_id` e chave de idempotencia para eventos de rede.
- Valores desconhecidos podem ser `null` ou omitidos, mas `measurements` nao pode ser objeto vazio.
- Reenvio identico deve retornar `202 Accepted` com `duplicate: true`; identificador reutilizado com conteudo diferente deve retornar `409 Conflict` com `error.code = "identifier_conflict"`.
- `aggregation` em `network_event` deve ser aceito, validado e persistido. Descarte silencioso nao e permitido.
- `network_window` gerado pelo processamento offline de PCAP permanece exportacao JSONL offline nesta entrega, sem endpoint de ingestao.

## Contrato de autenticacao para a integracao

### Administrador

- Uso: consultas operacionais e ingestao administrativa de telemetria por HTTP.
- Header: `Authorization: Basic <base64(usuario:senha)>`.
- Backend existente: `backend/app/core/security.py`.
- Configuracao existente:

```text
HARPI_ADMIN_USERNAME=admin
HARPI_ADMIN_PASSWORD=<senha-local-nao-versionada>
```

- `GET /api/v1/health` permanece publico.
- Endpoints administrativos continuam exigindo Basic administrativo:
  - `POST /api/v1/ingest/telemetry`
  - `GET /api/v1/telemetry`
  - `GET /api/v1/network-events`
- A credencial do gateway nao pode acessar consultas administrativas.

### Gateway

- Uso: ingestao de eventos do gateway em `POST /api/v1/ingest/network-events`.
- Header contratado: `Authorization: Basic <base64(gateway_id:gateway_secret)>`.
- Configuracao alvo no backend:

```text
HARPI_GATEWAY_USERNAME=harpisense.gateway.edge-1
HARPI_GATEWAY_PASSWORD=<senha-local-nao-versionada>
```

- Configuracao alvo na Edge:

```text
HARPISENSE_BACKEND_USERNAME=harpisense.gateway.edge-1
HARPISENSE_BACKEND_PASSWORD=<senha-local-nao-versionada>
```

- Respostas esperadas:
  - Evento valido com Basic do gateway: `202 Accepted`.
  - Evento repetido por `event_id`: `202 Accepted` com `duplicate: true`.
  - Mesmo `event_id` com conteudo diferente: `409 Conflict` com `error.code = "identifier_conflict"`.
  - Credencial ausente ou invalida: `401 Unauthorized`.
  - Payload invalido: `422 Unprocessable Entity`.
  - `HARPI_GATEWAY_USERNAME` ou `HARPI_GATEWAY_PASSWORD` ausente/invalido: `503 Service Unavailable`.
  - Gateway tentando `GET /api/v1/telemetry` ou `GET /api/v1/network-events`: `401 Unauthorized` ou `403 Forbidden`.

HTTP Basic usa Base64 e nao cifra credenciais. No laboratorio isolado pode rodar em HTTP local/controlado; fora dele deve usar HTTPS/TLS ou tunel equivalente.

Estado atual a corrigir antes da validacao:

- `backend-data` ainda aceita apenas Basic administrativo.
- `edge-security` ainda envia somente Bearer opcional quando configurado.
- Bearer nao deve ser usado contra o backend atual.
- A ingestao nao deve ser aberta sem autenticacao para contornar essa incompatibilidade.
- `backend-data` ja possui tratamento de `409 identifier_conflict` para identificadores reutilizados com conteudo diferente, mas ainda precisa aplicar a credencial de gateway separada.

## Ordem de inicializacao

Os comandos abaixo usam caminhos reais encontrados nas branches. Ajustar senhas, IPs e nomes de interface localmente antes da validacao real.

### 1. PostgreSQL

Branch/caminho: `backend-data:backend/docker-compose.yml`

```powershell
cd backend
docker compose up -d postgres
```

Dependencias:

- Docker com Compose.
- Porta local `5432` livre ou ajuste de compose.

### 2. API backend

Branch/caminho: `backend-data:backend/README.md`

```powershell
cd backend
Copy-Item .env.example .env
# Editar .env:
# HARPI_ADMIN_USERNAME=admin
# HARPI_ADMIN_PASSWORD=<senha-local-nao-versionada>
# HARPI_GATEWAY_USERNAME=harpisense.gateway.edge-1
# HARPI_GATEWAY_PASSWORD=<senha-local-nao-versionada>

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Estado atual:

- A API existente aceita HTTP Basic administrativo.
- `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD` ainda precisam ser implementados em `backend-data`.
- Enquanto isso nao for implementado, Edge nao conseguira autenticar com credencial propria no contrato decidido.
- Nao usar a senha administrativa como senha do gateway.

Health esperado:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/health"
```

### 3. Mosquitto

Branch/caminho: `iot-mqtt:mqtt/docker-compose.yml`

```powershell
cd mqtt
docker compose --profile init run --rm mosquitto-init
docker compose up -d mosquitto
```

Configuracao encontrada:

- `mqtt/config/mosquitto.conf`
- `mqtt/config/aclfile`
- `mqtt/config/lab-users.example`

Usuarios MQTT existentes:

- `iot_device_lab`: publica telemetria usando client id `poste-1`, `poste-2` ou `poste-3`.
- `mqtt_test_subscriber`: le `harpisense/v1/telemetry/#`.
- `mqtt_auth_exporter`: reservado para futuro `mqtt-auth-event`.

Usuario MQTT decidido para o backend:

- Adicionar `harpisense_backend_consumer:<senha-mqtt-backend-consumer>` ao arquivo local de usuarios usado por `mqtt/config/create-password-file.sh`.
- Adicionar no `mqtt/config/aclfile`:

```text
user harpisense_backend_consumer
topic read harpisense/v1/telemetry/#
```

- `harpisense_backend_consumer` nao deve ter permissao de publicacao nem acesso a `harpisense/v1/security/#`.

Dependencias:

- Docker com Compose.
- Arquivo local `mqtt/config/passwords` gerado e nao versionado.
- Senhas reais de laboratorio substituindo exemplos antes de rede real.

### 4. Consumidor MQTT do backend

Branch/caminho: `backend-data:backend/app/mqtt_worker.py`

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:HARPI_MQTT_ENABLED="true"
$env:HARPI_MQTT_HOST="localhost"
$env:HARPI_MQTT_PORT="1883"
$env:HARPI_MQTT_USERNAME="harpisense_backend_consumer"
$env:HARPI_MQTT_PASSWORD="<senha-mqtt-backend-consumer>"
$env:HARPI_MQTT_TELEMETRY_TOPIC="harpisense/v1/telemetry/+/+"
python -m app.mqtt_worker
```

Responsabilidade:

- Consumir telemetria MQTT.
- Validar topico contra `device_id` e `sensor_type`.
- Persistir no banco usando `backend/app/mqtt/consumer.py`.
- Usar `ingest_telemetry`, mantendo idempotencia por `message_id`.
- Retornar/registrar conflito de idempotencia quando `message_id` for reutilizado com conteudo diferente.

Correspondencia com o broker:

- `HARPI_MQTT_USERNAME` deve corresponder ao usuario `harpisense_backend_consumer` provisionado no Mosquitto.
- `HARPI_MQTT_PASSWORD` deve corresponder a senha local desse usuario no password file.
- `HARPI_MQTT_TELEMETRY_TOPIC` deve ficar dentro da ACL `topic read harpisense/v1/telemetry/#`.

### 5. Simulador MQTT

Branch/caminho: `iot-mqtt:lab/legitimate-traffic/simulate_poste.py`

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r lab\legitimate-traffic\requirements.txt

$env:MQTT_HOST="127.0.0.1"
$env:MQTT_PORT="1883"
$env:MQTT_USERNAME="iot_device_lab"
$env:MQTT_PASSWORD="<senha-mqtt-publicacao>"
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --device poste-2 --count 3 --interval 1
```

Topicos publicados:

- `harpisense/v1/telemetry/harpisense.poste.poste-2/environment`
- `harpisense/v1/telemetry/harpisense.poste.poste-3/environment`

Contrato observado:

- `message_id` gerado com UUID hexadecimal.
- `observed_at` em UTC com sufixo `Z`.
- `status.battery_pct` pode ser `null`.
- O simulador sintetico atual pode publicar multiplos postes com `--devices`, `--post-count`, `--duration`, `--seed` e tambem gerar JSONL local com `--jsonl`.

### 6. Poste 1 ESP32

Branch/caminho: `iot-mqtt:iot/esp32/poste1`

```powershell
cd iot\esp32\poste1
Copy-Item include\config.example.h include\config.h
# Editar WIFI_SSID, WIFI_PASSWORD, MQTT_HOST, MQTT_USERNAME, MQTT_PASSWORD.
pio run
pio run --target upload
pio device monitor
```

Dependencias ainda ausentes:

- Modelo de sensor fisico.
- Pinagem aprovada.
- Confirmacao de sincronizacao NTP no ambiente do ESP32.

Observacao:

- A implementacao atual publica `temperature_c` e `humidity_pct` como `null` enquanto sensor e pinagem nao forem definidos.
- Se NTP falhar, o firmware usa `1970-01-01T00:00:00.000Z`; isso passa no formato, mas deve ser tratado como evidencia temporal invalida na validacao real.

### 7. Edge Security

Branch/caminho: `edge-security:edge/capture/scapy_gateway.py`

No gateway Linux:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv tcpdump
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r edge/requirements.txt
ip -brief address
ip route
```

Execucao alvo, depois que `edge-security` implementar HTTP Basic do gateway:

```bash
export HARPISENSE_BACKEND_USERNAME='harpisense.gateway.edge-1'
export HARPISENSE_BACKEND_PASSWORD='<senha-local-nao-versionada>'
sudo --preserve-env=HARPISENSE_BACKEND_USERNAME,HARPISENSE_BACKEND_PASSWORD .venv/bin/python -m edge.capture.scapy_gateway \
  --iface eth-iot \
  --iface eth-test \
  --iot-cidr 192.168.20.0/24 \
  --test-cidr 192.168.30.0/24 \
  --broker-host 192.168.30.20 \
  --mqtt-port 1883 \
  --window-seconds 30 \
  --backend-url http://127.0.0.1:8000/api/v1/ingest/network-events \
  --backend-timeout-seconds 5 \
  --output-jsonl edge/capture/network-events.jsonl \
  --delivery-jsonl edge/capture/network-event-delivery.jsonl \
  --duration-seconds 120
```

Estado atual:

- O comando real existente aceita `--backend-token-env` e `--backend-token-file` para Bearer opcional.
- Nao existe opcao atual para HTTP Basic.
- Nao executar sem credencial contra a API real.
- Nao usar Bearer contra o backend atual, pois `backend-data` so aceita Basic.
- Apos a correcao, a Edge deve montar `Authorization: Basic ...` a partir de `HARPISENSE_BACKEND_USERNAME` e `HARPISENSE_BACKEND_PASSWORD`.

Verificacoes locais depois da execucao:

```bash
tail -n 5 edge/capture/network-events.jsonl
tail -n 5 edge/capture/network-event-delivery.jsonl
```

Tratamento do payload:

- `network_event` enviado ao backend deve manter `event_type: network_event`.
- Se `aggregation` estiver presente, o backend deve validar e persistir esse objeto junto do evento.
- Reenvio com mesmo `event_id` e mesmo conteudo deve resultar em `duplicate: true`.
- Reenvio com mesmo `event_id` e conteudo diferente deve resultar em `409 identifier_conflict`.
- `network_window` emitido por `edge.capture.offline_pcap` fica em JSONL offline e nao deve ser enviado a `/api/v1/ingest/network-events` nesta entrega.

### 8. Consulta pela API

Depois de telemetria e eventos persistidos, consultar com Basic administrativo:

```powershell
$pair = "admin:<senha-admin-local>"
$token = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$headers = @{ Authorization = "Basic $token" }

Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/telemetry?limit=10" -Headers $headers
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/network-events?dst_port=1883&limit=10" -Headers $headers
```

Confirmacao negativa de permissao do gateway:

```powershell
$gatewayPair = "harpisense.gateway.edge-1:<senha-gateway-local>"
$gatewayToken = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($gatewayPair))
$gatewayHeaders = @{ Authorization = "Basic $gatewayToken" }

# Deve retornar 401 ou 403; o gateway nao consulta dados administrativos.
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/network-events?limit=10" -Headers $gatewayHeaders
```

## Incompatibilidades a corrigir antes da validacao real

| Area | Correcao necessaria |
| --- | --- |
| `backend-data` | Implementar credencial Basic separada para gateway em `POST /api/v1/ingest/network-events`, com `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`; negar consultas administrativas ao gateway. |
| `edge-security` | Implementar envio de `Authorization: Basic ...` com usuario/senha do gateway; remover exemplos sem credencial para integracao real; nao usar Bearer contra o backend atual. |
| `backend-data` | Aceitar, validar e persistir `aggregation` enviado pelo Edge em `network_event`; rejeitar com `422` se presente e invalido; nao descartar silenciosamente. |
| `edge-security` | Manter `network_window` como exportacao offline JSONL; nao enviar `network_window` para a API nesta entrega. |
| `iot-mqtt` | Criar usuario MQTT dedicado `harpisense_backend_consumer` com permissao somente de leitura em `harpisense/v1/telemetry/#`. |
| `iot-mqtt` | Definir sensor fisico e pinagem do ESP32 para substituir `temperature_c` e `humidity_pct` nulos quando houver hardware. |
| `iot-mqtt` | Validar sincronizacao de hora do ESP32 antes de aceitar evidencias com `observed_at`. |
| `edge-security` | Confirmar nomes reais das interfaces e CIDRs; duas interfaces configuradas nao provam travessia se o fluxo nao aparecer em ambas. |

## Validacoes que continuam pendentes

- Subir PostgreSQL e aplicar Alembic em banco real.
- Subir API backend e verificar Basic administrativo.
- Validar Basic separado do gateway depois da implementacao nas duas areas.
- Subir Mosquitto com `mqtt/config/passwords` local gerado.
- Rodar simulador e confirmar recebimento no broker.
- Rodar consumidor MQTT do backend e consultar telemetria persistida.
- Rodar Edge em gateway Linux inline e confirmar eventos em `edge/capture/network-events.jsonl`.
- Confirmar entrega de eventos da Edge para o backend e consulta em `GET /api/v1/network-events`.
- Registrar evidencias em `docs/evidence/` somente depois de execucao real.

## Dependencias ainda ausentes

- Merge futuro das branches em uma base comum.
- Senhas locais nao versionadas para HTTP Basic administrativo e gateway.
- Suporte de Basic gateway na Edge e no Backend.
- Usuario MQTT de leitura dedicado para o worker, se aprovado.
- Hardware ESP32 conectado, rede Wi-Fi de laboratorio e sensor/pinagem aprovados.
- Gateway Linux inline com duas interfaces ou arranjo equivalente.
- Confirmacao de IP do broker e CIDRs reais da topologia.
- Validacao real ponta a ponta e evidencias em `docs/evidence/`.
