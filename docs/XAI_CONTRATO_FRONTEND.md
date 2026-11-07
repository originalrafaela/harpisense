# XAI consultável — contrato final da candidata 1.0.0

Estado: **interface congelada e validada tecnicamente; aprovação do Arquiteto
pendente**. Branch `feat/reusable-software`, sobre `c44bd6f`. O commit que contém
este documento é a referência da entrega; consultar `git log -1` na branch.
Maestri não estava acessível, portanto não foi atribuída aprovação a outro agente.

## HTTP e autenticação

GET sem body. Todas as rotas abaixo exigem a sessão administrativa Bearer
existente, com expiração, revogação, MFA e origem preservados. Basic técnico não
autoriza. Respostas do leitor usam `Cache-Control: no-store`.

| Consulta | Caminho exato na API | Query |
|---|---|---|
| Incidente | `/api/v1/p11/incidents/{incident_id}/explanations` | `incident_revision`: inteiro >=1, opcional |
| Detecção | `/api/v1/p11/detections/{detection_id}/explanations` | `incident_id` opcional; `incident_revision` opcional, exige incident_id |
| Observação | `/api/v1/p11/observations/{collection_session_id}/{window_id}/explanations` | `sensor_id` opcional |

No runtime nativo, acrescentar o mount **`/p11-api`**. Exemplo da chamada principal:

```http
GET /p11-api/api/v1/p11/incidents/{incident_id}/explanations?incident_revision=1
```

O Frontend deve enviar a revisão do incidente que está apresentando. Sem query,
o servidor seleciona a última revisão persistida desse incidente e informa a
revisão resolvida em `incident_ref`. Nunca seleciona pela última atividade do ativo.
Observação exige sessão e janela exatas; cada análise conserva também seu sensor.

Rotas anteriores preservadas: `GET /api/v1/p11/xai?limit=50&offset=0` e
`GET /api/v1/p11/xai/{explanation_id}/history`. Elas retornam as projeções/histórico
originais; as rotas novas validam os vínculos e oferecem o envelope descrito aqui.

## Resposta do incidente

```json
{
  "incident_ref": {"id": "inc-identificador", "revision": 1},
  "state": "available",
  "analyses": [],
  "read_only": true
}
```

`analyses` contém uma entrada por `detection_ref` da revisão selecionada, inclusive
quando não existe explicação. O state externo é `available` se pelo menos uma
análise tem explicação válida; nos demais casos é `absent_or_unavailable`.
Sempre interpretar o state de **cada análise**. O exemplo acima mostra somente
a estrutura do envelope; os exemplos executáveis completos estão no JSON abaixo.

## Campos exatos de cada análise válida

| Campo | Significado |
|---|---|
| `detection_id`, `detection_revision`, `input_fingerprint` | Identidade exata do registro/vetor explicado |
| `model.detector` | `random_forest` ou `isolation_forest` |
| `model.model_version`, `model.input_dtype` | Versão real; dtype canônico `float32` |
| `window` | `window_id`, `collection_session_id`, `sensor_id`, `feature_schema_version`, `traffic_profile`, `start`, `end` |
| `observation_ref` | `window_id`, `collection_session_id`, `sensor_id` |
| `entity` | `source_ip`, `destination_ip`, `device_id`, `mqtt_client_id`, conforme detecção |
| `asset` | `technical_id`, `display_name`, `name_state`, `name_source` |
| `incident_ref` | `{id,revision}` quando selecionado; null na consulta sem incidente |
| `operational_outputs.classification` | Objeto RF canônico, incluindo probabilities, attack_probability, classe predita/aceita e confiança; null para IF |
| `operational_outputs.anomaly` | Objeto IF canônico: anomaly_score, anomaly_threshold, anomaly_margin, is_anomaly, normal_reference_percentile; null para RF |
| `state`, `reason_code` | Estado e motivo descritos abaixo |
| `explanations` | Lista de explicações válidas, sem escolher silenciosamente classe/referência |
| `rejected_explanations` | Somente `{id,reason_code:INVALID_RECORD_OR_LINK}`; contribuições inválidas não são exibidas |
| `has_more` | Há mais de 100 projeções candidatas; não presumir cobertura completa |

