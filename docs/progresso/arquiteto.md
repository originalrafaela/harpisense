# Progresso - arquiteto

## Atualizacao em 2026-09-17

Rodada de preparacao documental da integracao, sem merge das branches de area e sem validacao real.

Branches lidas sem troca de worktree ocupada:

- `iot-mqtt` em `5cf116fd1d11b290734fc97a1c8fac6088571877`.
- `edge-security` em `97c4e5a5d1c5d08851e3bb9e8d413fa2312e918d`.
- `backend-data` em `1607ff89c725ee689666d7e9e7b0614f58ed7ff2`.

Implementacoes conferidas:

- Backend:
  - `backend/app/core/security.py`: HTTP Basic administrativo com `HARPI_ADMIN_USERNAME` e `HARPI_ADMIN_PASSWORD`.
  - `backend/app/core/config.py`: ainda sem `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`.
  - `backend/app/schemas/telemetry.py`: `measurements` nao pode ser vazio; opcionais aceitam `null`.
  - `backend/app/schemas/security_event.py`: `network_event` exige `raw_capture` e `unknown`.
  - `backend/app/services/telemetry.py`: idempotencia por `message_id`.
  - `backend/app/services/security_events.py`: idempotencia por `event_id`.
  - `backend/app/mqtt/consumer.py`: consumidor MQTT persiste via `ingest_telemetry` e valida topico contra payload.
- Edge:
  - `edge/capture/backend_client.py`: envio HTTP com Bearer opcional, sucesso apenas em `202`.
  - `edge/capture/scapy_gateway.py`: aceita `--backend-token-env` e `--backend-token-file`, ainda sem Basic do gateway.
- IoT/MQTT:
  - `mqtt/docker-compose.yml`: Mosquitto em `1883` e init de password file.
  - `mqtt/config/aclfile`: `iot_device_lab`, `mqtt_test_subscriber` e `mqtt_auth_exporter`.
  - `lab/legitimate-traffic/simulate_poste.py`: usa `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME` e `MQTT_PASSWORD`.

Documentos atualizados:

- `docs/CONTRATOS_COMPARTILHADOS.md`: autenticacao HTTP separada entre administrador e gateway, estado real das implementacoes, respostas esperadas, checklist minimo e detalhes do consumidor MQTT.
- `docs/ROTEIRO_INTEGRACAO_PRIMEIRA_ENTREGA.md`: commits lidos, contrato de autenticacao para integracao, ordem de inicializacao, comandos reais, pendencias e validacoes ainda abertas.

Decisao mantida:

- Nao deixar ingestao HTTP desprotegida como solucao de compatibilidade.
- Administrador continua usando HTTP Basic administrativo.
- Gateway deve usar HTTP Basic proprio em `POST /api/v1/ingest/network-events`.
- Bearer opcional da Edge nao deve ser usado contra o backend atual.
- BitNet local permanece fora do caminho critico.
- Administrador unico e modos IDS, IPS supervisionado e IPS autonomo seguem como definidos.

Correcoes pontuais pendentes por area:

- `backend-data`: implementar `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`; aceitar Basic do gateway somente em `POST /api/v1/ingest/network-events`; manter Basic administrativo nos demais endpoints; retornar `503` se senha de gateway nao estiver configurada; decidir persistencia ou rejeicao explicita de `aggregation`.
- `edge-security`: implementar envio de `Authorization: Basic ...` a partir de `HARPISENSE_BACKEND_USERNAME` e `HARPISENSE_BACKEND_PASSWORD`; nao usar Bearer no backend atual; manter falha de entrega quando status for diferente de `202`.
- `iot-mqtt`: decidir se o worker backend usa temporariamente `mqtt_test_subscriber` ou usuario dedicado `harpisense_backend_consumer`; definir sensor/pinagem do ESP32; validar NTP antes de aceitar evidencias reais.

Validacoes ainda pendentes:

- Nenhuma integracao real foi executada nesta rodada.
- Continuam pendentes PostgreSQL, API, Mosquitto, consumidor MQTT, simulador, ESP32, gateway Edge, envio ao backend e consultas finais.
- Evidencias em `docs/evidence/` devem ser registradas somente depois da execucao real.

## Contexto

