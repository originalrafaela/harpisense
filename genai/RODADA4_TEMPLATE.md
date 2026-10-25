# Template explícito e verificação bloqueada por RAM — 24/10/2026

**Resultado: correção de formatação coberta por testes; qualidade textual ainda
reprovada pela rodada 3 e não reavaliada com modelo nesta rodada.** Zero novas
inferências. Não há evidência para atribuir a falha anterior ao template.

## Estado e escopo

Confirmado HEAD inicial `ab9e2a4`, branch `feature/harpia-bitnet`, destino
`origin/bitnet`. Preservadas as alterações preexistentes em `contracts.py`,
`verify_cli.py`, `test_harpia.py` e `AUDITORIA_PROMPT.md`. A auditoria foi lida;
seu registro histórico de ausência de push refere-se àquela etapa.

Referências locais consultadas: P11 em
`referencias/versão_v2/11_Backend_Dashboard_BitNet/HarpiSense_Pacote11_Backend_Dashboard_BitNet_v2/backend11/bitnet.py`
e exemplos `risk_signal.json` dos pacotes Random Forest e Isolation Forest de
`referencias/Versões corretas`. A versão v2 tem prioridade; componentes anteriores
continuam válidos quando não atualizados. Sem acesso ao Drive ou varredura geral.
IF fornece `anomaly_score`, limiar e margem próprios; não equivale à probabilidade
RF nem autoriza bloqueio. Os valores dos exemplos não são os valores sintéticos
0,82/0,12 solicitados para o próximo teste.

## Mudança preservada e verificações acrescentadas

CLI: `--jinja --chat-template CHAT_TEMPLATE`, com `-sys` e `-p` separados. O Jinja
explícito usa `System:/User:/Assistant:` e EOT, substituindo a seleção automática
do legado `Human:/BITNETAssistant:` embutido no GGUF. O relatório CLI registra
o template. Não há `frame()` prévio no CLI.

Serviço: `/explain` chama `prompt()`/`frame()` uma vez e o runtime envia o texto
para `/completion`, sem segundo template de chat. BOS continua sob responsabilidade
do tokenizer; EOT e end_of_text terminam a resposta. O adaptador recebe somente
`content`, sem concatenar o prompt; o CLI extrai somente o trecho entre eco e
timings. A inspeção detalhada dos tokens permanece em `AUDITORIA_PROMPT.md`.

Nesta rodada foram reforçadas as asserções do transporte HTTP para conferir o
prompt completo e exatamente dois EOT, além de endpoint `/completion`, stops,
limite de tokens, temperatura e seed. Nenhum parâmetro operacional, contrato
Risk/Policy, VM, frontend ou API P11 foi alterado. Não houve download, troca de
pesos, recompilação ou alteração do runtime.

## Tentativa real e memória

Executado `python -m genai.scripts.verify_cli` com o Python dedicado da worktree.
O verificador bloqueou **antes de criar o processo nativo**:

| Campo | Observação |
|---|---|
| RAM total | 17.002.713.088 bytes |
| RAM disponível na primeira inspeção | 1.853.964.288 bytes (~1,73 GiB) |
| RAM disponível no verificador CLI | 2.800.410.624 bytes (~2,61 GiB) |
| Proteção preservada | 4096 + 2560 MiB = 6,5 GiB |
| Motivo | `insufficient_available_memory` |
| Inferência / duração da geração | não executada / não se aplica |
| Saída do modelo ou fallback nessa tentativa | nenhuma |

Entrada preparada pelo verificador: teste sintético de poste-2 offline, causa
desconhecida, observado em `2026-10-24T14:00:00Z`, pedindo frase curta em português.
Perfil registrado, **não executado**: 48 tokens, contexto 1024, 2 threads, CPU,
temperatura 0, seed 42. O JSON local `.local-harpia/results/real-cli.json` registra
`inference_executed=false` e `process_stopped=true`. Não se considera esta entrada
um teste completo do caso A, pois não explicita a ausência de evidência de ataque.
Não foi chamado `verify_real`, que faria mais gerações que o limite solicitado.
Não houve tentativa de liberar memória nem de diminuir a proteção.

| Caso solicitado | Resposta observada nesta rodada | Fidelidade |
|---|---|---|
| A: poste 2 sem comunicação, causa desconhecida, sem evidência de ataque | nenhuma; bloqueado por RAM | não avaliada |
| B: RF 0,82 e score operacional IF 0,12, fatores e decisão existentes | nenhuma; não carregado o runtime | não avaliada |

A confusão RF/IF e repetição documentadas na rodada 3 continuam sendo a última
evidência textual real. A preservação das chaves nos testes não comprova que o
modelo preservará os valores na resposta.

## Verificações executadas

- `python -m unittest genai.tests.test_harpia -v`: **24 testes aprovados**,
  1,898 s, sem skips, com `HARPIA_P11_REFERENCE` apontando ao P11 v2 local.
  Inferência simulada; inclui adaptador original, loopback, cache, limites,
  proteção de memória, fallback, tokens e extração da saída.
- `python -m genai.scripts.verify_local`: **smoke sem modelo aprovado**.
  Health 200, ready 503, retorno `source=deterministic_fallback` por HTTP 503.
  Início do wrapper 0,562 s, fallback 0,031 s, working set 25.686.016 bytes,
  RAM disponível antes 2.909.835.264 bytes. Saída 0, encerramento e porta fechada
  confirmados. Esse texto é fallback, nunca resposta BitNet.
- `verify_cli`: bloqueio preventivo confirmado, não aprovação de inferência.

Resultados locais permanecem ignorados em `.local-harpia/results/`; só código,
testes e documentação entram no commit. Não se publicou peso, runtime, ambiente,
credencial ou configuração privada.

## Pendências e próximo experimento

Quando houver RAM suficiente, executar **somente duas gerações sequenciais**, A e B,
com template corrigido e registro de entrada completa, saída, parâmetros, tempos,
memória e origem. Preferir serviço em loopback → adaptador para validar o caminho
de integração. No B, fornecer RF 0,82 e IF 0,12 com fatores/decisão de um snapshot
sintético validado pelos contratos; não fabricar risco ou decisão para preencher
campos. Não registrar os testes como incidentes reais.

Manter temperatura 0 e seed 42 inicialmente, limite curto compatível com a resposta
e proteção atual. Conferir incerteza no A e valores/semântica no B, ausência de
causa inventada, recálculo ou ação alegadamente executada. Duas respostas boas
representariam apenas validação inicial, sem isolar causalmente o template.
Não executar `verify_real` completo para esse experimento limitado.

Se persistir a falha, inspecionar compatibilidade entre o GGUF I2_S e o runtime
fixado, incluindo a identificação `ftype Q1_0`, sem presumir erro de tensores.
Formato do prompt, compatibilidade e comportamento do modelo continuam hipóteses;
não há justificativa nesta rodada para baixar pesos ou recompilar tudo.

Geração continua experimental e fora do caminho operacional padrão: nenhum backend
passou a importar o cliente. Para conectar ao HarpiServer, primeiro aprovar essa
validação inicial, depois mapear a árvore implantada do P11, adotar transporte
opt-in com orçamento de latência adequado, origem/revisão persistidas e fallback
explícito. Manter loopback mediante túnel autenticado planejado para a VM;
`127.0.0.1` da VM não aponta ao Windows. Nenhuma conexão ou mudança de VM foi feita.