`asset.name_state`: `available`, `unregistered`, `not_identified`.
`name_source`: `asset_registry`, `asset_projection` ou null. Nome ausente é null;
não renomear device_id/tópicos para preencher o rótulo. O adaptador usa o cadastro
da instalação quando presente e a projeção asset de identificador exato como
alternativa. Nome é metadado corrente, não snapshot histórico da análise.

Cada item de `explanations` tem:

| Campo | Conteúdo |
|---|---|
| `id`, `projection_revision` | Identidade da projeção XAI |
| `in_incident_explanation_refs` | true/false se consta no snapshot do incidente; null sem contexto de incidente |
| `record` | Registro canônico explanation, sem renomear os campos |
| `output_direction` | `positive_increases_class_probability` ou `positive_increases_anomaly_score` |
| `coherence` | reconstructed_output, absolute_error, reconstruction_tolerance, detection_output_tolerance, residual_tolerance, causality_or_detector_accuracy_proven=false |
| `risk_mapping` | Relação com o fator do Risk, sem alegar explicar o score total |

Campos obrigatórios de **`record`**: `schema_version=1.0.0`,
`record_type=explanation`, `explanation_id`, `created_at`, `detection_id`,
`window_id`, `collection_session_id`, `model_version`, `input_fingerprint`,
`method`, `explainer_version`, `reference_ref`, `target`, `base_value`,
`output_value`, `contributions`, `additivity_residual`, `parameters`, `limitations`.

O método produzido pelo núcleo existente é exatamente:

```json
{
  "method": "SHAPLEY_PERMUTATION",
  "explainer_version": "harpisense.xai.permutation.v1",
  "target": {"output": "CALIBRATED_CLASS_PROBABILITY", "class_label": "C01"},
  "parameters": {"seed": 42, "permutations": 8, "background_rows": 8}
}
```

É implementação própria, não TreeExplainer, TreeSHAP ou a classe
shap.PermutationExplainer. O enum canônico também admite SHAP_MODEL_AGNOSTIC para
outros registros compatíveis; isso não muda o identificador real deste produtor.
`parameters` acima são os do ensaio; defaults do núcleo são 32 permutações e seed
42. Referência é identificada pelo fingerprint `reference_ref`.

RF: `target.output=CALIBRATED_CLASS_PROBABILITY`, `class_label` explícito.
`output_value` é a probabilidade calibrada dessa classe, inclusive quando normal.
IF: `target.output=ANOMALY_SCORE`, `class_label=null`; saída é `-score_samples`,
na escala operacional, maior significando mais anômalo.

Cada contribuição é exatamente `{feature, value, contribution}`: value é a
entrada da característica; contribution é o valor **com sinal** na unidade da
saída explicada. Positivo aumenta essa saída; negativo a reduz. Aumentar P(normal)
não equivale a aumentar risco. Conservar todas as características, inclusive zeros.
Baseline é a média da saída do modelo sobre a referência, não média das entradas.

## Coerência e transformação para Risk

`base_value + sum(contribution) + additivity_residual = output_value` dentro de
`1e-8`. Resíduo canônico absoluto deve ser **menor que 1e-5**; a saída explicada
deve corresponder à detecção dentro de `1e-6`. A API usa o validador canônico e
informa as tolerâncias em coherence. Essa verificação não prova causalidade,
acurácia, representatividade do background ou qualidade de calibração.

RF no Risk: com cenário, `100 * P(scenario_id)`; sem cenário,
`100 * (1-P(normal))`, seguido de ROUND_HALF_UP a seis casas. `risk_mapping.state`
é `affine_transform` quando a classe explicada permite esse mapeamento;
`scale=100,offset=0` para a classe do cenário, ou `scale=-100,offset=100` para
normal sem cenário. A mesma escala se aplica às contribuições e ao resíduo;
offset se aplica ao baseline. Outra classe é
`different_class_not_additively_mapped`. A API informa source_probability,
factor_value, recorded_factor_value e matches_recorded_factor.

