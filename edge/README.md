# HarpiSense Edge Security

Primeira entrega da area `edge-security`: captura observacional de metadados de trafego MQTT legitimo no gateway Linux, geracao de eventos `network_event` e agregacao por janela configuravel.

Esta etapa nao executa bloqueios, nao aciona firewall, nao treina ML e nao apresenta classificacao alem de `raw_capture` com `label: unknown`.

## Execucao no gateway

Instale Scapy no ambiente do gateway Linux:

```bash
python -m pip install scapy
```

Exemplo com duas interfaces do gateway:

```bash
python -m edge.capture.scapy_gateway \
  --iface eth-iot \
  --iface eth-test \
  --iot-cidr 192.168.20.0/24 \
  --test-cidr 192.168.30.0/24 \
  --broker-host 192.168.30.20 \
  --mqtt-port 1883 \
  --window-seconds 30 \
  --backend-url http://127.0.0.1:8000/api/v1/ingest/network-events \
  --output-jsonl edge/capture/network-events.jsonl \
  --duration-seconds 120
```

Use `--iface` uma vez para cada lado observado do gateway. A verificacao de travessia so fica verdadeira quando o mesmo fluxo agregado aparece nas interfaces esperadas dentro da mesma janela.

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
