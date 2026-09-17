# HarpiSense Backend

Base local para a API FastAPI, PostgreSQL, SQLAlchemy, Alembic e ingestao de telemetria MQTT.

## Configuracao

Os comandos abaixo assumem o diretorio `backend/` como diretorio atual.

```powershell
Copy-Item .env.example .env
# Edite HARPI_ADMIN_PASSWORD, HARPI_GATEWAY_PASSWORD e HARPI_MQTT_PASSWORD no .env local.

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

docker compose up -d postgres
alembic upgrade head
uvicorn app.main:app --reload
```

Configuracao padrao:

- API: `http://localhost:8000`
- Health: `http://localhost:8000/api/v1/health`
- PostgreSQL: `localhost:5432`
- Database: `harpisense`
- User/password local do banco: `harpisense` / `harpisense`

Senhas reais nao devem ser versionadas. Use `.env`, que ja esta coberto pelo `.gitignore`.

## Autenticacao

`GET /api/v1/health` e publico. Os demais endpoints usam HTTP Basic com clientes separados:

```text
HARPI_ADMIN_USERNAME=admin
HARPI_ADMIN_PASSWORD=<senha-local>
HARPI_GATEWAY_USERNAME=harpisense.gateway.edge-1
HARPI_GATEWAY_PASSWORD=<senha-local-do-gateway>
```

Permissoes desta entrega:

- Administrador: `POST /api/v1/ingest/telemetry`, `GET /api/v1/telemetry`, `GET /api/v1/network-events`.
- Gateway: `POST /api/v1/ingest/network-events`.

Credenciais administrativas nao sao aceitas como substituto implicito das credenciais do gateway. Credenciais de gateway tambem nao acessam endpoints administrativos. Nao ha cadastro publico, multiplos perfis ou RBAC nesta etapa.

## Endpoints

```text
GET  /api/v1/health
POST /api/v1/ingest/telemetry
POST /api/v1/ingest/network-events
GET  /api/v1/telemetry
GET  /api/v1/network-events
```

Duplicidade e tratada pelos identificadores contratados:

- Telemetria: `message_id`
- Evento de rede/seguranca: `event_id`

Ao reenviar o mesmo identificador com conteudo identico, a API responde `202 Accepted` com `duplicate: true` e nao cria novo registro. Se o mesmo identificador for reutilizado com conteudo diferente, a API retorna `409 Conflict` com `error.code = identifier_conflict`.

Para `network_event`, o objeto opcional `aggregation` e aceito, validado e persistido como parte do payload. Se `aggregation` estiver presente e invalido, a API retorna `422 Unprocessable Entity`. `network_window` permanece fora da ingestao HTTP atual.

## Ingestao MQTT

O worker MQTT consome telemetria em `harpisense/v1/telemetry/+/+` e persiste o mesmo payload aceito por `POST /api/v1/ingest/telemetry`. Ele deve ser executado como processo separado da API; `app.main` nao inicia consumidor MQTT, evitando um consumidor duplicado por worker da API.

```powershell
$env:HARPI_MQTT_ENABLED="true"
python -m app.mqtt_worker
```

Variaveis relevantes:

```text
HARPI_MQTT_HOST=localhost
HARPI_MQTT_PORT=1883
HARPI_MQTT_USERNAME=harpisense_backend_consumer
HARPI_MQTT_PASSWORD=<senha-mqtt-backend-consumer>
HARPI_MQTT_TELEMETRY_TOPIC=harpisense/v1/telemetry/+/+
```

O usuario MQTT dedicado do worker deve ser `harpisense_backend_consumer`, com segredo fornecido externamente e nao versionado. No broker, esse usuario deve ter apenas leitura/assinatura em `harpisense/v1/telemetry/#`, sem permissao de publicacao ou leitura em `harpisense/v1/security/#`.

O worker fecha a conexao MQTT no encerramento do processo. Logs registram topico, ids de mensagem e erros operacionais, sem imprimir usuario ou senha MQTT.

## Testes preparados

Os testes de integracao usam PostgreSQL real e pulam quando o banco de teste nao esta configurado. SQLite nao deve ser usado para afirmar compatibilidade.

```powershell
$env:HARPI_TEST_DATABASE_URL="postgresql+psycopg://harpisense:harpisense@localhost:5432/harpisense_test"
pytest
```

Cobertura preparada:

- duplicata identica de `message_id`;
- reutilizacao de `message_id` e `event_id` com conteudo diferente;
- duplicata concorrente de telemetria;
- autenticacao separada de administrador e gateway;
- restricao de endpoints por cliente;
- `aggregation` valido, invalido e persistido em `network_event`;
- rejeicao de `network_window` na ingestao atual;
- payload invalido;
- valores `null` preservados em telemetria, captura MQTT e classificacao;
- filtros temporais e limite maximo;
- falha de banco sem resposta `202`.

## Verificacao com dados conhecidos

Com PostgreSQL migrado, API rodando, `HARPI_ADMIN_PASSWORD` e `HARPI_GATEWAY_PASSWORD` configuradas:

```powershell
.\scripts\verify_known_data.ps1 -Password "<senha-admin-local>" -GatewayPassword "<senha-gateway-local>"
```

O script verifica:

- health check;
- autenticacao via HTTP Basic;
- ingestao de telemetria conhecida;
- reenvio da mesma telemetria como duplicada;
- ingestao de `network_event` conhecido;
- reenvio do mesmo evento como duplicado;
- consulta de telemetria;
- consulta de eventos de rede.

Os dados do script representam telemetria comum e metadados brutos de trafego legitimo. Eles nao devem ser apresentados como incidentes, ataques ou deteccoes reais.
