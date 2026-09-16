# HarpiSense Backend

Base local para a API FastAPI, PostgreSQL, SQLAlchemy, Alembic e ingestao de telemetria MQTT.

## Configuracao

Os comandos abaixo assumem o diretorio `backend/` como diretorio atual.

```powershell
Copy-Item .env.example .env
# Edite HARPI_ADMIN_PASSWORD no .env antes de subir a API.

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

Exceto `GET /api/v1/health`, os endpoints usam HTTP Basic com um unico administrador:

```text
HARPI_ADMIN_USERNAME=admin
HARPI_ADMIN_PASSWORD=<senha-local>
```

Nao ha cadastro publico, multiplos perfis ou RBAC nesta etapa.

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

Ao reenviar o mesmo identificador, a API responde `202 Accepted` com `duplicate: true` e nao cria novo registro.

## Ingestao MQTT

O worker MQTT consome telemetria em `harpisense/v1/telemetry/+/+` e persiste o mesmo payload aceito por `POST /api/v1/ingest/telemetry`.

```powershell
$env:HARPI_MQTT_ENABLED="true"
python -m app.mqtt_worker
```

Variaveis relevantes:

```text
HARPI_MQTT_HOST=localhost
HARPI_MQTT_PORT=1883
HARPI_MQTT_USERNAME=
HARPI_MQTT_PASSWORD=
HARPI_MQTT_TELEMETRY_TOPIC=harpisense/v1/telemetry/+/+
```

## Verificacao com dados conhecidos

Com PostgreSQL migrado, API rodando e `HARPI_ADMIN_PASSWORD` configurada:

```powershell
.\scripts\verify_known_data.ps1 -Password "<senha-local>"
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
