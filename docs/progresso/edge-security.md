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
- Entrega ao backend considera sucesso somente com HTTP `202 Accepted`.
- Falhas de envio, timeout e status diferente de `202` sao registradas como nao entregues.
- URL do backend, timeout e token bearer opcional sao configuraveis por argumento.
- Credenciais nao foram versionadas; nomes suportados: `HARPISENSE_BACKEND_TOKEN` ou arquivo local passado por `--backend-token-file`.
- Documentada a topologia esperada em `lab/topology/edge-security-lab.md`.
- Atualizado `edge/README.md` com dependencias e comandos para Linux.
- Registrado status de captura em `docs/evidence/edge-security-capture-status.md`.
- Criados testes preparados em `tests/security/`.
- Adicionado processamento offline de PCAP em `edge/capture/offline_pcap.py`.
- A exportacao offline grava eventos brutos e janelas agregadas em JSONL separados, com `collection_session_id`, `format_version` e `collection_mode`.
- Eventos brutos usam `record_kind: raw_event`; janelas usam `record_kind: aggregate_window` e `event_type: network_window`.
- As janelas offline reutilizam `WindowAggregator` e sao baseadas em `observed_at` dos pacotes.
- Campos de autenticacao indisponiveis permanecem desconhecidos (`auth_result: unknown`, `auth_failure_count: null`).

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
- Os contratos vigentes nao definem autenticacao obrigatoria para ingestao de `network_event`; token bearer foi deixado opcional para alinhamento futuro.
- Nao foi alterado `docs/CONTRATOS_COMPARTILHADOS.md`; se `network_window` ou `format_version` precisarem virar contrato compartilhado, a proposta deve ser levada ao Arquiteto.

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

## Testes nao executados, bloqueios e dependencias

- `python -m unittest discover -s tests/security -p "test_*.py"` nao foi executado com sucesso neste host.
- `python` nao existe no PATH.
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
- Alinhar com Arquiteto/backend se o endpoint de ingestao exigira autenticacao; contrato atual nao especifica obrigatoriedade nem formato.
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

6. Se autenticacao for acordada, usar apenas nome de variavel ou arquivo local nao versionado:

```bash
export HARPISENSE_BACKEND_TOKEN='<valor-fora-do-git>'
sudo --preserve-env=HARPISENSE_BACKEND_TOKEN .venv/bin/python -m edge.capture.scapy_gateway \
  --backend-token-env HARPISENSE_BACKEND_TOKEN \
  --backend-url http://<backend-host>:<port>/api/v1/ingest/network-events \
  --iface <iot-iface> \
  --iface <test-iface>
```

## Commits relevantes

- `7af836096de4a92b0238aac7f479e15d53a0ee13` - `Implement edge traffic capture pipeline`
- `dd2f07439ddc03b9fe6c7a39f66b3227a06de4ab` - `Add backend delivery handling for network events`
