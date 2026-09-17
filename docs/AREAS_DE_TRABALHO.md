# HarpiSense - Areas de trabalho e posse de diretorios

Este documento separa os diretorios por frente para reduzir edicoes concorrentes. Arquivos compartilhados devem ser centralizados pelo responsavel de integracao antes de alteracoes nas worktrees.

## Fonte compartilhada centralizada

Arquivos de contrato e decisao compartilhados:

- `docs/DECISOES_ARQUITETURAIS.md`
- `docs/CONTRATOS_COMPARTILHADOS.md`
- `docs/PLANO_PRIMEIRA_ENTREGA.md`
- `docs/AREAS_DE_TRABALHO.md`
- `docs/ROTEIRO_INTEGRACAO_PRIMEIRA_ENTREGA.md`

Regras:

- As areas podem ler estes arquivos livremente.
- Alteracoes devem ser propostas e centralizadas antes de editar diretamente nas worktrees.
- Nenhuma area deve criar contrato paralelo para topicos MQTT, payloads, timestamps, eventos de rede ou ingestao backend.
- Evidencias de teste devem ir para `docs/evidence/` quando existirem, com nomes claros por data e area.

## iot-mqtt

Diretorios de responsabilidade:

- `iot/`
- `mqtt/`
- `lab/legitimate-traffic/`
- `tests/integration/` somente para testes de publicacao/assinatura MQTT acordados com `backend-data`

Responsabilidades liberadas:

- Firmware do ESP32 para o Poste 1.
- Simuladores dos postes 2 e 3.
- Publicacao MQTT nos topicos de telemetria contratados.
- Configuracao de laboratorio do Mosquitto, usuarios e ACLs sem credenciais reais versionadas.
- Subscriber de teste para validar payloads.

Limites:

- Nao alterar contratos compartilhados sem centralizacao.
- Nao implementar deteccao, ML, bloqueio ou API backend.
- Nao versionar senhas, `.env`, dumps sensiveis ou logs com segredo.

## edge-security

Diretorios de responsabilidade:

- `edge/`
- `lab/topology/`
- `lab/kali/` apenas para cenarios documentados de laboratorio, sem antecipar ataques nesta entrega
- `tests/security/` para validacoes da captura e, futuramente, politicas

Responsabilidades liberadas:

- Documentar interfaces e topologia real do gateway.
- Capturar metadados de trafego legitimo atravessando o gateway.
- Produzir eventos `network_event` conforme contrato.
- Enviar eventos de rede ao backend pela interface contratada.
- Validar que a primeira entrega opera sem bloqueio.

Limites:

- Nao implementar bloqueio real na primeira entrega.
- Nao acionar firewall para contencao nesta etapa.
- Nao tratar BitNet como dependencia do caminho critico.
- Nao treinar ou integrar modelo ML nesta etapa.

## backend-data

Diretorios de responsabilidade:

- `backend/`
- `tests/unit/`
- `tests/integration/` para API, persistencia e ingestao
- `docs/diagrams/` somente para diagramas de dados aprovados e coerentes com contratos compartilhados

Responsabilidades liberadas:

- Backend minimo de ingestao e consulta.
- Persistencia de telemetria de sensores.
- Persistencia de eventos de rede.
- Validacao basica de payloads, timestamps e identificadores.
- Health check da API.
- Scripts de inicializacao local quando necessarios.

Limites:

- Nao implementar dashboard completo nesta entrega.
- Nao implementar RBAC, multiplos perfis ou cadastro publico.
- Nao integrar AWS nesta entrega.
- Nao tratar eventos de bloqueio como executaveis enquanto o contrato estiver apenas reservado.

## Diretorios reservados para etapas posteriores

- `ml_pipeline/`: treinamento, datasets processados, metricas e artefatos de modelo.
- `frontend/`: dashboard completo.
- `cloud/`: AWS, RDS, S3, IAM, CloudWatch e Lambda.
- `genai/`: BitNet local e explicacoes de incidentes.
- `tests/resilience/`: testes de resiliencia quando houver servicos suficientes.

## Dependencias entre areas para a primeira entrega

- `iot-mqtt` fornece mensagens MQTT validas para o broker.
- `edge-security` observa o trafego legitimo e transforma observacoes em `network_event`.
- `backend-data` persiste e consulta telemetria e eventos.
- Integracao ponta a ponta so deve comecar depois que os contratos deste documento e de `docs/CONTRATOS_COMPARTILHADOS.md` estiverem aceitos pelas frentes.
