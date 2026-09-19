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
- Ha processamento offline de PCAP preparado em `edge.capture.offline_pcap`, reutilizando `packet_to_observation` e `WindowAggregator`.
- A exportacao offline separa eventos brutos (`network_event`) de janelas agregadas (`network_window`) e carimba `collection_session_id` e `format_version`.
- Campos de autenticacao extraidos da captura permanecem desconhecidos (`auth_result: unknown`, `auth_failure_count: null`) porque pacotes TCP/MQTT visiveis nao comprovam sucesso ou falha de autenticacao.

## Execucao de testes neste host

Em 2026-09-16, os testes nao foram executados com sucesso neste host porque nao ha Python completo disponivel no PATH. Foram encontrados runtimes embarcados em ferramentas de terceiros, mas eles nao incluem `unittest`; uma tentativa de criar venv temporario com o Python da NVIDIA nao concluiu. A execucao deve ser repetida com Python completo na VM Linux ou em ambiente local adequado.

Em 2026-09-17, `python -m unittest discover -s tests/security -p "test_*.py"` continuou pendente porque `python` nao esta no PATH. Foram executadas checagens alternativas com o Python embarcado do Nsight Systems:

- Parse sintatico com `ast.parse` dos modulos e testes da area: passou.
- Smoke test direto de `export_offline_observations`, validando ordenacao temporal, janelas separadas, campos de autenticacao desconhecidos e travessia nao comprovada: passou.

## Contrato pendente

Os contratos vigentes nao definem autenticacao obrigatoria para o endpoint de ingestao de eventos de rede. O capturador suporta token bearer opcional por variavel de ambiente ou arquivo local, mas a exigencia e o formato final de autenticacao precisam ser alinhados pelo Arquiteto com `backend-data` antes de serem tratados como obrigatorios.

## Pendencia externa

Executar no gateway Linux real com duas interfaces configuradas e trafego MQTT legitimo atravessando o caminho:

```bash
python -m edge.capture.scapy_gateway --iface <iot-iface> --iface <test-iface> --iot-cidr <iot-cidr> --test-cidr <test-cidr> --mqtt-port 1883 --duration-seconds 120
```

Anexar o JSONL gerado e/ou resumo do backend quando a VM e as interfaces estiverem disponiveis.

Validar tambem o processamento offline com PCAP real da VM Linux quando os arquivos estiverem disponiveis:

```bash
python -m edge.capture.offline_pcap --pcap <arquivo.pcap> --pcap-interface <iface> --iface <iface> --iot-cidr <iot-cidr> --test-cidr <test-cidr>
```
