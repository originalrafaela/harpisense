# HarpiSense - Plano da primeira entrega

Objetivo da primeira entrega: provar o caminho basico de dados do HarpiSense sem assumir funcionalidades futuras como prontas.

## Demonstracao esperada

Ao final da primeira entrega, deve ser possivel demonstrar:

1. Poste 1 fisico com ESP32 publicando telemetria MQTT.
2. Postes simulados publicando telemetria MQTT em topicos separados.
3. Trafego MQTT legitimo atravessando o gateway.
4. Gateway capturando metadados do trafego legitimo.
5. Backend recebendo e persistindo telemetria de sensores.
6. Backend recebendo e persistindo eventos de rede.
7. API consultando telemetria e eventos de rede persistidos.

## Nao objetivos desta entrega

- Treinar modelos de ML.
- Executar inferencia com modelo treinado.
- Implementar SHAP/XAI.
- Implementar bloqueios reais no firewall.
- Implementar aprovacao/rejeicao de bloqueio no produto.
- Implementar dashboard completo.
- Integrar AWS.
- Integrar BitNet.
- Implementar multiplos usuarios, perfis, RBAC ou cadastro publico.

## Sequencia sugerida

1. Validar topologia local e dependencias de hardware/VM.
2. Implementar publicadores MQTT do ESP32 e simuladores.
3. Configurar broker Mosquitto de laboratorio.
4. Validar publicacao e assinatura de telemetria.
5. Configurar gateway no caminho do trafego.
6. Capturar metadados de trafego legitimo no gateway.
7. Implementar backend minimo de ingestao e consulta.
8. Persistir telemetria e eventos de rede.
9. Executar teste de ponta a ponta.
10. Registrar evidencias em `docs/evidence/` somente quando os testes existirem.

## Criterios de aceite

- Um payload de telemetria do Poste 1 chega ao broker no topico contratado.
- Um payload de telemetria de poste simulado chega ao broker no topico contratado.
- O trafego MQTT entre produtor e broker atravessa a interface monitorada do gateway.
- Pelo menos um evento de rede gerado pelo trafego legitimo e persistido.
- A API retorna telemetria persistida via `GET /api/v1/telemetry`.
- A API retorna eventos de rede persistidos via `GET /api/v1/network-events`.
- Os registros possuem `observed_at` em UTC e `received_at` no backend.
- Nenhuma acao de bloqueio e executada.
- Nenhum item de checklist e apresentado como implementado sem evidencia.

## O que existe hoje

- Repositorio na branch `main`.
- Documentacao inicial em `docs/`.
- Imagens de arquitetura e ideias de dashboard em `docs/`.
- Estrutura de diretorios para as areas principais.
- `README.md` com descricao curta.
- `backend/requirements.txt` vazio.

## O que falta para esta entrega

- Codigo do publicador ESP32.
- Simuladores MQTT dos postes adicionais.
- Configuracao Mosquitto de laboratorio.
- Script ou servico de captura no gateway.
- Definicao concreta das interfaces de rede do gateway no ambiente local.
- Backend minimo com endpoints de ingestao e consulta.
- Persistencia local definida e inicializada.
- Testes ou scripts de validacao ponta a ponta.
- Evidencias executadas da demonstracao.

## Dependencias externas

- ESP32 fisico para o Poste 1.
- Sensor ou valores simulados no firmware do ESP32, conforme disponibilidade.
- Broker Mosquitto acessivel no laboratorio.
- Gateway com duas interfaces ou arranjo equivalente que permita observar trafego atravessando o caminho.
- Rede de laboratorio isolada para testes.
- Ferramentas de captura permitidas no host/VM do gateway.
- Python/ambiente backend a definir pela area `backend-data`.

## Riscos iniciais

- Captura nao observar trafego se o gateway nao estiver realmente inline.
- Timestamps inconsistentes entre ESP32, simuladores, gateway e backend.
- Publicadores e backend divergirem nos contratos de topicos e payloads.
- Checklists antigos serem interpretados como estado implementado.
- Tentativa de antecipar ML, bloqueio, dashboard ou BitNet antes da base de dados estar validada.
