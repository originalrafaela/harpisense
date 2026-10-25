# Diagnóstico de geração — 25/10/2026

**Encontrada e corrigida uma divergência funcional da FFN no runtime instalado.**
As quatro gerações desta rodada ocorreram **antes** da correção e reprovaram.
Compilação incremental corrigida e testes passaram; não houve quinta geração.
A correção ainda precisa de validação textual real. Não se comprovou que seja
a única causa da falha; o modelo não está liberado para explicar incidentes.

HEAD inicial `a17e24cd7c155fe19fe6c3f5f8bf1d3727bc7415`, worktree limpa,
`feature/harpia-bitnet` acompanhando `origin/bitnet`. Lidos o relatório 5 e suas
entradas/saídas integrais, serviço, runtime, DTO, cliente e adaptador P11 v2 local.
Referências continuam em `referencias/versão_v2` e, para RF/IF não atualizados,
`referencias/Versões corretas`. Não houve Drive, mudança de contratos, frontend,
HarpiServer, banco, MQTT, VMs, pesos ou configurações do Windows.

## Compatibilidade e erro concreto

- Revisão local BitNet: `0b341e582afbf9e1011f24744b554c96a3477eb5`; submódulo
  `390c307752ab78fd8189f359d6954c9ba1be74af`. Executável informa b9918/390c30775,
  Clang 19.1.5 x64. Fontes inicialmente limpas.
- GGUF oficial instalado: mesmo SHA-256
  `4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162`, conferido
  novamente. Cabeçalho GGUF v3, arquitetura `bitnet-b1.58`, 30 camadas, dimensão
  2560, FFN 6912, 20 cabeças/5 KV, contexto declarado 4096, vocabulário 128256.
- Inspeção local somente leitura: 332 tensores; 210 tipo 36/I2_S, 121 F32 e um F16.
  Os 210 spans I2_S correspondem a dados de 2 bits mais cauda de escala alinhada;
  todas as escalas lidas são positivas/finitas (0,7442138–4,596097). Sem divergência
  de offsets/tamanho encontrada. Isso **não é teste numérico dos kernels**.
- `general.file_type=40` vira rótulo Q1_0 no enum atual, enquanto os tensores
  permanecem I2_S=36; não se corrigiu metadado/quantização apenas por esse rótulo.

