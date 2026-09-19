# HarpiSense - Primeira versao integrada na VM Ubuntu

Este guia descreve a execucao reproduzivel da branch `integration/primeira-entrega` em uma VM Linux. Ele usa os arquivos reais integrados das branches `backend-data`, `iot-mqtt` e `edge-security`.

Nao coloque senhas reais no Git. Use placeholders nos comandos e variaveis locais na VM.

## Estado integrado

- Backend FastAPI/PostgreSQL/Alembic em `backend/`.
- Consumidor MQTT do backend em `backend/app/mqtt_worker.py`.
- Mosquitto e ACLs em `mqtt/`.
- Simulador MQTT sintetico em `lab/legitimate-traffic/simulate_poste.py`.
- Edge Security em `edge/capture/scapy_gateway.py`.
- Teste sintetico integrado em `tests/integration/run_first_delivery_vm.sh`.

## Dependencias Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip docker.io docker-compose-plugin curl tcpdump
sudo usermod -aG docker "$USER"
```

Abra uma nova sessao depois de adicionar o usuario ao grupo `docker`, ou execute Docker com `sudo` nessa sessao.

## Ambiente Python unico da integracao

Na raiz da worktree:

```bash
cd /caminho/para/harpisense
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install -r lab/legitimate-traffic/requirements.txt
python -m pip install -r edge/requirements.txt
```

## Configuracao local

Crie `backend/.env` a partir do exemplo e substitua apenas localmente:

```bash
cp backend/.env.example backend/.env
```

Valores esperados, sem senhas reais no documento:

```text
HARPI_DATABASE_URL=postgresql+psycopg://harpisense:harpisense@localhost:5432/harpisense
HARPI_ADMIN_USERNAME=admin
HARPI_ADMIN_PASSWORD=<senha-admin-local>
HARPI_GATEWAY_USERNAME=harpisense.gateway.edge-1
HARPI_GATEWAY_PASSWORD=<senha-gateway-local>
HARPI_MQTT_ENABLED=true
HARPI_MQTT_HOST=localhost
HARPI_MQTT_PORT=1883
HARPI_MQTT_USERNAME=harpisense_backend_consumer
HARPI_MQTT_PASSWORD=<senha-mqtt-backend-consumer>
HARPI_MQTT_TELEMETRY_TOPIC=harpisense/v1/telemetry/+/+
```

Use senhas diferentes para administrador, gateway e MQTT.

## PostgreSQL

O compose usa o volume nomeado `harpisense-postgres-data`. Para preservar banco existente, nao use `docker compose down -v`.

```bash
cd backend
docker compose up -d postgres
cd ..
```

Aplicar migracoes:

```bash
. .venv/bin/activate
cd backend
alembic upgrade head
cd ..
```

## Mosquitto

O compose monta `mqtt/config`, `mqtt/data` e `mqtt/log`. Para preservar dados existentes, nao remova `mqtt/data`, `mqtt/log` nem o arquivo local `mqtt/config/passwords`.

Primeira criacao do password file:

```bash
cd mqtt
export HARPISENSE_BACKEND_CONSUMER_PASSWORD='<senha-mqtt-backend-consumer>'
docker compose --profile init run --rm -e HARPISENSE_BACKEND_CONSUMER_PASSWORD mosquitto-init
unset HARPISENSE_BACKEND_CONSUMER_PASSWORD
docker compose up -d mosquitto
cd ..
```

Se `mqtt/config/passwords` ja existir, o script de init nao sobrescreve por padrao. Para rotacionar credenciais conscientemente, use o modo `--force` descrito em `mqtt/README.md`.

ACLs relevantes em `mqtt/config/aclfile`:

- `iot_device_lab`: publica telemetria no proprio `client_id` (`poste-1`, `poste-2`, `poste-3`).
- `harpisense_backend_consumer`: somente leitura em `harpisense/v1/telemetry/#`.
- Sem permissao do consumidor backend em `harpisense/v1/security/#`.

## API backend

Terminal 1:

```bash
. .venv/bin/activate
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health publico:

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
```

## Consumidor MQTT do backend

Terminal 2:

```bash
. .venv/bin/activate
cd backend
python -m app.mqtt_worker
```

O worker valida topico contra `device_id` e `sensor_type`, preserva `null`, persiste via o mesmo servico de ingestao de telemetria e reaproveita a idempotencia por `message_id`.

## Simulador MQTT

Terminal 3:

```bash
. .venv/bin/activate
export MQTT_HOST='127.0.0.1'
export MQTT_PORT='1883'
export MQTT_USERNAME='iot_device_lab'
export MQTT_PASSWORD='<senha-mqtt-publicacao>'
python lab/legitimate-traffic/simulate_poste.py --device poste-2 --count 3 --interval 1 --seed 20260919
unset MQTT_PASSWORD
```

Os dados do simulador sao sinteticos. Nao apresente essa saida como captura real de sensor fisico.