- Data: 2026-09-16.
- Pasta de trabalho: `D:\Projetos\tcc - harpisense`.
- Branch atual: `main`.
- Remote conferido: `origin` aponta para `https://github.com/originalrafaela/harpisense.git`.
- Worktree principal: `D:/Projetos/tcc - harpisense`.
- Worktrees existentes lidas sem troca de branch:
  - `D:/Projetos/harpisense-worktrees/iot-mqtt` em `iot-mqtt`.
  - `D:/Projetos/harpisense-worktrees/edge-security` em `edge-security`.
  - `D:/Projetos/harpisense-worktrees/backend-data` em `backend-data`.

## Implementado nesta area

Preparacao documental na `main`, sem implementar funcionalidades das areas:

- `docs/DECISOES_ARQUITETURAIS.md`: decisoes vigentes da primeira etapa.
- `docs/CONTRATOS_COMPARTILHADOS.md`: contratos MQTT, payloads, identificadores, timestamps, ingestao HTTP, autenticacao e consumidor MQTT.
- `docs/PLANO_PRIMEIRA_ENTREGA.md`: escopo da primeira entrega, criterios de aceite, estado observado, faltas e dependencias.
- `docs/AREAS_DE_TRABALHO.md`: posse de diretorios e fonte compartilhada centralizada.
- `docs/ROTEIRO_INTEGRACAO_PRIMEIRA_ENTREGA.md`: roteiro unico de integracao com comandos reais encontrados nas branches.
- `docs/progresso/arquiteto.md`: este registro de continuidade.

## Decisoes e contratos usados

- Administrador unico, sem multiplos perfis, RBAC ou cadastro publico nesta etapa.
- BitNet local permanece fora do caminho critico e sera usado apenas para explicar incidentes em etapa posterior.
- A protecao deve funcionar com BitNet desligado.
- Modos mantidos:
  - IDS: detecta, registra e alerta, sem bloquear.
  - IPS supervisionado: recomenda bloqueio, administrador aprova ou rejeita; solicitacoes expiram e devem ser revalidadas.
  - IPS autonomo: resposta automatica futura dentro de limites definidos por ML e politica.
- Primeira entrega: demonstrar publicacao MQTT, trafego legitimo atravessando gateway e persistencia/consulta pela API.
- Fora da primeira entrega: ML treinado, bloqueios reais, dashboard completo, AWS e BitNet integrado.
- Telemetria de sensores separada de eventos de seguranca.
- Timestamps em ISO 8601 UTC com sufixo `Z`.
- `observed_at` vem do produtor/observacao; `received_at` vem do backend.
- Idempotencia:
  - Telemetria por `message_id`.
  - Eventos de rede por `event_id`.
- Valores desconhecidos podem ser `null` ou omitidos; nao usar `"N/A"`.
- `measurements` nao pode ser objeto vazio.
- Ingestao HTTP nao deve ficar desprotegida.
- Autenticacao documentada:
  - Administrador: HTTP Basic com `HARPI_ADMIN_USERNAME` e `HARPI_ADMIN_PASSWORD`.
  - Gateway: HTTP Basic separado, alvo `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`.
  - Bearer opcional da Edge nao deve ser usado contra backend atual ate haver suporte explicito.
- Consumidor MQTT responsavel por alimentar o banco identificado em `backend/app/mqtt/consumer.py`, executado por `python -m app.mqtt_worker`.

## Testes realmente executados

- Nao foram executados testes automatizados de implementacao nesta area.
- Foram executadas conferencias documentais e Git:
  - `git status --short --branch`.
  - `git branch --show-current`.
  - `git remote -v`.
  - `git worktree list --porcelain`.
  - `git diff --check` antes do commit de integracao documental.
  - `git show --stat --oneline --name-only HEAD` apos commits anteriores.
- Resultado: a preparacao documental foi commitada localmente; nenhuma validacao real ponta a ponta foi declarada.

## Testes nao executados, bloqueios e dependencias

- Nao foi executada integracao real entre PostgreSQL, API, Mosquitto, consumidor MQTT, simulador, ESP32 e Edge.
- Nao foram executados testes das branches `iot-mqtt`, `edge-security` ou `backend-data` a partir da `main`.
- Nao foram validados hardware ESP32, sensor fisico, pinagem, Wi-Fi, NTP, broker real, interfaces do gateway ou CIDRs reais.
- Nao foi validada persistencia real pela API depois de captura Edge.
- Dependencias externas:
  - Docker/Compose para PostgreSQL e Mosquitto.
  - Python/venv por area.
  - Gateway Linux inline com duas interfaces ou arranjo equivalente.
  - ESP32 fisico e sensor/pinagem aprovados.
  - Senhas locais nao versionadas para MQTT, administrador e gateway.