A [configuração oficial](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T/blob/482c7a7/config.json)
define `hidden_act=relu2`. A [implementação indicada pela ficha do modelo](https://raw.githubusercontent.com/huggingface/transformers/096f25ae1f501a084d8ff2dcaf25fbc2bd60eba4/src/transformers/models/bitnet/modeling_bitnet.py)
aplica a ativação configurada à projeção gate, multiplica pela up, normaliza e
aplica down. No runtime fixado, `src/models/bitnet.cpp:133` usava incondicionalmente
`LLM_FFN_SILU`; a arquitetura GGUF `bitnet-b1.58` é despachada para
`llama_model_bitnet_b158`, que herda esse grafo de `llama_model_bitnet`
(`src/models/models.h:1318`). Portanto a diferença **atinge o modelo instalado**,
não apenas outro arquivo ou modelo legado.

Em `llama-graph.cpp`, SiLU com gate paralelo usa SwiGLU, enquanto o ramo
`LLM_FFN_RELU_SQR` faz ReLU, quadrado e a multiplicação pelo gate paralelo antes
da normalização externa. A diferença de função não é uma escolha de prompt ou
sampler. Constitui erro de compatibilidade do grafo em relação à configuração
publicada; sua contribuição causal para os textos ruins ainda exige inferência
após corrigir. Outros erros de kernel, pesos/tokenizer ou comportamento podem coexistir.

Correção mínima aplicada: selecionar `LLM_FFN_RELU_SQR` somente para 30 camadas,
preservando SiLU para os legados. Helper versionado `scripts/patch_runtime.py`,
idempotente, verifica as duas revisões e o SHA-256 exato do fonte antes de escrever.
Não sobrescreve modificações inesperadas. `build.ps1` aplica o helper antes de
compilar; o lock registra revisão **mais patch local**, sem fingir mudança de commit
upstream. Arquivo alterado localmente continua ignorado junto do runtime.

SHA do fonte original: `d7bf43b007b97c38e7110932846c02361eb15b351850b8c1a5bcdc36e25daea5`;
após patch: `5dfd6758d25c0e632100a305b31297882a817b9c8c33a3226f08141d2fa1a4ec`.

Compilação incremental CPU, um job, dos alvos llama-server/llama-cli **aprovada**.
Primeira tentativa falhou por sandbox negar leitura do SDK em AppData; repetição
autorizada fora do sandbox passou. `bitnet.obj` recompilado às 11:47:11, posterior
ao fonte corrigido às 11:45:36; servidor ligado às 11:47:15. Sem download de pesos
ou troca do runtime. O build reaproveitou assets UI locais antigos e avisou ausência
de gzip/OpenSSL; não houve build do frontend HarpiSense, nem UI operacional
(wrapper continua `--no-webui`). Estes avisos não invalidaram a compilação.

## JSON, template, tokenização e término

Conferidas [instruções BitNet da revisão instalada](https://github.com/microsoft/BitNet/blob/0b341e582afbf9e1011f24744b554c96a3477eb5/README.md)
e `run_inference.py`: execução CPU de GGUF I2_S é suportada; temperatura upstream
padrão 0,8 difere da configuração determinística local 0. Não houve alteração
de sampler nesta rodada. Ganhos oficiais não foram atribuídos a esta máquina.

O [tokenizer oficial](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T/blob/main/tokenizer_config.json)
publica `System:/User:/Assistant:` com EOT, igual ao frame do serviço. GGUF ainda
embute template legado; `/completion` recebe o texto já formatado e não o reaplica.
Os quatro prompts processados retornados pelo runtime são exatamente o texto
enviado com **um único BOS acrescentado**, sem cabeçalho duplo ou remoção de dados.
O GGUF tem EOS 128001; EOT 128009 existe, é reconhecido e consta dos stops locais.

Nenhuma gramática/JSON schema/response_format é enviada pelo serviço. O processo
é iniciado com ambiente LLAMA_* removido e sem flags de gramática. A resposta bruta
de **cada** geração informa `generation_settings.grammar=""`. `/props` indica
uma sequência e contexto 1024. POST JSON é apenas transporte, não restrição de saída.

O DTO contém JSON e muitos nulls, podendo induzir continuação de JSON; não há
exemplos few-shot pedindo JSON de saída. Porém a primeira tarefa sem DTO também
falha, gerando contagem numérica. Isso impede atribuir tudo à serialização P11.
No A foi pedido explicitamente texto corrido/sem JSON e a resposta continuou JSON.

[Documentação do servidor fixado](https://github.com/isHuangXin/llama.cpp/blob/390c307752ab78fd8189f359d6954c9ba1be74af/tools/server/README.md):
`stop_type` separa EOS, limite e stop textual; `truncated` informa excesso de contexto.
Nas quatro respostas, **truncated=false** e contagens cabem com folga em 1024:

| Teste | Caminho | Entrada | Saída real/máxima | Término | Parede |
|---|---|---:|---:|---|---:|
| 1 | Runtime direto, frame oficial, sem DTO P11 | 254 | 96/96 | limit | 10,672 s |
| 2 | Transporte cliente → serviço `/complete` → runtime | 263 | 26/96 | eos | 2,578 s |
| 3 | Client → serviço `/explain`, caso A em texto | 414 | 96/96 | limit | 10,157 s |
| 4 | Client → serviço `/explain`, caso B | 497 | 96/96 | limit | 11,171 s |

Os 96 tokens cortaram a **saída** em 1/3/4, mas já havia repetição/omissão desde
o início; não foi cortada uma explicação fiel demonstrada. O teste 2 falha mesmo
terminando por EOS antes do limite. Não houve timeout nem aumento de contexto/saída.
Não é possível afirmar o que o modelo produziria com limite maior; não há evidência
que justifique ampliá-lo para tentar resolver a divergência da FFN.

## Resultados e controles

Instrução comum 1/2: “Responda em português, em uma frase de texto, sem JSON:
quanto é dois mais dois?”. Resultado esperado: frase curta que diga quatro.
Teste 1 preserva SYSTEM HarpIA, mas não usa P11/JSON de incidente. Teste 2 usa
mesma instrução, com a proteção legada que adiciona `Dados legados P11:` e aspas
JSON. Os prompts diferem em 9 tokens: comparação de caminhos, **não ablação pura
de transporte**. Os prompts completos e saídas estão na evidência sanitizada.

1. Direto: `1. 2. 3. ... 32.` (abreviação só nesta lista; saída integral no JSON).
   Reprovado, não responde à pergunta.
2. Serviço: `1: "Responda em português, em uma frase de texto, sem JSON: quanto é dois mais?"`.
   Reprovado, eco semântico/reformulação da tarefa, não resultado. É texto gerado,
   não concatenação do prompt pelo adaptador.
3. A: JSON repetindo nulls, sem explicar poste offline e causa desconhecida.
   Reprovado, apesar do pedido explícito de texto.
4. B: mesmo padrão repetitivo da rodada 5, sem RF 0,82, IF 0,12 e OBSERVE_ONLY.
   Reprovado por omissão, sem concluir que houve troca numérica nesta rodada.

A/B retornaram `source=bitnet_unverified_text`, `responded_unverified`, sem fallback;
teste 2 usa o envelope legado `{text}` sem campo de origem. No teste 1 não há
adaptador: a origem direta foi rotulada no diagnóstico, sem simular fallback.
Os quatro textos entregues são iguais ao `content` bruto após `strip()` existente.
O teste 1 tinha espaço final: a checagem inicial comparou bytes sem normalização
e fez o verificador sair 1, apesar da inferência real. Corrigida apenas a prova
de origem do verificador para usar `valid_text`, preservando o bruto. Não se
reexecutou a geração para obter exit 0. Teste automatizado cobre essa diferença.

Memória antes: 4.830.138.368 bytes disponíveis (~4,50 GiB), commit total
16.791.666.688, limite 31.498.227.712. 140 amostras durante a execução; menor
disponível 3.459.190.784 (~3,22 GiB), menor margem de commit 14.461.181.952,
maior working set 1.395.838.976 (~1,30 GiB), maior privado 265.203.712 bytes.
Carga 1,438 s, nenhuma proteção acionada, runtime encerrado e aguardado. Limites
da rodada 5 preservados; não foram encerrados Chrome/VMs. Números são amostras
de teste curto, não consumo máximo garantido ou benchmark. Todos os casos são
sintéticos, separados de incidentes reais.

## Validação, recomendação e comparação opcional

**36 testes unitários/HTTP aprovados**, sem skips, 2,174 s, P11 v2 local incluído.
Novos testes: observação bruta preserva término/JSON settings e só retira espaços
das bordas na entrega; patch rejeita fonte inesperado e é idempotente. Build nativo
corrigido aprovado. Esses testes não validam qualidade textual nem equivalência
numérica completa da FFN/I2_S. Nenhuma inferência ocorreu após aplicar a correção.

Recomendação principal: **validar primeiro o BitNet corrigido**, em nova rodada
curta, com os mesmos prompts/perfil e captura bruta de término. Agora existe
uma diferença funcional demonstrada para corrigir; seria prematuro concluir
que o modelo falha com um runtime matematicamente correto ou substituí-lo.
Se a falha persistir, comparar numericamente o grafo/kernels e depois considerar
comparação isolada, sem alterar o fluxo operacional.

Pré-checagem de uma alternativa futura: a [família Qwen3 declara português](https://qwenlm.github.io/blog/qwen3/)
e há [Qwen3-0.6B-GGUF oficial Q8_0](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/tree/main)
de 639 MB. Tamanho em disco **não é RAM necessária**; runtime, buffers e KV somam
memória. Não foi identificado Q4_K_M nesse repositório oficial consultado, portanto
não se promete essa variante. [Uso oficial com llama.cpp](https://qwen.readthedocs.io/en/latest/run_locally/llama.cpp.html)
é documentado; isso não comprova execução no fork BitNet instalado.

Se essa comparação vier a ser necessária: instalação/pasta e runtime separados,
revisão/hash fixados, template Qwen próprio, modo sem thinking e mesmas entradas
sintéticas; começar com contexto 1024, saída curta e os mesmos monitores, medir
RAM/commit em vez de inferir do arquivo. A ficha recomenda amostragem própria
para não-thinking (temperatura 0,7, top_p 0,8, top_k 20, min_p 0 e presence penalty
1,5); registrar que isso difere do greedy BitNet, sem atribuir diferenças somente
ao modelo. Português declarado não garante fidelidade do 0.6B neste domínio.
**Não baixado, instalado, executado ou usado como substituto nesta rodada.**

HarpIA continua local/loopback e experimental. Resumo P11, controles, fallback e
limites de autoridade foram preservados. Não houve integração ao HarpiServer.

## Evidências e reprodução

- `scripts/diagnose_generation.py`: até quatro gerações sequenciais, mantém bruto
  somente na subclasse diagnóstica. Runtime normal não armazena prompts/respostas.
- `DIAGNOSTICO6_SINTETICO.json`: entradas, requests/saídas brutas e entregues
  completas, parâmetros efetivos, tempos, contagens e provas sanitizadas.
- `.local-harpia/results/generation-diagnostic.json`: original local, com amostras
  e `/props`, preservado; `model-layout-audit.json`, helper local de inspeção de
  cabeçalho e `runtime-activation-patch.json`: ignorados pelo Git.
- `python -m genai.scripts.patch_runtime`: reaplica idempotentemente a correção
  somente no fonte fixado; `genai/scripts/build.ps1 -Jobs 1` compila.

Executar o diagnóstico novamente consumirá novas gerações: não foi feito nesta
rodada após o patch. Pesos, fontes/binários externos, ambientes e segredos não
entram no commit; apenas o helper mínimo e o lock da alteração ficam versionados.
