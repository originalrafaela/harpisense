# Progresso - backend-data

## Estado em 2026-09-16

- Pasta de trabalho: `D:\Projetos\harpisense-worktrees\backend-data`
- Branch atual: `backend-data`
- Remote esperado: `origin -> https://github.com/originalrafaela/harpisense.git`
- Commit de implementacao existente: `5a05547e58b1f3b4b3d8183e51374b1c4a26beef`

## Implementacao realizada

Foi implementada a base inicial do backend da primeira entrega, restrita ao escopo `backend-data`:

- FastAPI em `backend/app/main.py`.
- Router v1 em `backend/app/api/v1/router.py`.
- Health check publico em `GET /api/v1/health`.
- Autenticacao HTTP Basic de administrador unico em `backend/app/core/security.py`.
- Configuracao via variaveis `HARPI_...` em `backend/app/core/config.py`.
- Exemplo de configuracao em `backend/.env.example`, sem senha real.
- PostgreSQL local via `backend/docker-compose.yml`.
- SQLAlchemy em `backend/app/db/` e modelos em `backend/app/models/`.
- Alembic em `backend/alembic.ini` e `backend/alembic/`.
- Migration inicial em `backend/alembic/versions/20260916002434_0001_initial_schema.py`.
- Schemas Pydantic em `backend/app/schemas/`.
- Servicos de persistencia e consulta em `backend/app/services/`.
- Ingestao HTTP:
  - `POST /api/v1/ingest/telemetry`
  - `POST /api/v1/ingest/network-events`
- Consultas HTTP:
  - `GET /api/v1/telemetry`
  - `GET /api/v1/network-events`
- Ingestao MQTT opcional de telemetria em `backend/app/mqtt/consumer.py` e `backend/app/mqtt_worker.py`.
- Script de verificacao com dados conhecidos em `backend/scripts/verify_known_data.ps1`.
- Documentacao de execucao e teste em `backend/README.md`.

## Entidades criadas

- `devices`: dispositivos canonicos iniciais (`poste`, `gateway`, `broker`).
- `telemetry_records`: telemetria de sensores, com `message_id` unico.
- `security_events`: eventos de rede/seguranca, com `event_id` unico.

## Decisoes tomadas e contratos usados

Fontes usadas, sem alteracao:

- `docs/DECISOES_ARQUITETURAIS.md`
- `docs/CONTRATOS_COMPARTILHADOS.md`
- `docs/PLANO_PRIMEIRA_ENTREGA.md`
- `docs/AREAS_DE_TRABALHO.md`

Decisoes aplicadas:

- Primeira entrega limitada a ingestao, persistencia e consulta.
- Sem dashboard completo, RBAC, cadastro publico, AWS, BitNet, ML, SHAP/XAI ou bloqueios reais.
- Autenticacao com um unico administrador.
- Senhas reais ficam fora do repositorio; somente nomes de variaveis foram documentados.
- Idempotencia por identificadores contratados:
  - Telemetria: `message_id`.
  - Eventos de rede/seguranca: `event_id`.
- Backend adiciona `received_at`.
- Produtores devem enviar `observed_at` ISO 8601 UTC com sufixo `Z`.
- `network_event` da primeira entrega permanece `classification.stage = raw_capture` e `classification.label = unknown`.
- Telemetria comum nao e classificada como incidente.
- Eventos de teste/verificacao nao devem ser apresentados como deteccoes reais.

## Testes realmente executados

Executados neste host:

- `git diff --check`: passou, apenas aviso de conversao LF/CRLF em Windows.
- `git diff --cached --check`: passou antes do commit `5a05547e58b1f3b4b3d8183e51374b1c4a26beef`.
- Confirmacao da branch: `git branch --show-current` retornou `backend-data`.
- Confirmacao do remote: `git remote -v` mostrou `https://github.com/originalrafaela/harpisense.git`.
- Confirmacao de status apos o commit de implementacao: worktree estava limpo antes deste arquivo de progresso.

Nao houve evidencia local de execucao de API, migracao ou ingestao real neste host.

## Testes nao executados, bloqueios e dependencias

Nao executados neste host:

- `python -m compileall ...`
- `pip install -r requirements.txt`
- `alembic upgrade head`
- Subida da API com `uvicorn app.main:app --reload`
- Execucao de `backend/scripts/verify_known_data.ps1`
- Teste de ingestao MQTT com broker real
- Teste ponta a ponta com ESP32, simuladores, gateway e broker Mosquitto

Bloqueios observados:

- `py -0p` retornou `No installed Pythons found!`; nao ha instalacao Python confirmada.
- `python` nao esta disponivel no PATH.
- Docker CLI existe, mas o daemon nao estava acessivel: falha ao conectar em `npipe:////./pipe/docker_engine`.

Dependencias para validar:

- Python instalado e acessivel.
- Ambiente virtual criado.
- Docker daemon ativo ou PostgreSQL local equivalente.
- Banco PostgreSQL migrado.
- Variavel `HARPI_ADMIN_PASSWORD` configurada localmente.
- Broker MQTT disponivel para validar o worker MQTT.

## Ambiente Python

- Caminho de Python confirmado: nao confirmado.
- Ambiente virtual confirmado: nao confirmado.
- Launcher `py.exe` existe em `C:\Windows\py.exe`, mas nao encontrou uma instalacao Python.

## Trabalho incompleto e alinhamentos pendentes

- Validar migrações Alembic em PostgreSQL real.
- Validar autenticação com credenciais locais.
- Validar ingestão HTTP e consultas com dados conhecidos.
- Validar idempotencia por `message_id` e `event_id` em banco real.
- Validar worker MQTT com broker Mosquitto real.
- Alinhar com `iot-mqtt` o envio dos payloads nos topicos contratados.
- Alinhar com `edge-security` o envio de `network_event` bruto pelo gateway.
- Registrar evidencias em `docs/evidence/` somente depois de testes realmente executados.

## Proximos passos

1. Instalar/confirmar Python e criar ambiente local:

```powershell
cd D:\Projetos\harpisense-worktrees\backend-data\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Criar `.env` local e configurar variaveis sem versionar segredo:

```powershell
Copy-Item .env.example .env
```

Variaveis necessarias:

- `HARPI_DATABASE_URL`
- `HARPI_ADMIN_USERNAME`
- `HARPI_ADMIN_PASSWORD`
- `HARPI_MQTT_ENABLED`
- `HARPI_MQTT_HOST`
- `HARPI_MQTT_PORT`
- `HARPI_MQTT_USERNAME`
- `HARPI_MQTT_PASSWORD`
- `HARPI_MQTT_TELEMETRY_TOPIC`

3. Subir PostgreSQL local e aplicar migrações:

```powershell
docker compose up -d postgres
alembic upgrade head
```

4. Subir API:

```powershell
uvicorn app.main:app --reload
```

5. Verificar com dados conhecidos:

```powershell
.\scripts\verify_known_data.ps1 -Password "<senha-local>"
```

6. Validar worker MQTT, se houver broker disponivel:

```powershell
$env:HARPI_MQTT_ENABLED="true"
python -m app.mqtt_worker
```

## Commits relevantes

- `5a05547e58b1f3b4b3d8183e51374b1c4a26beef` - `Implement backend ingestion base`
