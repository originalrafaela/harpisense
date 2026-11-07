# Ficha estruturada e avaliação humana do incidente

Base de composição `a8fef1f`, branch `feat/incident-dossier-product`.
Nenhuma alteração em worktrees de outros responsáveis, instâncias instaladas,
VMs, serviços existentes ou contenção real.

## API de sessão existente

- `GET /api/v1/p11/incidents/{id}/dossier?incident_revision=N`
- `POST /api/v1/p11/incidents/{id}/assessments`

O GET usa uma transação PostgreSQL `REPEATABLE READ READ ONLY`. Retorna
`incident_ref`, `incident_card`, `technical_cards`, `records`, `logs`,
`log_references`, `missing_links`, `assessments`, `latest_explanations`,
`commands` e `read_only: true`. Revisão não encontrada retorna 404, estado
inválido ou banco indisponível retorna 503. Todas as rotas exigem sessão
administrativa e usam `Cache-Control: no-store`.

`incident_card` contém:

- `incident_id`, `occurred_at`, `asset {technical_id,display_name}`;
- `anomaly {state,observations:[{detection_id,classification,anomaly}]}`;
- `attack_assessment {state,assessment_id,actor,at,reason}`;
- `attack_situation {state,value,source:'incident.status'}`;
- `defense_decision {state,records}` e `defense_execution {state,records}`;
- `operational_mode {state,value}`: M1/M2/M3 somente de snapshots de decisão
  vinculados à revisão exata; nunca usa o modo atual do dashboard.

Classificação RF e anomalia IF continuam sendo observações do modelo, sem
equivaler a avaliação humana de ataque. Ausência de execução é `state:missing`,
não uma afirmação de que a ação não foi executada. Dados de decisão/execução
são projeções `{id,revision,source,data}` com vínculos exatos e fingerprint da
ação. Não se resolve uma revisão ambígua pelo último registro arbitrariamente.

Cada ficha técnica inclui `incident_ref`, `detection_id`, `asset`, `window`,
`model`, `method`, `explainer_version`, `output {kind,class_label}`,
`reference {ref,value}`, `result {value}`, `principal_contribution`,
`summary`, `summary_source:deterministic` e `explanation {id,projection_revision,record}`.
São os mesmos registros canônicos validados pelo leitor XAI. Só são exibidas
explicações presentes nos `explanation_refs` do incidente selecionado. O resumo
determinístico cita a contribuição registrada com sinal; não afirma causas ou
confirmação de ataque. BitNet não é chamado. `latest_explanations` contém até
três fichas técnicas em ordem cronológica decrescente, sem fabricar histórico.

`logs` só contém projeções `network_event` explicitamente referenciadas. Um
`source_ref` em evidência é um ponteiro em `log_references`, não um log legível.
Referências ausentes, inválidas ou ambíguas são listadas em `missing_links`.

## Avaliação e auditoria

POST aceita somente `{incident_revision,assessment,reason}`, com avaliação
`confirmed`, `discarded` ou `inconclusive`. Usuário e horário são do servidor;
campos extras são recusados. Uma revisão ultrapassada retorna 409. O evento
append-only fica em `hs_incident_assessment` e a auditoria em `hs_control_audit`
com operação `INCIDENT_ASSESSED`, na mesma transação e lock de mudança de modo.
Também é usado o lock de projeção do incidente para impedir avaliação de uma
revisão substituída durante a gravação.

O evento preserva `origin` do registro (`synthetic`/`trusted-service`/`unknown`).
A avaliação não altera projeções, classificação, perfil, aprovação ou execução.
O retorno explicita esses três efeitos como `false`. O cadastro não permite
transformar uma simulação em evento real.

`OperationalQueue.snapshot` retém casos ativos conhecidos mesmo se sua fonte
ficar desatualizada, acrescentando `fresh:false` e mantendo `reliable:false`.
Acrescenta contagens por origem, `coverage` e `missing_sources`. Ataques humanos
confirmados permanecem bloqueadores até reavaliação explícita ou fechamento do
incidente. Esses eventos não atestam cobertura completa dos produtores.

## Integração nativa necessária

O instalador precisa executar `delivery/003_incident_assessment.sql` em seu
`prepare_database`. Depois da autenticação, montar:

```python
from delivery.incident_dossier import install_incident_api
install_incident_api(api, store, state['installation_id'])
```

Não há nova biblioteca ou dependência Docker. Builders existentes já coletam
o pacote delivery e os SQLs; ainda é necessário gerar e validar um pacote novo.

## Validação e bloqueio concreto

`backend/delivery_tests/test_incident_dossier.py` passou três testes com
PostgreSQL nativo em cluster novo, sessão MFA real e servidor HTTP Uvicorn,
sem Docker e sem BitNet. Exercitou leitura da ficha técnica, dados correspondentes
ao registro XAI, modo histórico M1, 401/404/409/422, gravação/auditoria de
avaliação, preservação de origem sintética e classificação, nenhuma simulação
ou execução disparada, recusa de troca após confirmação e retenção de caso
ativo sob perda de visibilidade. O cluster foi encerrado ao concluir.

Aprovação e execução operacional ainda não estão integradas: `commands`
retorna `approval_available:false`, `execution_available:false` e motivo.
O simulador isolado existente não foi exposto como um executor operacional.
Isso impede declarar o aceite completo do fluxo M1 avaliação → aprovação →
resultado; a avaliação e o histórico de decisão não simulam esse sucesso.
Também permanece pendente o aceite destes novos fluxos em pacote instalado
e reinício de sistemas Windows/Ubuntu limpos.
