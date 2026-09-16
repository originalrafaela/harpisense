# Evidencia de captura - edge-security

Data: 2026-09-16

## Estado do laboratorio

Nao ha VM/interface de gateway Linux disponivel neste ambiente de trabalho para executar Scapy contra trafego real. Por isso, nao foi registrada captura real de laboratorio nesta etapa.

## Preparado sem laboratorio

- Contrato `network_event` preservado para eventos gerados.
- `classification.stage` permanece `raw_capture`.
- `classification.label` permanece `unknown`.
- Ha teste automatizado preparado para agregacao por janela com entradas conhecidas.
- Ha teste automatizado preparado para verificacao de travessia com entradas conhecidas observadas em duas interfaces configuradas.
- Ha teste automatizado preparado para o caso de uma unica interface nao declarar travessia.
- Ha teste automatizado preparado para parser MQTT extrair topico de `PUBLISH` sem inventar resultado de autenticacao.
- Envio ao backend preparado via HTTP `POST /api/v1/ingest/network-events`, com entrega confirmada apenas em `202 Accepted`.
- Ha testes automatizados preparados para falha HTTP e falha de conexao com backend simulado.

## Execucao de testes neste host

Em 2026-09-16, os testes nao foram executados com sucesso neste host porque nao ha Python completo disponivel no PATH. Foram encontrados runtimes embarcados em ferramentas de terceiros, mas eles nao incluem `unittest`; uma tentativa de criar venv temporario com o Python da NVIDIA nao concluiu. A execucao deve ser repetida com Python completo na VM Linux ou em ambiente local adequado.

## Contrato pendente

Os contratos vigentes nao definem autenticacao obrigatoria para o endpoint de ingestao de eventos de rede. O capturador suporta token bearer opcional por variavel de ambiente ou arquivo local, mas a exigencia e o formato final de autenticacao precisam ser alinhados pelo Arquiteto com `backend-data` antes de serem tratados como obrigatorios.

## Pendencia externa

Executar no gateway Linux real com duas interfaces configuradas e trafego MQTT legitimo atravessando o caminho:

```bash
python -m edge.capture.scapy_gateway --iface <iot-iface> --iface <test-iface> --iot-cidr <iot-cidr> --test-cidr <test-cidr> --mqtt-port 1883 --duration-seconds 120
```

Anexar o JSONL gerado e/ou resumo do backend quando a VM e as interfaces estiverem disponiveis.
