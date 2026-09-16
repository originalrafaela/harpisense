# HarpiSense - Decisoes arquiteturais vigentes

Este documento registra as decisoes que prevalecem para a primeira etapa do HarpiSense. Quando houver divergencia com documentos anteriores em `docs/`, este arquivo deve ser tratado como fonte de verdade ate nova decisao registrada.

## Escopo operacional

- O sistema tera um unico administrador.
- Nao havera multiplos perfis, RBAC, cadastro publico ou autoinscricao de usuarios nesta etapa.
- O HarpiSense e um NIDS/NIPS para ambiente IoT/MQTT de laboratorio, com gateway inline entre a zona de testes e a rede IoT protegida.
- Poste 1 sera representado por ESP32 fisico.
- Os demais postes serao simulados.
- A primeira entrega deve demonstrar publicacao MQTT, trafego legitimo atravessando o gateway e persistencia/consulta pela API.

## IA generativa

- A IA generativa sera BitNet local.
- O BitNet sera usado exclusivamente para explicar incidentes ja detectados e registrados.
- O BitNet nao decide bloqueios, nao executa acoes e nao acessa firewall.
- A protecao do HarpiSense deve funcionar com o BitNet desligado.
- Amazon Bedrock fica fora do escopo vigente.

## Modos IDS/IPS

### IDS

- Detecta, registra e alerta.
- Nao bloqueia.
- E o modo base para validacao inicial.

### IPS supervisionado

- O sistema recomenda bloqueio.
- O administrador aprova ou rejeita cada solicitacao.
- Sem aprovacao explicita, nenhum bloqueio e executado.
- Solicitacoes expiram.
- Antes da execucao, uma solicitacao aprovada deve ser revalidada contra estado atual, whitelist, expiracao e politica vigente.

### IPS autonomo

- ML e motor de politicas podem permitir resposta automatica dentro de limites definidos previamente.
- Nao exige aprovacao por incidente quando a politica permitir a acao.
- Deve respeitar whitelist, limites de duracao, limites de escopo e auditoria.

## Bloqueios e auditoria

- Bloqueios serao temporarios por padrao.
- Deve existir whitelist.
- Deve existir desbloqueio manual.
- Toda recomendacao, aprovacao, rejeicao, bloqueio, expiracao, desbloqueio e alteracao de politica deve gerar auditoria.
- Bloqueios reais nao fazem parte da primeira entrega.

## Fora da primeira entrega

- ML treinado.
- Inferencia online com modelo treinado.
- SHAP/XAI.
- Bloqueios reais via firewall.
- Dashboard completo.
- AWS.
- BitNet integrado.
- Cadastro publico, multiplos usuarios e RBAC.

## Estado observado no repositorio em 2026-09-15

- Existe `README.md` com descricao curta do projeto.
- Existe `.gitignore` cobrindo credenciais, ambientes, builds e artefatos comuns.
- Existe `backend/requirements.txt`, atualmente vazio.
- Existem documentos e imagens em `docs/`.
- Existem diretorios planejados para `backend`, `edge`, `iot`, `mqtt`, `lab`, `ml_pipeline`, `frontend`, `cloud`, `genai` e `tests`, mas sem codigo rastreado de implementacao.
- O arquivo `docs/HarpiSense_Documentacao_Projeto.docx` esta vazio no repositorio.
- Os checklists existentes em `docs/` sao planejamento e referencia; itens marcados como checklist nao devem ser tratados como funcionalidades implementadas.
