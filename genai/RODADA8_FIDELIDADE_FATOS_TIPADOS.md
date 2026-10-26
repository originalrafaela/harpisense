# Rodada 8 — fidelidade com fatos tipados

## Conclusão

**A fidelidade do BitNet não foi reavaliada por inferência nesta rodada.** A execução dos dois casos de desenvolvimento foi bloqueada antes de carregar o modelo: a memória física disponível ficou abaixo da política local de entrada. Portanto não há respostas novas para aprovar ou reprovar; os testes automatizados abaixo comprovam apenas o encanamento e as validações objetivas.

Foi confirmada uma falha de implementação na preparação do contexto: a saída tipada do seletor P11 inclui `risk_factors` como objeto numérico e `xai_contributions` como lista de objetos; o DTO antigo aceitava apenas escalares/listas textuais e não representava todos os campos emitidos pelo seletor. O BitNet não podia receber essa projeção completa. A ponte experimental agora valida essas estruturas com allowlists de chaves, limites e números finitos. Isso corrige a compatibilidade de dados; não comprova melhoria textual.

## Estado preservado e diagnóstico anterior

- Base: serviço `origin/bitnet`, commit `650d1cd`; branch de trabalho isolada `experiment/harpia-bitnet-fidelity`.
- A integração determinística em `integration/harpia-deterministic` (`c2eaed6`) não foi alterada.
- Históricos das rodadas 5–7 já verificaram uma aplicação do template oficial no frame do serviço, ausência de gramática/JSON constraint, entrada sem truncamento e término das gerações por EOS ou limite, sem timeout. A saída de 96 tokens chegou ao limite em alguns exemplos, mas respostas inadequadas também ocorreram antes do limite. Esses dados usaram contexto anterior, com texto livre, e não representam o experimento atual.
- As respostas históricas pós-patch de ativação continuaram reprovadas: resposta aritmética sem relação com a pergunta; no caso A, repetição e afirmação não suportada sobre execução; no caso B, confusão entre RF/IF/risco e omissão da decisão. Como a origem dos casos foi o resumo antigo com texto livre, não é evidência do comportamento com a seleção atual.
- Não foi aplicado patch novo à arquitetura ou ao runtime. O artefato registrado continua sendo o runtime BitNet `0b341e582afbf9e1011f24744b554c96a3477eb5`, submódulo llama.cpp `390c307752ab78fd8189f359d6954c9ba1be74af`, patch local identificado como `bitnet-2b4t-signature-relu2-v2`, fonte corrigido SHA-256 `e0d5113c65d15adc0ed713a43095001c747b9e036db0bd688588415bab0256b8`. O `llama-server` instalado é versão `9918 (390c30775)`, SHA-256 `a90d9162fbf6c150a850dbe510be63eee5921a0fe4b8389a45570195d854b9b7`.
- O GGUF é o snapshot oficial Microsoft `microsoft/bitnet-b1.58-2B-4T-gguf`, revisão `a1f2f1c765812aa8af3f6eda4a313707064bba15`, arquivo I2_S de 1.187.801.280 bytes, SHA-256 registrado `4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162`, licença MIT. A página oficial do snapshot identifica o repositório/modelo, licença e uso GGUF [Hugging Face, snapshot fixado](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf/tree/a1f2f1c765812aa8af3f6eda4a313707064bba15). O repositório de runtime fixado descreve o suporte BitNet/I2_S [BitNet README, commit fixado](https://github.com/microsoft/BitNet/blob/0b341e582afbf9e1011f24744b554c96a3477eb5/README.md). O patch local de ativação não é upstream e deve ser reproduzido com o helper/hash já registrado; a documentação upstream não valida esse patch nem a fidelidade da saída.

## Seleção e limites dos fatos

A entrada experimental chama o seletor existente `genai.harpia.p11.explain`, passa sua projeção por `context_from_p11` e pelo DTO existente, e chega a `Client.explanation` → serviço local `/explain` → runtime. Fixtures usam um `SyntheticStore` em memória; nenhuma gravação foi feita no PostgreSQL da VM. Logs/evidências livres não são consultados nem incluídos como texto. O caso malicioso é apenas uma string sintética em uma linha de evidência não lida pelo seletor. A separação reduz a superfície de entrada, mas não é apresentada como garantia contra prompt injection.

**Limitação comprovada do caso offline:** o seletor P11 atual não lê estado de conectividade nem uma observação textual do dispositivo. Assim, embora a fixture local contenha “Poste 2 sem comunicação; causa desconhecida” em evidência sintética, essa frase é excluída antes do prompt. O modelo recebe `target_ref=poste-2`, estado do incidente e limitações dizendo que conectividade/causa não foram fornecidas. Não é correto avaliar se ele preserva o fato “offline” quando esse fato não foi selecionado. Uma fonte tipada oficial para conectividade precisa ser definida pelo responsável do contrato/P08-P09 antes de incluir essa afirmação; não foi criada aqui.

O prompt candidato pede prosa curta em português brasileiro, somente fatos fornecidos, distingue probabilidade RF, score operacional IF e resultado Risk, reproduz decisão sem recomendá-la, trata execução ausente como desconhecida e não permite deduzir causa/ataque/risco/ação. O identificador experimental é `typed-p11-prose-v1`. O template de mensagens usa `System:/User:/Assistant:` com `<|eot_id|>`, aplicado uma vez pelo serviço. Perfil preservado: contexto 1024, saída máxima 96 tokens, 2 threads, temperatura 0, seed 42, uma sequência, timeout 45 s e stops `<|eot_id|>` / `<|end_of_text|>`. Nenhum parâmetro foi aumentado.

`valid_model_text` só rejeita respostas vazias/fora do limite, JSON evidente na primeira posição ou tokens especiais expostos. Se rejeitada, o endpoint retorna erro controlado e o cliente apresenta `deterministic_fallback` com origem identificada. Essas verificações objetivas não atestam semântica. A resposta bruta é guardada pelo verificador apenas no diretório local ignorado para revisão; o serviço normal não persiste prompts ou respostas.

## Experimento planejado e bloqueio

Conjunto de desenvolvimento (2 gerações) para revisar uma vez o prompt:

1. conectividade/causa ausentes no conjunto tipado (evidência sintética de poste offline excluída);
2. valores distintos de RF, IF e Risk, preservados por detecções/Risk tipados.

Conjunto separado de avaliação (6 gerações), somente após uma execução de desenvolvimento e eventual revisão identificada do prompt:

1. conectividade/causa ausentes;
2. RF, IF e Risk distintos com decisão `OBSERVE_ONLY`;
3. decisão `REQUEST_APPROVAL` e ação candidata `BLOCK_SOURCE_IP`;
4. decisão/ação existente sem qualquer registro de execução;
5. execução com `MITIGATION_CONFIRMED` e horário verificador;
6. referência de evidência com instrução maliciosa, excluída do prompt.

Limite total do verificador: 12 gerações sequenciais, sem retry automático. As saídas seriam revisadas por caso em contradição, invenção, troca de significado, omissão essencial, incerteza e legibilidade. Não há classificação textual nesta rodada, pois não houve inferência.

Na leitura inicial e no início do verificador:

| Medição | Valor registrado |
|---|---:|
| RAM física disponível no início do processo verificador | 3.353.145.344 bytes (3,12 GiB) |
| Limite de entrada mantido | 3.584 MiB (3,5 GiB) |
| Falta para iniciar | 404.951.040 bytes (~386 MiB) |
| Margem de commit | 3.841.232.896 bytes (3,58 GiB) |
| Limite de entrada de commit | 3.072 MiB (3 GiB) |
| Motivo | `insufficient_available_memory` |

O verificador não carregou pesos nem iniciou processo de inferência. `generation_enabled` permaneceu falso. No instante da inspeção, maiores working sets eram VMware (`vmware-vmx`, ~0,87 GiB), compressão de memória (~0,84 GiB) e processos Chrome individuais (~0,63–0,36 GiB); nenhum foi encerrado. Valores são snapshots, não perfil contínuo. A evidência local completa da tentativa está em `.local-harpia/results/fidelity-development.json` (ignorado pelo Git), contendo hashes/configuração, medição inicial e bloqueio; não contém entradas/respostas geradas.

## Verificações executadas

- `python -m unittest discover -s genai/tests`: **45 aprovados, 1 ignorado** (referência P11 opcional não configurada neste ambiente), 2,082 s.
- `py_compile` nos módulos de DTO, serviço, seletor, ponte, verificador e testes: aprovado.
- `python -m genai.scripts.verify_fidelity --help`: aprovado.
- Tentativa única da fase de desenvolvimento: bloqueada pela política de RAM antes de carregar o modelo. Não é inferência real nem validação textual.
- O primeiro comando usou `py -3.12` e não encontrou instalação global do Python; as verificações foram concluídas com o ambiente virtual BitNet existente, fora do Git.

## Conclusão e próximo passo

Houve uma correção de implementação comprovada na conversão da projeção P11 para o DTO do modelo. Não há evidência nesta rodada de que isso melhore a geração, porque nenhuma nova resposta foi produzida. O conjunto histórico continua reprovado, mas não deve ser usado como substituto do ensaio com fatos tipados. O modelo permanece sem aprovação textual e fora do caminho operacional padrão; `generation_enabled` não foi habilitado.

Próximo experimento: quando a RAM disponível alcançar 3,5 GiB sem encerrar outros programas, executar somente os 2 casos de desenvolvimento sequenciais. Revisar os textos uma vez. Se houver alteração no prompt, incrementar `PROMPT_ID` e então executar os seis casos fixos de avaliação, ainda limitado a 12 gerações total. Se a inadequação persistir com a projeção tipada, registrar o erro do modelo/runtime sem novo patch de arquitetura baseado em texto; comparar numericamente contra referência independente do grafo/kernels seria o próximo diagnóstico técnico. Nenhuma integração operacional é autorizada por esta rodada.
