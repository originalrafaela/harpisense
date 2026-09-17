# Progresso - arquiteto

## Encerramento do dia - 2026-09-17

Estado Git confirmado no encerramento:

- Diretorio do projeto: `D:\Projetos\tcc - harpisense`.
- Branch atual: `main`.
- Remote `origin`: `https://github.com/originalrafaela/harpisense.git`.
- `main` estava alinhada com `origin/main` antes desta atualizacao de encerramento.
- Nenhum merge das branches de area foi feito nesta rodada.
- Nenhuma implementacao nova foi criada nesta rodada.

Commits documentais da `main` ja publicados antes deste encerramento:

- `332cb600e850e7d4e8b47c0240da8fe4ac0f1321` - `docs: prepare HarpiSense integration auth`.
- `82481f69f543b5246b571a334815484d89d89b52` - `docs: finalize integration contracts`.

Commits conhecidos das outras areas, lidos sem checkout:

- `backend-data`: `f142aaeb819d80bace6f272b1f157a2e055fba54` - `Harden backend ingestion idempotency`.
- `edge-security`: `b48c9dc649b85ff782b0fa21f379948e72ad02c6` - `Add offline PCAP export pipeline`.
- `iot-mqtt`: `d92120c68fda7395ab73b03e8011ac426d3c3ddd` - `Expand synthetic MQTT simulator`.

Trabalho realmente revisado por mim:

- Documentos vigentes em `docs/`, especialmente:
  - `docs/CONTRATOS_COMPARTILHADOS.md`;
  - `docs/ROTEIRO_INTEGRACAO_PRIMEIRA_ENTREGA.md`;
  - `docs/DECISOES_ARQUITETURAIS.md`;
  - `docs/PLANO_PRIMEIRA_ENTREGA.md`;
  - `docs/AREAS_DE_TRABALHO.md`.
- Trechos de implementacao lidos nas branches:
  - Backend: autenticacao Basic administrativa, configuracao, rotas de ingestao, schemas, servicos de idempotencia, consumidor MQTT e handlers de erro.
  - Edge: cliente HTTP, captura Scapy, agregador, construcao de `network_event` e exportacao offline de PCAP.
  - IoT/MQTT: Compose do Mosquitto, ACL, exemplo de usuarios, script de geracao de password file, contrato MQTT e simulador sintetico.
- Validacoes executadas por mim nesta frente:
  - `git branch --show-current`;
  - `git status --short --branch`;
  - `git remote -v`;
  - `git diff --check`;
  - revisao de diff documental antes dos commits;
  - `git push origin main` apos os commits documentais anteriores.

Trabalho relatado pelos agentes ou branches, mas nao validado por mim ponta a ponta:

- `backend-data` relata FastAPI, PostgreSQL/Alembic, ingestao, consultas, idempotencia e consumidor MQTT.
- `edge-security` relata captura, agregacao, envio HTTP e processamento offline de PCAP.
- `iot-mqtt` relata Mosquitto, ACLs, simulador, firmware ESP32 e smoke tests.
- Nenhum desses fluxos foi executado por mim em ambiente real integrado.
- Entregas do backend permanecem pendentes ate confirmacao com execucao local ou evidencias:
  - migracoes Alembic em PostgreSQL real;
  - API subindo com `.env` local;
  - Basic administrativo;
  - Basic separado do gateway;
  - `409 identifier_conflict`;
  - validacao e persistencia de `aggregation`;
  - consumidor MQTT persistindo telemetria vinda do Mosquitto;
  - consultas reais em `GET /api/v1/telemetry` e `GET /api/v1/network-events`.

Decisoes vigentes e contratos finalizados:

- Administrador unico, sem RBAC, multiplos perfis, cadastro publico ou autoinscricao nesta etapa.
- BitNet local permanece fora do caminho critico e sera usado apenas para explicar incidentes ja detectados em etapa posterior.
- Modos mantidos:
  - IDS: detecta, registra e alerta, sem bloquear.
  - IPS supervisionado: recomenda bloqueio e exige aprovacao explicita do administrador.
  - IPS autonomo: resposta automatica futura dentro de limites de politica, whitelist, duracao, escopo e auditoria.
- Primeira entrega continua limitada a publicacao MQTT, trafego legitimo atravessando o gateway, persistencia e consulta pela API.
- Fora da primeira entrega: ML treinado, inferencia online, SHAP/XAI, bloqueio real, dashboard completo, AWS e BitNet integrado.
- Autenticacao HTTP:
  - Administrador: `HARPI_ADMIN_USERNAME` e `HARPI_ADMIN_PASSWORD`.
  - Gateway no backend: `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`.
  - Cliente Edge: `HARPISENSE_BACKEND_USERNAME` e `HARPISENSE_BACKEND_PASSWORD`.
  - Gateway so pode acessar `POST /api/v1/ingest/network-events`.
  - Gateway nao pode consultar endpoints administrativos.
  - Bearer opcional da Edge nao deve ser usado contra o backend atual.
  - Ingestao sem autenticacao nao e solucao aceita.
  - HTTP Basic nao cifra credenciais; fora de laboratorio isolado exige HTTPS/TLS ou tunel equivalente.
