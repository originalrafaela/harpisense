# Evidencia de captura - edge-security

Data: 2026-09-16

## Estado do laboratorio

Nao ha VM/interface de gateway Linux disponivel neste ambiente de trabalho para executar Scapy contra trafego real. Por isso, nao foi registrada captura real de laboratorio nesta etapa.

## Validado sem laboratorio

- Contrato `network_event` preservado para eventos gerados.
- `classification.stage` permanece `raw_capture`.
- `classification.label` permanece `unknown`.
- Agregacao por janela validada com entradas conhecidas em teste automatizado.
- Verificacao de travessia validada com entradas conhecidas observadas em duas interfaces configuradas.
- Caso de uma unica interface validado para nao declarar travessia.
- Parser MQTT validado para extrair topico de `PUBLISH` sem inventar resultado de autenticacao.

## Pendencia externa

Executar no gateway Linux real com duas interfaces configuradas e trafego MQTT legitimo atravessando o caminho:

```bash
python -m edge.capture.scapy_gateway --iface <iot-iface> --iface <test-iface> --iot-cidr <iot-cidr> --test-cidr <test-cidr> --mqtt-port 1883 --duration-seconds 120
```

Anexar o JSONL gerado e/ou resumo do backend quando a VM e as interfaces estiverem disponiveis.
