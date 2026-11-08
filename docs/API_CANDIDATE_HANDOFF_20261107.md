# Contrato comum: implementação e lacunas

Branch `feat/backend-incident-shap-integration`: controles finais `2aa0ca4`,
SHAP real `a3eb885`, fichas/produtores/resolver `dd7d813`, primeiro acesso `071d052`,
aprovação/resultados `10acba5` e casos distintos v2 `5608399` + `fb0f8e9`.
Nenhuma mudança em native-installers ou na prévia 5174.

## Rotas existentes testadas por HTTP/PostgreSQL

Todas exigem sessão administrativa. No runtime nativo, prefixar `/p11-api`.

| Rota | Resposta implementada |
| --- | --- |
| GET `/api/v1/security/settings/mode/default` | `value`, `revision`, `cases`, `pending`, `effective_state`, `observed_at`, `change_allowed` |
| PUT na mesma rota | `value`, `expected_revision`, `reason`; recusa 409 com `detail.current` vigente e motivo curto |
| GET `/api/v1/p11/health` | `operational_controls.cases` e `operational_controls.effective_state` |
| POST `/api/v1/security/emergency-stop` | independente de consulta à fila; não apaga fatos ativos persistidos |
| GET `/api/v1/p11/incidents/{id}/dossier?incident_revision=N` | ficha, registros ligados, ausências, avaliação e análises canônicas |
| POST `/api/v1/p11/incidents/{id}/assessments` | `{incident_revision,assessment,reason}`; ator/horário do servidor, sem aprovação/despacho |
| GET `/api/v1/p11/incidents/{id}/explanations?incident_revision=N` | `incident_ref`, `analyses`, `read_only` |
| GET `/api/v1/p11/detections/{id}/explanations?incident_id=ID&incident_revision=N` | registro canônico XAI e indicador `in_incident_explanation_refs` |

Os seis testes de `test_backend_integration.py` passaram com PostgreSQL nativo
Windows, Uvicorn, sessão MFA e BitNet desligado. Foram gerados exemplos reais
da API sobre fixtures artificiais em `docs/evidence/backend-integration-20261107`:
`incident-with-explanation.json`, `incident-without-explanation.json`,
`profile-change-refused.json`. Não contêm credenciais ou códigos de recuperação.
O servidor do teste é encerrado ao final; `http-check.json.url_tested` não é URL
de serviço permanente. As fixtures raiz de recusa refletem cases v1 histórico;
as fixtures v2 atuais estão no subdiretório cases-v2.
Runner auth confirmado em 18082 com origem 5176; E2E real reportado pelo Codex
concluiu primeiro acesso. API cases v2 em 18083 usa o MESMO banco, sem provisionar
nem reiniciar 18082, e permite origem 5176 (sem sessão retorna 401 esperado).
O proxy Vite remove /p11-api: escolher alvo 18082 ou 18083 conforme a versão,
sem mudar 5174/5175. Não declarar cases v2 no processo antigo de 18082.

## Casos: campos atuais, sem implementar a proposta por suposição

`cases.status`: active|none_active|partial|unknown.
`cases.coverage`: complete|partial|unknown.
`cases.known_active_count`: número distinto conhecido; null quando não se pode
identificar casos por vínculos verificáveis ou o adapter está indisponível.
`cases.count_basis`: **distinct_incident_id** na versão 2. Regras e campos exatos
em CASES_V2_CONTRACT_20261107.md. A projeção antiga source_item fica apenas em
pending.source_cases para diagnóstico.
`cases.sources`: source/source_revision/observed_at/fresh/valid/complete.
`cases.items`: grupos por case_id com incident_refs/links e fatos em items;
cada fato preserva source/record_id/source_revision/state/fresh e record_revision
apenas quando fornecida pelo produtor. Casos contam incident/anomaly; pendências
approval/execution/verification estão em pending.blockers. Todas as fontes devem
estar atuais e verificadas para permitir Aplicar.

TTL de snapshot: 30s. Ativos conhecidos continuam visíveis depois de vencer.
Omissão exige encerramento explícito anterior do ID. UNKNOWN nunca é confiável.
Somente none_active permite "Sem casos ativos"; 0 com cobertura desconhecida não.

Totais distintos, classificação sustentada por ciclo de vida e avaliação e
navegação exata estão implementados em 5608399 e passaram nove testes HTTP/PG.
Ausência de vínculo ainda impede total completo: total_active_count é null,
nunca uma soma presumida de itens fonte. Não fabricar IDs a partir de record_id.
As contagens por classe se sobrepõem; não somá-las. Cobertura operacional real
completa continua não certificada: as evidências de casos são fixtures controladas.
Avaliação histórica confirmed não atesta atividade atual; ensaio não entra na
autoridade operacional. Não há cobertura operacional real completa publicada.

## Ficha, estado, defesa e SHAP

`incident_card.origin` preserva a origem da projeção; não deriva origem da
avaliação. `attack_assessment.state` pode ser unassessed|confirmed|discarded|
inconclusive; assessment_id/actor/at/reason são nulos sem registro. Esse é o nome
existente, não substituir por um campo assessment nullable inventado no frontend.
`operational_mode` usa apenas decisões ligadas, ou unknown/value:null. Sidecars
de perfil/política exigem ID e revisão exatos da decisão em hs_decision_snapshot;
ausentes aparecem em missing_links. Nunca usar o perfil atual como histórico.

records.decision/approval/execution/verification são separados e preservam
id/revision/source/data. `defense_execution.state:missing` significa sem registro,
não "não executado". Sucesso só pode vir de status de execução/verificação
vinculado e validado; aprovação não atesta contenção. Executor real permanece
not_integrated/available:false, observed_at/source:null com bloqueio explícito.

technical_cards, gráfico e tabela devem usar explanation.record.contributions
do MESMO explanation.id/projection_revision, com base_value/output_value do mesmo
registro. Tree RF é RAW_CLASS_PROBABILITY antes da calibração; Permutation RF é
CALIBRATED_CLASS_PROBABILITY; IF é ANOMALY_SCORE validado contra -score_samples.
IF não é chance de ataque. SHAPLEY_PERMUTATION histórico mantém seu nome.
A ficha filtra in_incident_explanation_refs===true; falta de explicação retorna
technical_cards e latest_explanations vazios. Frontend deve limpar seleção anterior
durante a troca de ID; o teste backend não substitui esse aceite visual.

## Primeiro acesso, runtimes e pacote

Contrato de conta em `FIRST_ACCESS_AUTH_CONTRACT_20261107.md`. Onboarding da conta
é independente do setup/wizard de instalação: confirmar códigos não muda setup,
configuração ou progresso. Não há requisito de terminar wizard para confirmar.

SHAP: requirements-scientific.txt/lock comuns e coleta de pacotes adicionada aos
builders Windows/Ubuntu nesta worktree. Faltam locks/wheels específicos e aceites
dos artefatos finais. Auth primeiro acesso: migration admin_auth/004_first_access.sql,
sem nova biblioteca/serviço. Atividade: delivery/004_activity_decision_snapshot.sql.
Nenhuma prova depende apenas de Docker; tampouco estes testes provam pacote instalado.
Faltam Windows e Ubuntu limpos sem Docker, reboot, login/painel e serviços automáticos.
