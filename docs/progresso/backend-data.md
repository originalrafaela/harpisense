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

## Estado em 2026-09-17

Revisao complementar na branch `backend-data`, preservando API, autenticacao existente, modelos, migration inicial e consumidor MQTT.

Implementado/preparado:

- Reenvio identico por `message_id` e `event_id` permanece idempotente com `202 Accepted` e `duplicate: true`.
- Reutilizacao do mesmo identificador com conteudo diferente agora retorna conflito por `IdentifierConflictError`.
- Proposta para o Arquiteto registrada em `backend/README.md`: formalizar `409 Conflict` com `error.code = identifier_conflict` para identificador idempotente reutilizado com payload divergente.
- Persistencia HTTP continua respondendo `202` somente apos `commit` e `refresh`; falhas SQLAlchemy passam pelo handler `database_error` com `503`.
- Valores `null` permitidos nos payloads continuam como `None`/JSON null, sem conversao para zero.
- Consultas adicionaram desempate por `id` depois de `observed_at` e `received_at`, mantendo filtros temporais e limite maximo `500`.
- `ensure_device` usa `INSERT ... ON CONFLICT DO NOTHING` em PostgreSQL para reduzir corrida na criacao canonica de dispositivo.
- Worker MQTT permanece executavel separado (`python -m app.mqtt_worker`), nao e iniciado por `app.main`, fecha a conexao no encerramento e nao loga credenciais.
- Testes de integracao preparados em `backend/tests/`, exigindo PostgreSQL real via `HARPI_TEST_DATABASE_URL` ou `--postgres-url`.

Testes preparados nesta rodada:

- duplicata identica de telemetria;
- conflito de `message_id` com payload diferente;
- duplicata concorrente de telemetria;
- payload invalido;
- preservacao de `null`;
- filtros temporais e limite maximo;
- conflito de `event_id` com payload diferente;
- falha de banco sem resposta `202`.

Testes realmente executados nesta rodada:

- Ainda nao executados com Python/PostgreSQL neste host.

Pendencias de validacao real:

- Executar `pytest` com `HARPI_TEST_DATABASE_URL` apontando para PostgreSQL de teste.
- Executar `alembic upgrade head` em PostgreSQL real.
- Validar API com PostgreSQL ativo e credencial local.
- Validar worker MQTT com broker real.

## Estado em 2026-09-17 apos merge de `main`

Revisao de compatibilidade com o contrato atualizado incorporado da `main`, sem editar `docs/CONTRATOS_COMPARTILHADOS.md` ou demais contratos compartilhados.

Implementado nesta rodada:

- Separacao de HTTP Basic administrativo e HTTP Basic do gateway.
- Novas configuracoes `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`.
- `POST /api/v1/ingest/network-events` agora exige credencial do gateway e nao aceita a credencial administrativa como fallback.
- Endpoints administrativos continuam exigindo credencial administrativa:
  - `POST /api/v1/ingest/telemetry`
  - `GET /api/v1/telemetry`
  - `GET /api/v1/network-events`
- Respostas envelopadas para credencial ausente/invalida (`401`), configuracao ausente/invalida (`503`) e conflitos de identificador (`409 identifier_conflict`).
- `aggregation` em `network_event` passou a ser aceito, validado e persistido no JSONB `payload`; objeto invalido retorna `422`.
- `network_window` permanece fora da ingestao atual, rejeitado pelo contrato de `event_type`.
- Comparacao de idempotencia de `event_id` inclui `aggregation` normalizado; campo opcional omitido e `null` sao tratados de forma consistente.
- Worker MQTT documentado/configurado para usar o usuario dedicado `harpisense_backend_consumer`, com senha fornecida externamente.
- Script `backend/scripts/verify_known_data.ps1` atualizado para usar senha administrativa nas consultas/telemetria e senha de gateway nos eventos de rede.

Testes preparados nesta rodada:

- autenticacao administrativa valida nos endpoints administrativos;
- credencial do gateway aceita somente em `POST /api/v1/ingest/network-events`;
- credencial administrativa recusada em ingestao de `network-events`;
- ausencia de credencial do gateway retorna `401`;
- configuracao ausente de gateway retorna `503`;
- gateway recusado em endpoints administrativos;
- `aggregation` valido aceito, persistido e idempotente;
- `aggregation` invalido retorna `422`;
- `network_window` rejeitado pela ingestao atual;
- duplicatas e `409 identifier_conflict` preservados para `message_id` e `event_id`.

Testes realmente executados nesta rodada:

- `git diff --check`: executado apos as alteracoes.
- `git diff --cached --check`: executado antes do commit.

Nao executados nesta rodada:

- `pytest`, pois o host continua sem `python` no PATH e a validacao real com PostgreSQL ficara para etapa posterior.
- Validacao com broker MQTT real.

Pendencias para integracao:

- Configurar `HARPI_GATEWAY_USERNAME=harpisense.gateway.edge-1` e `HARPI_GATEWAY_PASSWORD` no ambiente real do backend.
- Atualizar a Edge para enviar HTTP Basic com `HARPISENSE_BACKEND_USERNAME` e `HARPISENSE_BACKEND_PASSWORD`.
- Provisionar no Mosquitto o usuario `harpisense_backend_consumer` com somente leitura em `harpisense/v1/telemetry/#`.
- Executar `pytest` com `HARPI_TEST_DATABASE_URL` apontando para PostgreSQL real.

## Commits relevantes

- `5a05547e58b1f3b4b3d8183e51374b1c4a26beef` - `Implement backend ingestion base`
