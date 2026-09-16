# HarpiSense - Roteiro unico de integracao da primeira entrega

Este roteiro consolida as implementacoes encontradas nas branches `iot-mqtt`, `edge-security` e `backend-data` em 2026-09-16. Ele prepara a integracao, mas nao declara validacao real. Nao fazer merge das branches nem editar arquivos das areas durante esta rodada.

## Branches lidas

| Area | Branch | Commit lido | Observacao |
| --- | --- | --- | --- |
| `iot-mqtt` | `iot-mqtt` | `c7aa9e0` | Mosquitto, simulador, firmware ESP32 e smoke test MQTT |
| `edge-security` | `edge-security` | `dd2f074` | Captura Scapy, agregacao e envio HTTP de `network_event` |
| `backend-data` | `backend-data` | `5a05547` | FastAPI, PostgreSQL, Alembic, schemas, API e consumidor MQTT |

## Premissas mantidas

- BitNet local fica fora do caminho critico e sera usado apenas para explicar incidentes em etapa posterior.
- O sistema tem administrador unico.
- Modos IDS, IPS supervisionado e IPS autonomo continuam definidos em `docs/DECISOES_ARQUITETURAIS.md`.
- Esta entrega nao valida ML, bloqueio real, dashboard completo, AWS ou BitNet.
- Ingestao HTTP nao deve ficar sem autenticacao.

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
$env:HARPI_MQTT_USERNAME="mqtt_test_subscriber"
$env:HARPI_MQTT_PASSWORD="<senha-mqtt-leitura>"
$env:HARPI_MQTT_TELEMETRY_TOPIC="harpisense/v1/telemetry/+/+"
python -m app.mqtt_worker
```

Responsabilidade:

- Consumir telemetria MQTT.
- Validar topico contra `device_id` e `sensor_type`.
- Persistir no banco usando `backend/app/mqtt/consumer.py`.

Pendencia recomendada:

- Criar usuario MQTT dedicado `harpisense_backend_consumer` com permissao de leitura em `harpisense/v1/telemetry/#`, ou documentar que `mqtt_test_subscriber` sera usado temporariamente na primeira validacao.

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

Verificacoes locais depois da execucao:

```bash
tail -n 5 edge/capture/network-events.jsonl
tail -n 5 edge/capture/network-event-delivery.jsonl
```

### 8. Consulta pela API

Depois de telemetria e eventos persistidos, consultar com Basic administrativo:

```powershell
$pair = "admin:<senha-admin-local>"
$token = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$headers = @{ Authorization = "Basic $token" }

Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/telemetry?limit=10" -Headers $headers
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/network-events?dst_port=1883&limit=10" -Headers $headers
```

## Incompatibilidades a corrigir antes da validacao real

| Area | Correcao necessaria |
| --- | --- |
| `backend-data` | Implementar credencial Basic separada para gateway em `POST /api/v1/ingest/network-events`, com `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`. |
| `edge-security` | Implementar envio de `Authorization: Basic ...` com usuario/senha do gateway; remover exemplos sem credencial para integracao real. |
| `backend-data` | Decidir e implementar tratamento de `aggregation` enviado pelo Edge: persistir como JSON ou rejeitar explicitamente; evitar ignorar silenciosamente na integracao validada. |
| `iot-mqtt` | Definir se o consumidor backend usara `mqtt_test_subscriber` temporariamente ou um novo usuario MQTT dedicado de leitura. |
| `iot-mqtt` | Definir sensor fisico e pinagem do ESP32 para substituir `temperature_c` e `humidity_pct` nulos quando houver hardware. |
| `iot-mqtt` | Validar sincronizacao de hora do ESP32 antes de aceitar evidencias com `observed_at`. |
| `edge-security` | Confirmar nomes reais das interfaces e CIDRs; duas interfaces configuradas nao provam travessia se o fluxo nao aparecer em ambas. |

## Dependencias ainda ausentes

- Merge futuro das branches em uma base comum.
- Senhas locais nao versionadas para HTTP Basic administrativo e gateway.
- Suporte de Basic gateway na Edge e no Backend.
- Usuario MQTT de leitura dedicado para o worker, se aprovado.
- Hardware ESP32 conectado, rede Wi-Fi de laboratorio e sensor/pinagem aprovados.
- Gateway Linux inline com duas interfaces ou arranjo equivalente.
- Confirmacao de IP do broker e CIDRs reais da topologia.
- Validacao real ponta a ponta e evidencias em `docs/evidence/`.
