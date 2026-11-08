# Análise do modelo (XAI/SHAP)

## Integração

A aba consulta somente explicações persistidas e vinculadas à revisão selecionada do incidente:

```http
GET /api/v1/p11/incidents/{incident_id}/explanations?incident_revision={revision}
```

A chamada usa a sessão administrativa existente e passa pelo proxy local restrito `/p11-api`. Não executa inferência, não consulta banco diretamente e não chama Risk, Policy, HarpIA ou executor. O transporte permite apenas GET para essa rota e rejeita query strings além de `incident_revision`.

O identificador e a revisão vêm do registro de incidente selecionado (`data.incident_id`/`id` e `data.revision`). A resposta precisa repetir esse vínculo no envelope. Cada explicação também precisa corresponder à detecção, ao modelo e à saída explicada; `in_incident_explanation_refs` precisa ser `true` para que a explicação seja mostrada como pertencente ao incidente. Um XAI persistido que não esteja referenciado pelo incidente é tratado como “Explicação não disponível”. Resultados anteriores são descartados imediatamente na troca de incidente e respostas tardias não substituem a seleção atual.

| Campo da interface | Campo do contrato |
|---|---|
| Nome amigável / ID técnico | `asset.display_name` / `asset.technical_id` |
| Modelo e versão | `model.detector` / `model.model_version` |
| Janela | `window.window_id`, `window.start`, `window.end` |
| Classe e probabilidade RF | `record.target.class_label`, `record.output_value`; unidade `CALIBRATED_CLASS_PROBABILITY` |
| Score IF | `record.output_value`; unidade `ANOMALY_SCORE`, sem porcentagem |
| Referência e pontuação final | `record.base_value` / `record.output_value` |
| Característica e contribuição | `record.contributions[].feature`, `.value`, `.contribution` |
| Direção | `output_direction` |
| Método | `record.method`; `SHAPLEY_PERMUTATION` aparece como “Shapley por permutações” |

RF e IF aparecem em seletores independentes por detecção. O painel não combina contribuições nem pontuações e não interpreta `risk_mapping` como saída explicada. A API é a autoridade para vínculos, validação canônica e coerência numérica.

## Estados

- `absent`: “Explicação não disponível”.
- Explicação existente sem referência no incidente: descartada para esse incidente.
- `invalid`: resposta marcada inválida ou inconsistente com o contrato; apresentada como erro de análise.
- `unavailable`: análise indisponível, com motivo quando fornecido.
- Erro HTTP/rede/autorização: falha da consulta, com opção de tentar novamente; não vira ausência.
- Envelope com incidente/revisão diferente: rejeitado como incompatível.

As análises `unavailable` podem conter apenas `detection_id`, estado, motivo e listas vazias; a interface não inventa ativo, modelo, janela, revisão ou score.

## Versão de contrato e verificação

Implementação feita em `feat/product-visual-refinement`, baseada na `feat/native-installers` em `96511ee9dffe62c646ace71717097684b3a9957f`. O contrato candidato publicado pelo Backend está em `feat/reusable-software`, commit `48bb43aa2e86b5de433759a6698972dde7534a6f`, nos arquivos `docs/XAI_CONTRATO_FRONTEND.md` e `docs/evidence/xai-reader-20261107/openapi.json`. O contrato marca a aprovação arquitetural e a inclusão no instalador completo como pendentes.

Verificações locais usam respostas de teste isoladas e validam RF, IF, ausência, erro HTTP, vínculo ao incidente, troca rápida sem resposta obsoleta, acessibilidade básica por teclado e layout em 1280×900 e 390×844. Elas não são navegador conectado à API. O Backend reportou 200/autorizado e sete verificações do leitor em runtime de ensaio, com hash do runtime `c610b33fecbb56500716f79b1ba54ee6dd408a5bcd40cfc1dfeb5f0f0e6a9675`; isso não equivale ao aceite do software instalado completo, pois `build_info.json`/`installed_build` não foram encontrados e os modelos científicos não estavam instalados naquele runtime. Nesta worktree, a porta loopback `18089` não estava escutando quando verificada e não havia sessão administrativa autorizada disponível no navegador; portanto, os fluxos RF/IF reais pela UI não foram validados.

Para uma validação conectada, configurar `HARPI_API_TUNNEL_TARGET` como URL loopback do túnel aprovado, iniciar o frontend na origem aprovada pelo Backend, autenticar pela sessão administrativa normal e abrir um incidente que possua referência XAI. Nunca copiar tokens ou segredos para parâmetros, logs, arquivos versionados ou relatório. IDs dos exemplos de desenvolvimento não são os IDs do runtime instalado.
