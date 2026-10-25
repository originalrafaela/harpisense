# Auditoria restrita de prompt e resposta — 24/10/2026

Branch local `feature/harpia-bitnet`, iniciada limpa em `ab9e2a4`. Investigação
restrita a `contracts.py`, `runtime.py`, `server.py`, `client.py`, verificadores
CLI/serviço, testes diretamente relacionados, relatório da rodada 3 e arquivos
do runtime que aplicam templates/tokenizam/retornam a conclusão. Referência local:
`referencias/versão_v2/11_Backend_Dashboard_BitNet/HarpiSense_Pacote11_Backend_Dashboard_BitNet_v2/backend11/bitnet.py`.
Nenhuma referência necessária ausente; sem varredura geral, instalação, download
de artefatos, alteração de pesos/runtime, VM, frontend ou push.

## Diferença concreta encontrada

O template embutido no **GGUF já instalado**, lido diretamente do cabeçalho, é:

```jinja
{% for message in messages %}{% if loop.first %}{{ bos_token }}{% endif %}{% if message['role'] == 'user' %}{{ 'Human: ' + message['content'] + '\n\nBITNETAssistant: ' + eos_token }}{% elif message['role'] == 'assistant' %}{{ message['content'] + eos_token }}{% endif %}{% endfor %}
```

O [tokenizer oficial do modelo](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T/blob/main/tokenizer_config.json)
publica outro formato: `System: ...<|eot_id|>User: ...<|eot_id|>Assistant: `.
O CLI escolhia automaticamente o template do GGUF; o serviço montava o segundo
formato em `frame()` e chamava `/completion`, que **não aplica template de chat**.
Portanto as duas execuções da rodada 3 não usaram a mesma formatação.

O template legado não tem ramo `system`. Isso **não comprova perda das instruções**:
o runtime fixado possui workaround que pode fundir uma mensagem system com a
próxima mensagem quando o template não suporta esse papel (`common/chat.cpp`).
A diferença de formatação é confirmada; sua responsabilidade pela resposta ruim
continua sendo hipótese, especialmente porque o serviço já usava o formato oficial.

Correção mínima: `CHAT_TEMPLATE`, cópia do Jinja oficial em `contracts.py`, passado
explicitamente por `verify_cli.py` com `--jinja --chat-template`. O serviço continua
com seu formato já existente; não houve refatoração do transporte ou do contrato.
O relatório futuro do CLI também registra o template escolhido. A decisão de
priorizar o tokenizer oficial elimina a diferença entre os caminhos, sem afirmar
que os metadados embutidos sejam prova de como todos os pesos foram treinados.

## Tokens e resposta

Metadados locais: BOS `128000` = `<|begin_of_text|>`, EOS `128001` =
`<|end_of_text|>`, `add_bos_token=true`; EOT `128009` = `<|eot_id|>` existe no
vocabulário. O tokenizer oficial usa EOT como EOS. O runtime detecta EOT pelo
texto do token (`src/llama-vocab.cpp`), mesmo quando EOS do GGUF é outro ID.
Cabeçalhos genéricos Llama 3 `<|start_header_id|>` / `<|end_header_id|>` existem
no vocabulário, mas não fazem parte do template oficial deste modelo.

`frame()` não insere BOS manualmente. Tanto CLI quanto `/completion` usam a
tokenização do runtime com `add_special=true, parse_special=true`; não é necessário
acrescentar outro BOS. O serviço já limita a conclusão por EOT/end_of_text.

A [documentação do servidor fixado](https://github.com/isHuangXin/llama.cpp/blob/390c307752ab78fd8189f359d6954c9ba1be74af/tools/server/README.md)
distingue `/apply-template` (formata, sem inferência) de `/completion` (gera a
continuação e devolve `content`). O código HarpIA lê somente `content`; não concatena
o campo `prompt`. No CLI, banner, prompt ecoado e timings são separados pelo
verificador; a sequência numérica da rodada 3 estava realmente no trecho gerado,
não no prompt de entrada. Não foi encontrado erro de extração nesses casos.

RF e IF: `context_dto()` preserva separadamente `rf_attack_probability=0.82` e
`if_anomaly_score=0.12`; `prompt()` serializa ambos com suas chaves intactas.
Não há mapeamento para um score comum. A troca desses valores na resposta da
rodada 3 ocorreu no texto gerado, não no transporte. Não alteramos o contrato XAI,
os valores nem a redação do SYSTEM para tentar mascarar a falha.

## Testes e observação

Sete testes diretamente relacionados passaram: formato oficial em `frame()`,
identidade RF/IF no contexto serializado, retorno de `content` sem eco, três
casos de separação da saída CLI e neutralização dos delimitadores nos dados.
São verificações com respostas simuladas; não provam compreensão do modelo.

**Zero inferências reais novas nesta rodada.** Leituras de memória disponível
ficaram em aproximadamente 5,14–5,53 GiB durante a inspeção, abaixo da margem
preventiva existente de 6,5 GiB. Não reduzimos/desativamos a proteção nem liberamos
RAM encerrando outros trabalhos. O limite autorizado de duas inferências não
foi consumido. A nova formatação ainda não foi confirmada com o runtime em execução.

A única resposta real observada é a evidência histórica da rodada 3:
`: 0, 1, 2, ...`; no serviço houve JSON repetitivo que associou `0.82` ao IF,
quando esse número pertencia ao RF. Não são respostas de um teste após a correção.

**Pendência:** com memória suficiente, comparar no máximo duas gerações curtas
sequenciais com mesmo conteúdo e perfil, variando somente a formatação antiga
versus oficial, e revisar português/fidelidade. Não usar `verify_real` completo
para essa comparação restrita, pois ele faz mais de duas gerações. Qualidade
continua reprovada; esta correção não encerra o diagnóstico.

Artefatos locais ignorados: `.local-harpia/results/prompt-audit-metadata.json`
(metadados lidos, sem pesos) e `prompt-audit-tests.txt` (saída dos testes).
Arquivos alterados: `genai/harpia/contracts.py`, `genai/scripts/verify_cli.py`,
`genai/tests/test_harpia.py`; adicionado este registro. Sem push.