## Edge Security

No gateway Linux com interfaces reais:

```bash
. .venv/bin/activate
ip -brief address
ip route
export HARPISENSE_BACKEND_USERNAME='harpisense.gateway.edge-1'
export HARPISENSE_BACKEND_PASSWORD='<senha-gateway-local>'
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
unset HARPISENSE_BACKEND_PASSWORD
```

Ajuste `--iface`, CIDRs e `--broker-host` para a topologia real. Duas interfaces configuradas nao provam travessia; confirme `aggregation.interfaces_observed`, `aggregation.expected_interfaces` e `aggregation.traversal_verified`.

## Consultas administrativas

```bash
curl -fsS -u 'admin:<senha-admin-local>' 'http://127.0.0.1:8000/api/v1/telemetry?limit=10'
curl -fsS -u 'admin:<senha-admin-local>' 'http://127.0.0.1:8000/api/v1/network-events?dst_port=1883&limit=10'
```

A credencial do gateway deve falhar em endpoints administrativos:

```bash
curl -i -u 'harpisense.gateway.edge-1:<senha-gateway-local>' 'http://127.0.0.1:8000/api/v1/network-events?limit=1'
```

Resposta esperada: `401 Unauthorized` ou `403 Forbidden`.

## Teste integrado sintetico

Com PostgreSQL, API, Mosquitto e consumidor MQTT ja em execucao:

```bash
. .venv/bin/activate
export API_BASE_URL='http://127.0.0.1:8000'
export MQTT_HOST='127.0.0.1'
export MQTT_PORT='1883'
export MQTT_USERNAME='iot_device_lab'
export MQTT_PASSWORD='<senha-mqtt-publicacao>'
export HARPI_ADMIN_USERNAME='admin'
export HARPI_ADMIN_PASSWORD='<senha-admin-local>'
export HARPI_GATEWAY_USERNAME='harpisense.gateway.edge-1'
export HARPI_GATEWAY_PASSWORD='<senha-gateway-local>'
bash tests/integration/run_first_delivery_vm.sh
unset MQTT_PASSWORD HARPI_ADMIN_PASSWORD HARPI_GATEWAY_PASSWORD
```

O teste:

- publica uma telemetria sintetica identificavel via simulador MQTT;
- extrai o `message_id` da saida do simulador;
- aguarda persistencia pelo consumidor MQTT;
- consulta a telemetria pela API administrativa;
- envia um `network_event` sintetico autenticado com Basic do gateway;
- consulta o evento pela API administrativa e verifica `aggregation`.

Esse teste valida a integracao em execucao, mas nao substitui captura real no gateway nem evidencia de sensor fisico.

## Verificacoes de contrato

- MQTT aceita `null` em campos contratados, como `status.battery_pct`; `measurements` nao pode ser vazio.
- `POST /api/v1/ingest/telemetry` e consultas administrativas exigem Basic admin.
- `POST /api/v1/ingest/network-events` exige Basic do gateway.
- Reenvio identico de `message_id` ou `event_id` retorna `202` com `duplicate: true`.
- Reutilizacao de identificador com conteudo diferente retorna `409` com `error.code = identifier_conflict`.
- `aggregation` valido e persistido em `payload`; `aggregation` invalido retorna `422`.
- `network_window` nao e aceito pela API nesta entrega.
- Host na VM: normalmente `localhost`/`127.0.0.1` para API, PostgreSQL e Mosquitto publicados no host.
- Entre containers: use nomes de servico Docker quando houver uma rede Compose compartilhada; os compose atuais de backend e MQTT sao separados, entao a execucao documentada usa portas expostas no host.

## ML

Nao ha implementacao de ML integrada nesta entrega.

- Extracao de features: existe apenas feature engineering observacional/documentado no Edge (`edge/README.md`) e campos agregados em `edge/capture/aggregator.py`; nao ha pipeline ML.
- Preparacao de dataset: nao ha codigo de dataset.
- Treinamento: nao ha codigo de treinamento.
- Avaliacao: nao ha avaliador de modelo.
- Inferencia: nao ha inferencia online/offline com modelo treinado.
- Artefatos de modelo: nao ha `.pkl`, `.joblib`, ONNX ou artefato equivalente versionado.

## Testes que dependem da VM

- `python -m pytest backend/tests tests/security tests/integration/test_mqtt_contract.py`, porque o ambiente atual precisa de Python e dependencias.
- Testes backend com PostgreSQL real usando `HARPI_TEST_DATABASE_URL`.
- ACL real do Mosquitto com `tests/integration/test_mqtt_backend_consumer_acl.ps1` ou equivalente Linux.
- Teste sintetico integrado `tests/integration/run_first_delivery_vm.sh`.
- Captura real Edge com Scapy, interfaces e CIDRs da VM/gateway.
- Validacao com ESP32 fisico, sensor/pinagem e NTP.