- Idempotencia:
  - primeira persistencia valida: `202 Accepted`, `duplicate: false`;
  - reenvio identico: `202 Accepted`, `duplicate: true`;
  - mesmo identificador com conteudo diferente: `409 Conflict`, `error.code = "identifier_conflict"`;
  - telemetria compara conteudo canonico de `message_id`, excluindo `id`, `received_at` e metadados de banco;
  - eventos de rede comparam conteudo canonico de `event_id`, incluindo `aggregation` quando presente e excluindo metadados gerados pelo servidor.
- `aggregation` produzido pela Edge em `network_event` deve ser aceito, validado e persistido pelo backend.
- `aggregation` invalido deve retornar `422`; descarte silencioso esta proibido.
- `network_window` permanece exportacao offline JSONL nesta entrega; nao ha endpoint de ingestao de janelas.
- MQTT:
  - consumidor backend deve usar usuario dedicado `harpisense_backend_consumer`;
  - permissao somente de leitura/assinatura em `harpisense/v1/telemetry/#`;
  - variaveis do consumidor: `HARPI_MQTT_HOST`, `HARPI_MQTT_PORT`, `HARPI_MQTT_USERNAME`, `HARPI_MQTT_PASSWORD`, `HARPI_MQTT_TELEMETRY_TOPIC`;
  - provisionamento do broker deve adicionar usuario local e ACL correspondente, sem credenciais reais versionadas.
- Regras preservadas:
  - timestamps ISO 8601 UTC com sufixo `Z`;
  - `observed_at` vem do produtor/observacao;
  - `received_at` vem do backend;
  - valores desconhecidos podem ser `null` ou omitidos;
  - `measurements` nao pode ser objeto vazio;
  - consumidor MQTT deve validar topico contra `device_id` e `sensor_type`.

Pendencias de integracao para amanha:

- Confirmar se as branches locais de area devem ser publicadas antes da integracao.
- Integrar ou preparar PRs sem perder os commits locais das areas.
- Backend:
  - implementar ou confirmar `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`;
  - separar autenticacao de gateway da autenticacao administrativa;
  - negar consultas administrativas ao gateway;
  - validar e persistir `aggregation`;
  - manter e testar `409 identifier_conflict`;
  - confirmar migracoes, API, ingestao e consultas em execucao real.
- Edge:
  - substituir uso real de Bearer/sem credencial por Basic com `HARPISENSE_BACKEND_USERNAME` e `HARPISENSE_BACKEND_PASSWORD`;
  - manter `network_window` apenas offline;
  - confirmar interfaces, CIDRs e travessia real do fluxo.
- IoT/MQTT:
  - adicionar `harpisense_backend_consumer` ao provisionamento e ACL;
  - validar broker, simulador e subscriber;
  - definir sensor fisico e pinagem do ESP32;
  - validar NTP do ESP32 antes de aceitar evidencias reais.
- Integracao:
  - subir PostgreSQL;
  - subir API;
  - subir Mosquitto;
  - iniciar consumidor MQTT;
  - publicar telemetria simulada e, quando houver hardware, Poste 1;
  - executar Edge no gateway;
  - consultar telemetria e eventos persistidos;
  - registrar evidencias reais em `docs/evidence/` somente depois da execucao.

Primeiro passo recomendado para amanha:

1. Comecar por `backend-data`: aplicar o contrato final de autenticacao do gateway e `aggregation`, rodar testes/unitarios disponiveis e confirmar a API com PostgreSQL local antes de tentar a integracao ponta a ponta.

## Atualizacao em 2026-09-17 - contratos fechados para implementacao

Rodada documental na `main`, sem merge das branches de area e sem validacao real.

Branches locais mais recentes lidas sem checkout:

- `backend-data` em `f142aaeb819d80bace6f272b1f157a2e055fba54` (`Harden backend ingestion idempotency`).
- `edge-security` em `b48c9dc649b85ff782b0fa21f379948e72ad02c6` (`Add offline PCAP export pipeline`).
- `iot-mqtt` em `d92120c68fda7395ab73b03e8011ac426d3c3ddd` (`Expand synthetic MQTT simulator`).

Implementacoes conferidas nesta rodada:

