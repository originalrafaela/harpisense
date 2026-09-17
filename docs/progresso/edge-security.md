# Progresso - edge-security

Data: 2026-09-16

Pasta de trabalho: `D:\Projetos\harpisense-worktrees\edge-security`

Branch: `edge-security`

## Implementacao registrada

- Criada a primeira entrega da area de captura observacional em `edge/`.
- Implementado gerador de eventos `network_event` conforme contrato vigente em `docs/CONTRATOS_COMPARTILHADOS.md`.
- Implementada agregacao por janela configuravel em `edge/capture/aggregator.py`.
- Implementado parser MQTT conservador em `edge/capture/events.py`, sem inferir resultado de autenticacao.
- Implementado capturador Scapy configuravel em `edge/capture/scapy_gateway.py`.
- Implementado cliente HTTP de backend em `edge/capture/backend_client.py`.
- Entrega ao backend considera sucesso com HTTP `202 Accepted`, incluindo reenvio idempotente com `duplicate: true`.
- Falhas de envio, timeout, credencial ausente e status diferente de `202` sao registradas como nao entregues.
- Cliente HTTP ajustado para Basic obrigatorio do gateway via `HARPISENSE_BACKEND_USERNAME` e `HARPISENSE_BACKEND_PASSWORD`.
- Bearer foi removido da integracao de envio ao backend e nao ha fallback para envio sem autenticacao quando `--backend-url` estiver configurado.
- Documentada a topologia esperada em `lab/topology/edge-security-lab.md`.
- Atualizado `edge/README.md` com dependencias e comandos para Linux.
- Registrado status de captura em `docs/evidence/edge-security-capture-status.md`.
- Criados testes preparados em `tests/security/`.
- Adicionado processamento offline de PCAP em `edge/capture/offline_pcap.py`.
- A exportacao offline grava eventos brutos e janelas agregadas em JSONL separados, com `collection_session_id`, `format_version` e `collection_mode`.
- Eventos brutos usam `record_kind: raw_event`; janelas usam `record_kind: aggregate_window` e `event_type: network_window`.
- As janelas offline reutilizam `WindowAggregator` e sao baseadas em `observed_at` dos pacotes.
- Campos de autenticacao indisponiveis permanecem desconhecidos (`auth_result: unknown`, `auth_failure_count: null`).
- `network_window` permanece apenas na exportacao offline; o cliente HTTP recusa enviar registros que nao sejam `network_event` ao endpoint `/api/v1/ingest/network-events`.

Arquivos principais:

- `edge/capture/events.py`
- `edge/capture/aggregator.py`
- `edge/capture/scapy_gateway.py`
- `edge/capture/offline_pcap.py`
- `edge/capture/backend_client.py`
- `edge/README.md`
- `edge/requirements.txt`
- `lab/topology/edge-security-lab.md`
- `docs/evidence/edge-security-capture-status.md`
- `tests/security/test_capture_aggregation.py`
- `tests/security/test_backend_delivery.py`
- `tests/security/test_offline_pcap_export.py`

## Decisoes e contratos usados

- Contrato usado: `network_event` de `docs/CONTRATOS_COMPARTILHADOS.md`.
- Endpoint usado: `POST /api/v1/ingest/network-events`.
- Status de sucesso usado: `202 Accepted`.
- Classificacao da primeira entrega mantida como `classification.stage: raw_capture`, `label: unknown`, `confidence: null`.
- Nenhum bloqueio real foi implementado.
- Nenhuma regra foi apresentada como ML treinado.
- Nenhum resultado de autenticacao MQTT foi inferido de pacotes TCP.
- Eventos `mqtt_auth_event` permanecem dependentes de logs/exportador do Mosquitto.
- O contrato atualizado exige HTTP Basic para a credencial propria do gateway no `POST /api/v1/ingest/network-events`.
- O cliente Edge usa `HARPISENSE_BACKEND_USERNAME` e `HARPISENSE_BACKEND_PASSWORD`, conforme solicitado para a integracao da area.
- Nao foi alterado `docs/CONTRATOS_COMPARTILHADOS.md`; `network_window` e `format_version` continuam fora do endpoint de ingestao.
- `409 identifier_conflict` deve ser tratado como falha; a Edge nao altera `event_id` para contornar conflito.

## Validacao realmente executada

- `git diff --cached --check`: passou antes dos commits.
- `py_compile` executado com:

```powershell
$env:PYTHONHOME='C:\Program Files\NVIDIA Corporation\Nsight Systems 2025.5.2\host-windows-x64\python'
& 'C:\Program Files\NVIDIA Corporation\Nsight Systems 2025.5.2\host-windows-x64\python\bin\python.exe' -m py_compile edge\capture\backend_client.py edge\capture\aggregator.py edge\capture\events.py edge\capture\scapy_gateway.py tests\security\test_capture_aggregation.py tests\security\test_backend_delivery.py
```

Resultado: passou sem saida.

Validacao adicional em 2026-09-17:

- `git diff --check`: passou, com avisos esperados de conversao LF/CRLF.
- Parse sintatico com `ast.parse` para `edge/capture/backend_client.py`, `edge/capture/aggregator.py`, `edge/capture/events.py`, `edge/capture/scapy_gateway.py`, `edge/capture/offline_pcap.py` e testes em `tests/security`: passou.
- Smoke test direto de `export_offline_observations`: passou, validando ordenacao temporal, contagem de eventos/janelas, campos offline de autenticacao desconhecidos e `traversal_verified: false` quando falta interface esperada.

Validacao adicional em 2026-09-17 apos merge da `main`:

- Parse sintatico com `ast.parse` para modulos e testes da area: passou.
- Smoke test direto do cliente HTTP com backend simulado: passou para Basic, `202 duplicate=false`, `202 duplicate=true`, credencial ausente, recusa de `network_window` e falhas `401`, `403`, `409 identifier_conflict` e `503`.
- Estes testes continuam sendo simulacao local, nao integracao real com `backend-data`.

## Testes nao executados, bloqueios e dependencias

- `python -m unittest discover -s tests/security -p "test_*.py"` nao foi executado com sucesso neste host.
- `python` nao existe no PATH.
- Tentativa de `unittest discover` com o Python embarcado do Nsight Systems em 2026-09-17 falhou com `No module named unittest`.
- `py` existe em `C:\Windows\py.exe`, mas retornou `No installed Python found!`.
- Pythons encontrados fora do PATH:
  - `C:\Program Files\NVIDIA Corporation\Nsight Systems 2025.5.2\host-windows-x64\python\bin\python.exe` - Python 3.12.4, mas sem modulo `unittest`.
  - `C:\Program Files\NVIDIA Corporation\Nsight Compute 2025.4.1\host\target-windows-x64\python\bin\python.exe` - Python 3.12.4, mas sem modulo `unittest`.
  - `C:\Program Files\MySQL\MySQL Workbench 8.0\python.exe` - Python 3.11.7 embarcado, mas sem `unittest` utilizavel neste contexto.
- Tentativa de criar venv temporario com Python da NVIDIA nao concluiu e foi interrompida.
- Captura real com Scapy nao foi executada porque a VM Linux/gateway com interfaces reais nao esta disponivel neste host.
- Integracao real com backend nao foi executada; os testes preparados usam backend HTTP simulado.

## Trabalho incompleto e alinhamentos pendentes

- Executar testes `unittest` em Python completo.
- Validar captura real na VM Linux com duas interfaces e trafego MQTT legitimo.
- Validar envio real ao backend `backend-data` e consulta posterior em `GET /api/v1/network-events`.
- Validar no backend real que `POST /api/v1/ingest/network-events` aceita Basic do gateway e retorna `202`, `duplicate: true`, `401`, `403`, `409` e `503` conforme contrato.
- Se houver NAT entre interfaces do gateway, revisar a chave de fluxo usada para `traversal_verified`, pois alteracao de IP/porta pode impedir o casamento.

## Proximos passos

1. Preparar ambiente Python completo na VM Linux:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv tcpdump
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r edge/requirements.txt
```

2. Executar testes locais com backend simulado:

```bash
. .venv/bin/activate
python -m unittest discover -s tests/security -p 'test_*.py'
```

3. Identificar interfaces e rotas no gateway:

```bash
ip -brief address
ip route
```

4. Capturar trafego MQTT legitimo, ajustando interfaces, CIDRs e backend reais:

```bash
sudo .venv/bin/python -m edge.capture.scapy_gateway \
  --iface <iot-iface> \
  --iface <test-iface> \
  --iot-cidr <iot-cidr> \
  --test-cidr <test-cidr> \
  --broker-host <broker-ip> \
  --mqtt-port 1883 \
  --window-seconds 30 \
  --backend-url http://<backend-host>:<port>/api/v1/ingest/network-events \
  --backend-timeout-seconds 5 \
  --output-jsonl edge/capture/network-events.jsonl \
  --delivery-jsonl edge/capture/network-event-delivery.jsonl \
  --duration-seconds 120
```

5. Verificar eventos e entregas:

```bash
tail -n 5 edge/capture/network-events.jsonl
tail -n 5 edge/capture/network-event-delivery.jsonl
curl 'http://<backend-host>:<port>/api/v1/network-events?limit=5'
```

6. Configurar credenciais Basic do gateway por variaveis de ambiente, sem versionar segredos:

```bash
export HARPISENSE_BACKEND_USERNAME='<gateway-id>'
export HARPISENSE_BACKEND_PASSWORD='<gateway-secret>'
sudo --preserve-env=HARPISENSE_BACKEND_USERNAME,HARPISENSE_BACKEND_PASSWORD .venv/bin/python -m edge.capture.scapy_gateway \
  --backend-url http://<backend-host>:<port>/api/v1/ingest/network-events \
  --iface <iot-iface> \
  --iface <test-iface>
```

## Commits relevantes

- `7af836096de4a92b0238aac7f479e15d53a0ee13` - `Implement edge traffic capture pipeline`
- `dd2f07439ddc03b9fe6c7a39f66b3227a06de4ab` - `Add backend delivery handling for network events`
