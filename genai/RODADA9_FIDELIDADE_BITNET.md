# Rodada 9 — inferência BitNet com fatos selecionados pelo P11

## Resultado

Foram concluídas **duas gerações de desenvolvimento e seis de avaliação**, sequenciais, pelo caminho seletor P11 → DTO → serviço loopback → adaptador. Todas vieram do modelo (bitnet_unverified_text); nenhuma foi fallback. As oito respostas foram reprovadas no resultado global de fidelidade/legibilidade. O modelo permanece experimental e fora do caminho operacional.

Uma tentativa anterior do verificador iniciou o servidor, mas perdeu o relatório porque amostras deque não eram serializáveis em JSON. Não foi possível recuperar as respostas nem confirmar o número exato de gerações daquela tentativa. O orçamento reservou conservadoramente até duas chamadas; somando essa reserva e as oito respostas preservadas, o consumo contabilizado fica em no máximo dez das doze chamadas permitidas. A instrumentação foi corrigida (list(...)) antes da repetição. A tentativa perdida não foi misturada aos resultados observados.

## Contrato e contexto

Foi pesquisado o catálogo v2 e os pacotes locais anteriores. O contrato oficial de incidente contém status, target_ref, referências, Risk e gates, mas **não contém estado de conectividade/online/offline**. O seletor P11 também não lê evidência textual. Por isso o caso “poste offline” foi retirado como caso de fidelidade: atribuir sua omissão ao modelo seria incorreto. Foi substituído por “incidente observado; resultados e execução não informados”, representável pelos campos selecionados. A lacuna de conectividade permanece documentada; não foi criado campo concorrente.

Antes da carga, os contextos finais foram inspecionados. A ponte preservou RF, IF, status/score/fatores Risk, XAI tipado, decisão, estado de execução e campos nulos. Nos casos de métricas, RF, IF e Risk chegam como valores distintos. A evidência com SYNTHETIC_LOG_MARKER aparece somente na linha sintética do Store; o seletor não a consulta nem a inclui no prompt. O marcador não aparece em nenhuma entrada efetiva ou resposta. Isso reduz a superfície de texto não confiável, mas não demonstra proteção geral contra prompt injection.

O arquivo [RODADA9_SINTETICO.json](RODADA9_SINTETICO.json) preserva contextos efetivos, prompts completos enviados, respostas brutas, respostas entregues pelo adaptador, configurações do pedido e do runtime, término, duração e memória por caso. Todos os dados são sintéticos; nada foi escrito no PostgreSQL.

## Configuração e memória

- Modelo: GGUF BitNet I2_S Microsoft, SHA-256 4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162.
- Runtime fixado: BitNet revisão completa 0b341e582afbf9e1011f24744b554c96a3477eb5, submódulo llama.cpp 390c307752ab78fd8189f359d6954c9ba1be74af, versão 9918 (390c30775), executável SHA-256 a90d9162fbf6c150a850dbe510be63eee5921a0fe4b8389a45570195d854b9b7. Patch local de ativação mantido; nenhum arquivo de runtime ou peso foi alterado.
- Perfil: contexto 1024, máximo 96 tokens, timeout 45 s, duas threads, temperatura 0, seed 42, uma sequência, stops <|eot_id|> e <|end_of_text|>. Gramática vazia. O runtime reportou top-k 40, top-p 0,95, min-p 0,05.
- Desenvolvimento: carregamento 1,485 s; 113 amostras; RAM livre mínima 5.450.702.848 bytes; margem de commit mínima 13.596.229.632 bytes; pico de working set 1.353.125.888 bytes.
- Avaliação: carregamento 1,453 s; 309 amostras; RAM livre mínima 5.358.866.432 bytes; margem de commit mínima 13.537.214.464 bytes; pico de working set 1.611.898.880 bytes.
- Em ambos os grupos a proteção de entrada de 3,5 GiB e o limite de commit de 3 GiB foram respeitados; não houve encerramento por pressão, timeout ou erro do runtime. O processo encerrou normalmente após cada fase.
- truncated=false em todas as respostas indica que não houve truncamento de contexto. Quatro das seis respostas de avaliação encerraram com stop_type=limit em 96 tokens e terminam incompletas. As outras duas respostas de avaliação e as duas de desenvolvimento encerraram por EOS.
- O runtime incluiu reasoning_format=deepseek nos metadados da geração, embora o modelo seja BitNet. Não foi alterado conforme o escopo; não há evidência nesta rodada de que esse metadado tenha causado as falhas.

## Desenvolvimento — prompt typed-p11-prose-v1

**Caso dev-observed-missing** — entrada factual: estado OBSERVED, alvo poste-2, Risk NOT_EVALUATED; RF, IF, fatores, Policy e execução ausentes/nulos.

Saída bruta (15,437 s; EOS; origem modelo):

    O resumo não fornecia dados sobre a ação ou estatísticas. O Random Forest não calculou a probabilidade de ataque. O Isolation Forest não forneciu a probabilidade de ataque. O Risk Engine não calculou o risco. O Policy Engine não forneciu a ação ou a decisão. O estado da execução não foi informado. O JSON não é usado.

**Reprovado.** Não inventa ataque, mas converte RF/IF nulos em afirmações de que os detectores não calcularam, chama o IF de probabilidade, atribui ausência da decisão ao Policy Engine e contém erro gramatical. “Risk não calculou” é compatível com o status explícito NOT_EVALUATED; o mesmo não se aplica aos demais campos nulos.

**Caso dev-metrics-distinct** — entrada factual: RF 0.73, IF 0.18, Risk score 46, nível MODERATE, fatores detection=20, corroboration=21, impact=22, anomaly=23, criticality=24, XAI packet_count=140 / contribuição 0.045; calibração RF, Policy e execução nulas.