- `backend-data`:
  - `backend/app/services/telemetry.py` compara conteudo existente e novo para `message_id`.
  - `backend/app/services/security_events.py` compara `payload` persistido e novo para `event_id`.
  - `backend/app/services/idempotency.py` define `IdentifierConflictError`.
  - `backend/app/api/errors.py` transforma conflito em `409` com `error.code = "identifier_conflict"`.
  - `backend/app/api/v1/routes/ingest.py` ainda aplica `require_admin` ao router inteiro.
  - `backend/app/core/config.py` ainda nao possui `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`.
  - `backend/app/schemas/security_event.py` ainda nao declara `aggregation`.
- `edge-security`:
  - `edge/capture/aggregator.py` produz `aggregation` em `network_event`.
  - `edge/capture/events.py` adiciona `aggregation` ao evento quando fornecido.
  - `edge/capture/offline_pcap.py` exporta `network_event` bruto e `network_window` offline em JSONL.
  - `edge/README.md` ainda documenta Bearer opcional e envio sem credencial por padrao.
- `iot-mqtt`:
  - `mqtt/config/lab-users.example` ainda contem `iot_device_lab` e `mqtt_test_subscriber`, sem `harpisense_backend_consumer`.
  - `mqtt/config/aclfile` ainda nao declara ACL do usuario dedicado do backend.
  - `mqtt/config/create-password-file.sh` provisiona usuarios a partir de linhas `username:password`.
  - `lab/legitimate-traffic/simulate_poste.py` foi expandido para multiplos postes, duracao, seed e JSONL local.

Decisoes fechadas:

- HTTP Basic separado:
  - Administrador: `HARPI_ADMIN_USERNAME` e `HARPI_ADMIN_PASSWORD`.
  - Gateway no backend: `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`.
  - Cliente Edge: `HARPISENSE_BACKEND_USERNAME` e `HARPISENSE_BACKEND_PASSWORD`, com valores correspondentes aos do gateway.
- Gateway so pode acessar `POST /api/v1/ingest/network-events`; nao pode consultar endpoints administrativos.
- Basic nao cifra credenciais; HTTPS/TLS ou tunel equivalente e obrigatorio fora de laboratorio isolado.
- Idempotencia:
  - primeira persistencia ou reenvio identico: `202 Accepted`;
  - reenvio identico: `duplicate: true`;
  - mesmo identificador com conteudo diferente: `409 Conflict`, `error.code = "identifier_conflict"`.
- Comparacao de idempotencia exclui metadados gerados pelo servidor, como `id`, `received_at`, colunas derivadas e metadados de banco.
- `aggregation` produzido pela Edge em `network_event` deve ser aceito, validado e persistido nesta entrega.
- `aggregation` invalido deve retornar `422`; descarte silencioso esta proibido.
- `network_window` permanece exportacao offline JSONL; nao ha endpoint de ingestao de janelas nesta entrega.
- Usuario MQTT dedicado definido: `harpisense_backend_consumer`, somente leitura em `harpisense/v1/telemetry/#`.
- Mantidas regras existentes: valores desconhecidos podem ser `null` ou omitidos; `measurements` nao pode ser vazio; consumidor MQTT deve validar topico contra `device_id` e `sensor_type`.

Documentos atualizados:

- `docs/CONTRATOS_COMPARTILHADOS.md`: permissoes por endpoint, respostas de autenticacao, nota de Basic/HTTPS, idempotencia completa, tratamento de `aggregation`, `network_window` offline e usuario MQTT dedicado.
- `docs/ROTEIRO_INTEGRACAO_PRIMEIRA_ENTREGA.md`: roteiro ajustado para `harpisense_backend_consumer`, Basic do gateway, 409 de idempotencia, validacao/persistencia de `aggregation` e verificacao negativa de permissao do gateway.

Implementacoes ainda necessarias por area:

- `backend-data`: adicionar `HARPI_GATEWAY_USERNAME` e `HARPI_GATEWAY_PASSWORD`; separar dependencia de autenticacao do gateway em `POST /api/v1/ingest/network-events`; negar consultas administrativas ao gateway; validar e persistir `aggregation`; manter `409 identifier_conflict`.
- `edge-security`: trocar a integracao real de Bearer opcional/sem credencial para HTTP Basic com `HARPISENSE_BACKEND_USERNAME` e `HARPISENSE_BACKEND_PASSWORD`; nao enviar `network_window` a API; manter `network_window` offline.
- `iot-mqtt`: adicionar `harpisense_backend_consumer` ao provisionamento local de usuarios e ACL com somente `topic read harpisense/v1/telemetry/#`; manter publicadores sem permissao de leitura/consulta administrativa.

Validacao:

- Nao foi executada integracao real.
- `git diff --check` executado nesta rodada; apenas avisos LF/CRLF esperados no Windows, sem erro de whitespace.

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
