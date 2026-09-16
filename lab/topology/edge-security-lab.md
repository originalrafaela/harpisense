# Topologia do laboratorio Edge Security

## Objetivo

Validar que trafego MQTT legitimo entre postes IoT e Mosquitto atravessa o gateway Linux inline antes de gerar eventos `network_event`.

## Topologia esperada

```text
Zona IoT protegida              Gateway Linux                  Zona teste/broker
ESP32/simuladores  <---->  eth-iot | roteamento | eth-test  <---->  Mosquitto/backend
192.168.20.0/24             harpisense.gateway.edge-1             192.168.30.0/24
```

Os nomes de interfaces e enderecos acima sao exemplos. A captura deve receber valores reais por argumento:

- Interfaces: `--iface eth-iot --iface eth-test`
- Rede IoT: `--iot-cidr 192.168.20.0/24`
- Rede teste/broker: `--test-cidr 192.168.30.0/24`
- Porta MQTT: `--mqtt-port 1883`
- Backend de ingestao: `--backend-url http://<backend>/api/v1/ingest/network-events`

## Verificacao de travessia

Para considerar que o trafego atravessou o gateway, a mesma chave de fluxo precisa aparecer nos dois lados configurados dentro da janela de agregacao:

- protocolo;
- IP e porta de origem;
- IP e porta de destino;
- direcao derivada dos CIDRs configurados;
- metadados MQTT visiveis quando houver.

Configurar duas interfaces no comando nao prova travessia por si so. O agregado registra `aggregation.traversal_evidence.observed_interfaces` com as interfaces que realmente observaram a chave de fluxo naquela janela. Quando apenas uma interface e observada, o evento continua sendo emitido, mas `aggregation.traversal_verified` fica `false` e `aggregation.traversal_reason` informa a interface ausente.

Limites desta verificacao:

- Ela prova observacao da mesma chave de fluxo nas interfaces configuradas durante a janela.
- Ela nao substitui validacao de roteamento/NAT do laboratorio.
- Se NAT alterar IP/porta entre as interfaces, a chave de fluxo pode nao casar e a travessia nao sera marcada como verificada.
- Trafego cifrado permite metadados IP/TCP, mas nao topico MQTT.

## Operacao permitida nesta etapa

- Capturar metadados de trafego legitimo.
- Persistir JSONL local como evidencia operacional.
- Enviar `network_event` ao backend pela rota contratada.

Nao permitido nesta etapa:

- Bloqueios reais.
- Alteracao de firewall para contencao.
- Regras apresentadas como deteccao ML treinada.
- Inferir autenticacao MQTT a partir de pacotes quando o broker nao forneceu logs.