## Trabalho incompleto e alinhamentos pendentes

- `backend-data` precisa implementar credencial Basic separada do gateway em `POST /api/v1/ingest/network-events`.
- `edge-security` precisa implementar envio de `Authorization: Basic ...` com usuario/senha do gateway.
- `backend-data` precisa decidir se persiste ou rejeita explicitamente o objeto `aggregation` produzido pela Edge; hoje a documentacao alerta para evitar perda silenciosa.
- `iot-mqtt` precisa decidir se o worker backend usa temporariamente `mqtt_test_subscriber` ou se sera criado usuario dedicado `harpisense_backend_consumer`.
- `iot-mqtt` precisa definir sensor fisico e pinagem do ESP32.
- `iot-mqtt` precisa validar sincronizacao de hora do ESP32; `1970-01-01T00:00:00.000Z` nao deve ser aceito como evidencia real.
- `edge-security` precisa confirmar nomes reais das interfaces e CIDRs. Configurar duas interfaces nao basta; a travessia precisa aparecer nos eventos.
- As branches ainda nao foram mergeadas na `main`.

## Proximos passos em ordem

1. Garantir que todas as branches estejam publicadas no GitHub antes de qualquer integracao.
2. Aplicar nas areas as correcoes de autenticacao documentadas:
   - Backend: adicionar `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`.
   - Edge: adicionar envio Basic do gateway.
3. Decidir tratamento de `aggregation` no backend.
4. Decidir usuario MQTT de leitura do worker backend.
5. Preparar ambiente de integracao local apos merges planejados, sem declarar validacao antes de executar.
6. Rodar a sequencia documentada em `docs/ROTEIRO_INTEGRACAO_PRIMEIRA_ENTREGA.md`.
7. Registrar evidencias reais em `docs/evidence/` somente depois dos testes.

## Comandos de execucao conhecidos

PostgreSQL, na area `backend-data`:

```powershell
cd backend
docker compose up -d postgres
```

API backend:

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Mosquitto, na area `iot-mqtt`:

```powershell
cd mqtt
docker compose --profile init run --rm mosquitto-init
docker compose up -d mosquitto
```

Consumidor MQTT do backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:HARPI_MQTT_ENABLED="true"
$env:HARPI_MQTT_HOST="localhost"
$env:HARPI_MQTT_PORT="1883"
$env:HARPI_MQTT_USERNAME="<usuario-mqtt-leitura>"
$env:HARPI_MQTT_PASSWORD="<senha-mqtt-leitura>"
$env:HARPI_MQTT_TELEMETRY_TOPIC="harpisense/v1/telemetry/+/+"
python -m app.mqtt_worker
```

Simulador MQTT:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r lab\legitimate-traffic\requirements.txt
$env:MQTT_HOST="127.0.0.1"
$env:MQTT_PORT="1883"
$env:MQTT_USERNAME="iot_device_lab"
$env:MQTT_PASSWORD="<senha-mqtt-publicacao>"
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --device poste-2 --count 3 --interval 1
```

ESP32 Poste 1:

```powershell
cd iot\esp32\poste1
Copy-Item include\config.example.h include\config.h
pio run
pio run --target upload
pio device monitor
```

Edge Security, alvo apos suporte a Basic do gateway:

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

## Python e ambiente virtual

- Python da area arquiteto/main: nao confirmado por execucao local.
- Ambientes virtuais documentados por area:
  - Backend: `backend/.venv`, ativacao `.\.venv\Scripts\Activate.ps1` a partir de `backend/`.
  - IoT/simulador: `.venv` na raiz da worktree de `iot-mqtt`, uso `.\.venv\Scripts\python`.
  - Edge: `.venv` na raiz da worktree de `edge-security`, uso `.venv/bin/python` em Linux.

## Commits relevantes

- `1907570de4ee161bf79a5059cef01611561f6a61` - `docs: prepare integration authentication plan`.
- `b87f592e178c899456fce8304a5cf90fb8999fb1` - `docs: prepare first delivery contracts`.
- `5a05547e58b1f3b4b3d8183e51374b1c4a26beef` - branch `backend-data`, `Implement backend ingestion base`.
- `dd2f07439ddc03b9fe6c7a39f66b3227a06de4ab` - branch `edge-security`, `Add backend delivery handling for network events`.
- `c7aa9e0cd759bb9367c948af4651abdf380c6cbf` - branch `iot-mqtt`, `Add IoT MQTT lab delivery`.
