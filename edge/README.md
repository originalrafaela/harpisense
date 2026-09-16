# HarpiSense Edge Security

Primeira entrega da area `edge-security`: captura observacional de metadados de trafego MQTT legitimo no gateway Linux, geracao de eventos `network_event` e agregacao por janela configuravel.

Esta etapa nao executa bloqueios, nao aciona firewall, nao treina ML e nao apresenta classificacao alem de `raw_capture` com `label: unknown`.

## Contrato de backend

O contrato vigente define HTTP `POST /api/v1/ingest/network-events` e sucesso somente com `202 Accepted`. Os documentos em `docs/` nao definem autenticacao obrigatoria para este endpoint. Por isso, o capturador envia sem credencial por padrao e aceita token bearer opcional apenas se isso for acordado com `backend-data`/Arquiteto.

O evento capturado e sempre gravado no JSONL local. A entrega ao backend e registrada separadamente em `network-event-delivery.jsonl`:

- `backend_delivered: true`: somente quando o backend respondeu `202`.
- `backend_delivered: false`: timeout, falha de conexao ou qualquer status diferente de `202`.

## Dependencias

No gateway Linux:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv tcpdump
```

`tcpdump` fornece suporte/libpcap para filtros BPF usados pelo Scapy em muitas distribuicoes.

Crie um ambiente isolado a partir da raiz do repositorio:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r edge/requirements.txt
```

## Testes locais

Os testes em `tests/security` usam entradas conhecidas e backend HTTP simulado. Eles validam agregacao, parser MQTT conservador e falha/sucesso de envio ao backend simulado. Nao sao integracao real com backend `backend-data`.

```bash
. .venv/bin/activate
python -m unittest discover -s tests/security -p 'test_*.py'
```

## Selecionar interfaces no Linux

Liste interfaces e enderecos:

```bash
ip -brief address
ip route
```

Escolha uma interface do lado IoT e outra do lado teste/broker. Configure os CIDRs reais do laboratorio nos argumentos `--iot-cidr` e `--test-cidr`.

## Executar captura MQTT legitima

Exemplo com duas interfaces do gateway:

```bash
sudo .venv/bin/python -m edge.capture.scapy_gateway \
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

Se houver token bearer acordado posteriormente, nao versione o segredo. Use variavel de ambiente ou arquivo local ignorado pelo Git, como `.env.edge-backend-token` contendo apenas o token:

```bash
export HARPISENSE_BACKEND_TOKEN='<token-fornecido-fora-do-git>'
sudo --preserve-env=HARPISENSE_BACKEND_TOKEN .venv/bin/python -m edge.capture.scapy_gateway \
  --iface eth-iot \
  --iface eth-test \
  --iot-cidr 192.168.20.0/24 \
  --test-cidr 192.168.30.0/24 \
  --broker-host 192.168.30.20 \
  --mqtt-port 1883 \
  --window-seconds 30 \
  --backend-url http://127.0.0.1:8000/api/v1/ingest/network-events \
  --backend-token-env HARPISENSE_BACKEND_TOKEN \
  --output-jsonl edge/capture/network-events.jsonl \
  --delivery-jsonl edge/capture/network-event-delivery.jsonl \
  --duration-seconds 120
```

Alternativa com arquivo local ignorado por `.gitignore`:

```bash
sudo .venv/bin/python -m edge.capture.scapy_gateway \
  --iface eth-iot \
  --iface eth-test \
  --iot-cidr 192.168.20.0/24 \
  --test-cidr 192.168.30.0/24 \
  --mqtt-port 1883 \
  --backend-url http://127.0.0.1:8000/api/v1/ingest/network-events \
  --backend-token-file .env.edge-backend-token \
  --duration-seconds 120
```

Nao configure firewall nem execute bloqueios nesta etapa.

## Verificar eventos e entrega

Inspecione os eventos capturados:

```bash
tail -n 5 edge/capture/network-events.jsonl
```

Inspecione confirmacoes de envio:

```bash
tail -n 5 edge/capture/network-event-delivery.jsonl
```

Confirme que a API do backend lista o evento persistido, quando a integracao real estiver disponivel:

```bash
curl 'http://127.0.0.1:8000/api/v1/network-events?limit=5'
```

Esse `curl` verifica a consulta real do backend; os testes automatizados desta area foram escritos com backend simulado e devem ser descritos como simulacao.

Use `--iface` uma vez para cada lado observado do gateway. A verificacao de travessia so fica verdadeira quando a mesma chave de fluxo aparece nas interfaces esperadas dentro da mesma janela de agregacao. Configurar duas interfaces nao basta: `aggregation.traversal_evidence.observed_interfaces` precisa conter as interfaces onde o fluxo foi realmente observado, e `aggregation.traversal_verified` permanece `false` se uma delas nao aparecer.

## Campos do evento

Campos vindos dos pacotes capturados:

- `capture.interface`: interface Scapy onde o pacote foi observado.
- `capture.direction`: derivado dos CIDRs configurados em `--iot-cidr` e `--test-cidr`.
- `capture.protocol`, `src_ip`, `dst_ip`, portas, tamanho e `tcp_flags`: cabecalhos IP/TCP/UDP.
- `mqtt.present`, `mqtt.message_type` e `mqtt.topic`: extraidos do payload MQTT quando trafego nao cifrado estiver visivel.
- `mqtt.client_id`: extraido apenas de pacotes MQTT `CONNECT` visiveis; em `PUBLISH`, normalmente permanece `null`.

Campos que dependem de logs do Mosquitto ou exportador do broker:

- Resultado de autenticacao (`success` ou `failure`).
- Motivo de falha de autenticacao.
- Username autenticado.
- Relacao confiavel entre um `client_id` e sessoes posteriores quando o pacote `CONNECT` nao foi observado na janela.

O capturador nao inventa resultado de autenticacao a partir de pacotes TCP. Eventos `mqtt_auth_event` devem vir do broker/exportador quando essa frente estiver disponivel.

## Agregacao

`--window-seconds` controla o tamanho da janela. Dentro de cada janela, os pacotes sao agrupados por protocolo, origem, destino, portas, direcao e metadados MQTT visiveis. O evento resultante adiciona:

- `aggregation.packet_count`
- `aggregation.total_packet_size_bytes`
- `aggregation.interfaces_observed`
- `aggregation.expected_interfaces`
- `aggregation.traversal_verified`
- `aggregation.traversal_reason`

`capture.packet_size_bytes` representa o total de bytes agregados naquele evento.
