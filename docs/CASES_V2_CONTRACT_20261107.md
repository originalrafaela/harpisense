# Casos distintos: contrato implementado v2

Ownership: Backend Data implementa `delivery/linked_cases.py`, o produtor em
`delivery/activity.py` e a composição em `delivery/app.py`. Reutiliza a fila e
controles publicados; não altera `controls.py`, `routes.py` nem
`operational_queue.py`, não cria segundo mecanismo de troca de perfil.

## Rotas existentes

- GET `/api/v1/security/settings/mode/default`: resposta `cases` no topo.
- GET `/api/v1/p11/health`: `operational_controls.cases`.
- PUT settings: revalida sob lock 72611027 e devolve 409 `detail.current`
  vigente quando há atividade/pendência/desconhecido. Nenhuma alteração de modo
  ao investigar, avaliar, aprovar ação ou ler este snapshot.
- No instalado, prefixar `/p11-api`; no proxy Vite esse prefixo é removido.

Não criar endpoint `/operational_state`: não existe neste contrato.

## Campos exatos de cases

| Campo | Contrato |
| --- | --- |
| `contract_version` | inteiro 2 |
| `status` | active / none_active / partial / unknown |
| `coverage` | complete / partial / unknown |
| `count_basis` | distinct_incident_id |
| `known_active_count` | quantidade de IDs de incidente distintos com atividade vinculada conhecida; null quando só há itens ativos sem vínculo verificável |
| `total_active_count` | total distinto apenas sob observação suficiente; null sob parcial/desconhecido |
| `classification_counts` | `{anomaly, confirmed_attack, incident}`: contagens conhecidas de IDs distintos por classe |
| `classification_count_basis` | distinct_incident_id_per_class |
| `classification_overlap` | true: categorias se sobrepõem, NÃO somar para formar total |
| `unlinked_active_item_count` | quantidade de itens fonte ativos sem vínculo verificável |
| `observation_sufficient` | boolean; ambas fontes de casos atuais/completas e nenhum item ativo sem vínculo |
| `observed_at` | horário do relatório mais antigo entre as duas fontes necessárias; null se alguma nunca foi observada |
| `observation_basis` | oldest_required_source_report |
| `sources` | relatórios incident/anomaly com proveniência, validade e motivos |
| `items` | casos distintos com referências exatas, classificação, fatos e navegação |
| `unlinked_items` | fatos bloqueadores sem navegação inferida |
| `reason_codes` | lista de objetos `{code,source,record_id?}` |

`sources` preserva `source`, `source_revision`, `observed_at`, `fresh`, `valid`,
`complete`. Acrescenta `reason_codes` e
`freshness_policy:{version:'operational-authority.v1',max_age_seconds:30,clock:'postgresql'}`.
Não usar updated_at do controle nem TTL calculado pelo frontend para frescor.

Cada `items[]` contém:

- `case_id`: o ID canônico do incidente, não um ID de detecção inventado;
- `incident_refs:[{id,revision}]`: todos os vínculos exatos fornecidos;
- `incident_ref`: o único vínculo se inequívoco; null quando existem revisões
  distintas do mesmo caso. Continuam sendo um caso, com links separados;
- `classifications`: anomaly / incident / confirmed_attack, quando sustentadas;
- `confirmed_attack_refs`: revisões exatas que sustentam essa classificação;
- `items`: fatos fonte com source, record_id, source_revision,
  source_observed_at, fresh, state, origin, incident_ref, activity_type e
  record_revision apenas quando fornecida. Sob UNKNOWN pode conter
  last_known_state/last_known_source_revision/last_known_observed_at;
- `assessment_records`: avaliação persistida, identidade, horário e motivo,
  vinculados à revisão. Não é o estado do modelo ou do ciclo de vida;
- `links:[{rel:'incident_dossier',incident_ref,path}]`: rota relativa real de
  ficha por ID/revisão. Não construir navegação usando record_id de fonte.

## Critérios e limites semânticos

O produtor publica `incident_ref:{id,revision}` e origem imutável. O registro
referenciado deve existir e validar a mesma identidade/revisão/origem. Ensaios
synthetic são persistidos como ensaio, nunca atualizam a autoridade operacional.
Snapshots operacionais carregam origin trusted-service. Vínculos inexistentes,
origem ausente ou contraditória ficam em unlinked_items, bloqueiam Aplicar e
impedem total completo; não são deduplicados por sensor, IP ou proximidade temporal.

`anomaly` conta casos com fato ativo da fonte anomaly. `incident` conta casos
com fato ativo da fonte incident. `confirmed_attack` exige simultaneamente fato
ativo da fonte incident explicitamente `activity_type:'attack'` e última avaliação
confirmed na revisão vinculada. Avaliação histórica sozinha não cria atividade;
avaliação confirmed + anomalia sem ciclo de ataque explícito não vira ataque ativo.

Exemplo: incident e anomaly apontam para o mesmo ID; esse ID tem fato de ataque
e avaliação confirmed. As três classificações valem 1 e o TOTAL vale 1, não 3.
Sem vínculos suficientes, o total fica null, nunca uma soma presumida.

Perda de comunicação não encerra caso. Ativos stale permanecem contados com
ressalva e total null. UNKNOWN nunca é confiável: quando existe fato ativo anterior
no ledger do produtor, ele é retido com proveniência, sem afirmar observação nova.
Somente encerramento explícito do mesmo ID fonte permite omissão posterior.
Histórico encerrado não conta e não bloqueia; avaliação confirmed não é consultada
como autoridade global de atividade.

Somente status none_active + observation_sufficient true + total_active_count 0
permitem "Sem casos ativos". Zero conhecido sob parcial/desconhecido não permite.
Approval/execution/verification continuam em pending.blockers, separados dos
casos incident/anomaly. Aplicar exige todas as cinco fontes operacionais atuais,
sem bloqueadores. Emergência continua independente. M2/M3 não provam contenção.

`pending.source_cases` preserva a projeção antiga count_basis source_item apenas
para diagnóstico; não é o total distinto. O frontend deve consumir cases v2.

## Evidências

`backend/delivery_tests/test_linked_cases_native.py`: nove testes aprovados com
PostgreSQL nativo Windows, HTTP autenticado, sem Docker; inclui concorrência real
entre conexões, duplicação incidente/anomalia, revisões distintas do mesmo ID,
avaliação separada, ausência de vínculo, stale/UNKNOWN e encerramento explícito.

Payloads exatos em `docs/evidence/backend-integration-20261107/cases-v2/*.json`:
`current-sufficient-active`, `current-sufficient-zero`, `partial-unlinked`,
`partial-observation`, `never-observed`, `stale-known-attack`,
`communication-loss-known-attack`. Cada arquivo identifica fixtures controladas
e encapsula a resposta real em `response`; não comprova ataque/tráfego real.

Sem dependência ou migração nova além de delivery/004_activity_decision_snapshot.sql
e delivery/003_incident_assessment.sql já integradas. Os produtores reais ainda
precisam declarar cobertura completa: o produto novo sem relatório permanece
unknown. Não comprova instalado, reboot nem captura operacional certificada.