Saída bruta (11,516 s; EOS; origem modelo):

    O resumo inclui dados sobre um ataque de RandomForest, com uma probabilidade de 73%. O Status é OBSERVED, e o Risco é MÉDIO. O RandomForest detectou um risco de 46%. O RandomForest não foi calibrado. O RandomForest detectou 20% de impacto, com 23% de anomaly e 21% de corroboration. O RandomForest não foi executado.

**Reprovado.** Converte RF para porcentagem e infere um ataque; atribui Risk score e fatores ao Random Forest; associa detection=20 a impacto; afirma falta de calibração e não execução a partir de nulos; omite IF 0.18, criticality e XAI. A redação não é legível o bastante para uso.

## Avaliação fixa — prompt typed-p11-labeled-values-v2

Após revisar o desenvolvimento, foi feito um único ajuste geral: exigir rótulos separados para RF/IF/Risk/Policy/Execução, valores numéricos literais sem conversão e interpretação explícita de nulos. O conjunto de seis casos permaneceu separado do desenvolvimento.

| Caso | Duração / término | Avaliação |
|---|---|---|
| eval-missing-results | 15,266 s / EOS | **Reprovado.** Trata nulos como “não calculado”, confunde RF com calibração e contradiz as limitações dizendo que conectividade “foi fornecida” por textos que dizem que não foi. Não relata estado/decisão/execução de forma correta. |
| eval-rf-if-risk | 13,125 s / limite | **Reprovado.** Preserva os números 0.82, 0.12 e 57, mas não identifica o 0.12 explicitamente como IF; renomeia Risk Engine (“Rotaio de Risco”), chama a decisão apenas de Status e termina no meio de “detection”. Fatores incompletos e XAI omitido. |
| eval-approval-pending | 12,718 s / limite | **Reprovado.** Conserva REQUEST_APPROVAL e BLOCK_SOURCE_IP, mas entrega um dump em inglês, associa NOT_EVALUATED a RF e fatores Risk às limitações textuais. |
| eval-execution-unknown | 12,094 s / limite | **Parcial nos fatos, reprovado no caso.** Distingue AUTHORIZED de execução N/A e não afirma que a ação ocorreu. A saída é dump de campos em inglês, termina incompleta e não explica em português que a execução não foi informada. |
| eval-execution-confirmed | 12,578 s / limite | **Parcial nos fatos, reprovado no caso.** Reproduz BLOCK_SOURCE_IP e MITIGATION_CONFIRMED, mas não inclui o horário de verificação, mistura campos irrelevantes e termina incompleta em inglês. |
| eval-malicious-evidence | 11,344 s / EOS | **Reprovado.** O texto malicioso não chegou ao prompt nem à resposta; RF 0.41 e IF 0.29 aparecem com rótulos corretos. Porém troca rótulos de fatores Risk, chama o nível MODERATE de Status, omite score/fatores e não produz português compreensível. |

As respostas brutas completas (inclusive as saídas encerradas pelo limite) estão na evidência JSON vinculada acima. Em todas as chamadas de modelo, a resposta entregue pelo adaptador corresponde ao texto gerado após remover espaços nas bordas; não foi usado fallback.

## Separação dos tipos de falha

- **Seleção/preparação:** a ponte preserva os valores tipados e XAI, decisão e estado de execução sem incorporar textos livres. A ausência de conectividade no contrato impediu testar o fato “offline”; esse caso foi substituído, sem penalizar o modelo. A frase de limitação inserida pelo serviço foi contradita pelo modelo no caso eval-missing-results.
- **Instrumentação:** o primeiro relatório falhou ao serializar deque; corrigido ao materializar as amostras em lista. Uma tentativa anterior perdeu suas respostas e foi contabilizada conservadoramente com reserva de até duas chamadas. As oito respostas atuais têm relatório completo.
- **Execução:** modelo e serviço carregaram, chamadas terminaram, processos foram encerrados, sem pressão de memória, timeout ou erro de processo. Quatro saídas de avaliação bateram o teto de 96 tokens; isso causou incompletude, mas não explica as trocas semânticas presentes antes do término.
- **Fidelidade/legibilidade:** permanece reprovada. Houve preservação literal de alguns números em eval-rf-if-risk e ausência do marcador malicioso, porém também ocorreram troca/atribuição errada de campos, inferências sobre nulos, contradição, saídas em inglês e incompletude.

Os valores Risk/fatores usados são dados sintéticos de teste para distinguir campos e **não foram executados pelo Risk Engine nem validados pela fórmula** nesta rodada; não devem ser tratados como incidente nem como resultado operacional. Isso limita conclusões sobre coerência entre fatores e score, mas não explica o modelo atribuir esses campos ao Random Forest ou IF.

## Conclusão e próximo passo

O único ajuste no prompt **não demonstrou melhora global**. A preservação de dois valores decimais e a remoção do texto malicioso são evidências parciais, insuficientes diante de erros de campo, contradições, português ruim e quatro respostas cortadas. A integração determinística c2eaed6, VMs, PostgreSQL, frontend e runtime permaneceram intocados; generation_enabled continua falso.

O próximo passo limitado é verificar a origem/efeito do metadado reasoning_format=deepseek e a extração de conteúdo do endpoint /completion no runtime instalado, sem trocar o runtime nem os pesos. Se isso não explicar a linguagem/dump em inglês, documentar a falha como fidelidade do modelo/runtime e avaliar numericamente o grafo somente com uma referência independente e um plano de comparação fechado. Não repetir ajuste de prompt por caso, não integrar ao fluxo operacional.