IF no Risk: `100 * normal_reference_percentile if is_anomaly else 0`, não o score
bruto explicado. `state=nonlinear_transform_not_additively_mapped`; constam
percentil, limiar, margem, indicador, fator calculado e fator registrado. As
contribuições continuam explicando somente o score operacional. Não são
atribuições aditivas do percentil ou do risco ponderado total. Sem contexto de
incidente: `state=incident_not_selected`. Sempre `risk_score_explained=false`.

## Ausência, invalidez e erro

| Contexto | HTTP / shape |
|---|---|
| Detecção válida sem XAI persistido | 200; analysis.state=`absent`, reason_code=`EXPLANATION_NOT_PERSISTED`, explanations=[], rejected_explanations=[] |
| Existem candidatos XAI, todos inválidos | 200; state=`invalid`, reason_code=`INVALID_RECORD_OR_LINK`, explanations=[], rejected_explanations=[{id,reason_code}] |
| Detecção referenciada ausente | Incidente continua 200; entrada state=`unavailable`, reason_code=`DETECTION_NOT_FOUND`, explanations=[] |
| Revisão ambígua / detecção inválida | 200; state=`unavailable`; reason_code=`DETECTION_REVISION_AMBIGUOUS` / `INVALID_DETECTION_RECORD` |
| Item válido entre candidatos rejeitados | 200; state=`available`; rejeitados permanecem separados |
| Detecção direta ou incidente/revisão inexistentes | 404, `{error:{code:DETECTION_NOT_FOUND/INCIDENT_NOT_FOUND}}` |
| Detecção fora do incidente selecionado | 404, `{error:{code:DETECTION_NOT_IN_INCIDENT}}` |
| Query inválida | 422; error.code=`INVALID_REQUEST` ou `INCIDENT_ID_REQUIRED` |
| Sem sessão ou sessão inválida | 401; envelope de autenticação existente |
| Origem/Host recusados | 403, conforme guarda existente |
| Banco indisponível ou incidente canônico inválido | 503, `{error:{code:XAI_UNAVAILABLE}}` |

Entradas unavailable contêm somente detection_id/state/reason_code/explanations/
rejected_explanations/has_more; os demais campos não são inventados. Observação
sem detecções retorna 200 com analyses=[], has_more=false, read_only=true.
Observações são limitadas a 200 detecções, com has_more explícito e filtro sensor_id.

Abrir a aba é somente GET em transação PostgreSQL READ ONLY. Não gera explicação,
BitNet, decisão, aprovação, execução ou contenção. Explicação é contribuição do
modelo; evidências/logs, texto HarpIA e estados de defesa continuam separados.

## Artefatos e ambiente acessível

- [Exemplos completos RF, IF, normal e ausência](evidence/xai-reader-20261107/examples.json).
- [OpenAPI com schemas XAIAnalysis, XAIIncident, XAIObservation e XAIExplanationRecord](evidence/xai-reader-20261107/openapi.json).
- [Aceite instalado e hashes](evidence/xai-reader-20261107/installed-runtime.json).
- [Encaminhamento ao Arquiteto](XAI_PACOTE_E_VALIDACAO.md).

Ensaio instalado ativo na validação desta entrega:
**`http://127.0.0.1:18089/p11-api`**, túnel SSH restrito ao loopback do host para
a VM descartável Ubuntu. GET principal é a base acima +
`/api/v1/p11/incidents/{incident_id}/explanations?incident_revision=1`.
Sessão e IDs corretos da fixture estão em `local-evidence/xai-reader/access.json`,
arquivo local privado ignorado pelo Git; não transmitir nem versionar seu conteúdo.
Os exemplos de desenvolvimento possuem outros IDs, porque usam modelos e banco
independentes. Não copiar seus incident_ids para a fixture instalada.

Para validação em navegador, usar a origem `http://127.0.0.1:18089` e o mount
`/p11-api`; requests de outras origens podem ser recusados pela guarda nativa.
Não alterar CORS/Origin para contornar a política. Token segue os timeouts reais
da sessão; a VM, servidor de ensaio e túnel precisam continuar ativos. Não é URL
de produção nem disponibilidade permanente após encerrar o ambiente de testes.
