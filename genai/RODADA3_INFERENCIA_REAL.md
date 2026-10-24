# Runtime compilado e primeira inferência real — 24/10/2026

**Marco técnico atingido:** CLI nativo → serviço HarpIA em loopback → adaptador,
usando pesos reais e sem fallback nas chamadas registradas. **Qualidade reprovada**:
as respostas não são explicações compreensíveis e fiéis dos dados sintéticos.
Não estão aprovadas para uso operacional ou integração com incidentes reais.

Mesma branch `feature/harpia-bitnet` e worktree. Commits `63f1c18` e `47bcd17`
preservados. Nenhum merge, push, mudança em VMs, serviços existentes, frontend
ou API P11. Nenhum download repetido de BitNet/Python/pesos. S3/IAM continuam
exclusivamente fora do fluxo operacional, para backup; BitNet não tem autoridade
de decisão/aprovação/execução. Fonte P11 v2 e contratos anteriores mantidos.

## Reconhecimento e compilação

Os dois componentes instalados pelo usuário foram reconhecidos pelo `vswhere`
e no disco da instância `695b5bcc`, VS2022 Build Tools `17.14.37806.7`:

- `Microsoft.VisualStudio.Component.VC.Llvm.Clang`: Clang 19.1.5.
- `Microsoft.VisualStudio.Component.VC.Llvm.ClangToolset`: MSBuild/ClangCL presente.

CMake 3.31.6-msvc6, MSVC 14.44.35207, Windows SDK 10.0.26100.0; CPU backend
AVX2/FMA/F16C. Runtime microsoft/BitNet permanece na revisão
`0b341e582afbf9e1011f24744b554c96a3477eb5`, submódulo llama.cpp
`390c307752ab78fd8189f359d6954c9ba1be74af` (build b9918).
Não foram alterados kernels nem pesos para obter os resultados.

Primeiro, o sandbox negou leitura do Windows SDK. O mesmo build, autorizado fora
do sandbox, passou dessa etapa; não foi necessária nova elevação administrativa.
Depois, `BUILD_SHARED_LIBS=ON`, padrão do upstream, falhou no link de ggml-base
por símbolos `quantize_i2_s` e `dequantize_row_i2_s`.
Resolvido por **configuração de ligação estática**: `BUILD_SHARED_LIBS=OFF`.

A primeira configuração também herdou o provisionamento automático da UI do
submódulo: executou npm install local no runtime (1030 pacotes) e baixou assets UI
de `https://huggingface.co/buckets/ggml-org/llama-ui/resolve/b9918/dist.tar.gz`,
com verificação de arquivo pelo script upstream. Isso ocorreu dentro da instalação
dedicada, não no frontend HarpiSense. O build npm da UI falhou por npx ausente no
ambiente e acionou o fallback de assets do upstream. Essa dependência opcional
não deveria participar do build HarpIA; a repetição foi corrigida com
`LLAMA_BUILD_UI=OFF` e `LLAMA_USE_PREBUILT_UI=OFF`. Os assets já gerados ficam locais
e removíveis junto de `.local-harpia`. Nenhum pacote global foi atualizado.
A tentativa de encerrar o build pelo PID foi recusada pela validação de identidade,
pois o processo já havia terminado; nenhum processo externo foi encerrado.

Build final: um job, CPU, sem novos downloads. Executáveis gerados:

- `.local-harpia/runtime/BitNet/build/bin/Release/llama-cli.exe`: 10.986.496 bytes.
- `.local-harpia/runtime/BitNet/build/bin/Release/llama-server.exe`: 20.994.048 bytes.

`dumpbin /DEPENDENTS` identificou `libomp140.x86_64.dll`, já disponível em System32.
Não copiamos DLLs para diretórios globais. OpenSSL ausente é irrelevante ao HTTP
de loopback desta etapa. O wrapper mantém `--no-webui` e nenhuma porta LAN aberta.

## RAM preventiva versus requisito

RAM total visível: 17.002.713.088 bytes (~15,84 GiB). Antes do primeiro build,
7.173.881.856 bytes livres (~6,68 GiB). Antes da compilação estática, o script
registrou ~7419 MiB livres. As verificações de memória foram executadas novamente
antes de carregar CLI/runtime. Nenhuma VM ou processo alheio foi encerrado.

A margem de **6656 MiB (6,5 GiB)** não bloqueou esta rodada e não foi desativada.
Ela é uma regra local preventiva: **4096 MiB de reserva para outros trabalhos +
2560 MiB de estimativa de runtime**. Não é requisito documentado do modelo nem
consumo medido. A memória real depende de contexto, KV cache, batches, threads,
versão do runtime e pressão do sistema. Os resultados abaixo permitem calibrar
um perfil futuro, mas uma amostra não justifica eliminar toda margem de segurança.

## CLI nativo: resposta real e medições

Modelo: `microsoft/bitnet-b1.58-2B-4T-gguf`, I2_S oficial, 1.187.801.280 bytes,
revisão `a1f2f1c765812aa8af3f6eda4a313707064bba15`. SHA-256 novamente conferido por
leitura, sem download: `4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162`.

Dados **sintéticos**, não incidente real:

```json
{"synthetic":true,"device":"poste-2","status":"offline","observed_at":"2026-10-24T14:00:00Z","cause":"unknown"}
```

Foi solicitado descrever estado e causa desconhecida em uma frase curta em PT-BR.
O CLI desta revisão é conversacional; o script foi adaptado para `--single-turn`,
`-sys` e `-p` separados, evitando aplicar um template duas vezes. A resposta foi
extraída entre o prompt ecoado e os timings nativos; banner não conta como geração.

Texto realmente gerado (última execução, native exit code 0):

```text
: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
```

| Medida | Observação |
|---|---|
| RAM disponível antes | 7.719.968.768 bytes (~7,19 GiB) |
| Carga + geração, parede | 9,344 s (não confundir com load time isolado) |
| Pico working set amostrado | 1.373.065.216 bytes (~1,279 GiB) |
| CPU acumulada | 17,8125 s, somando threads |
| Velocidade nativa informada | prompt ~65,8 tokens/s; geração ~13,8 tokens/s |
| Geração | até 48 tokens, contexto 1024, 2 threads, GPU layers 0, temperature 0, seed 42 |
| Encerramento | código nativo 0 e processo finalizado |

A primeira execução já havia gerado o mesmo texto, em 9,172 s, mas a impressão do
relatório no terminal CP1252 falhou por caracteres do banner. O JSON UTF-8 tinha
sido salvo corretamente e o executável nativo saiu 0. A saída de console do
verificador foi corrigida para JSON ASCII-escaped, preservando arquivos UTF-8.
Uma repetição confirmou o script completo com exit 0; não foi necessário recompilar.

## Serviço real → adaptador

O verificador iniciou **um** `llama-server` residente em `127.0.0.1:8092`, após o CLI
ser encerrado; o serviço HTTP HarpIA usou `127.0.0.1` com porta efêmera. Não houve
duas cópias simultâneas do modelo, frontend direto ou conexão com HarpiServer.

| Medida | Resultado |
|---|---|
| RAM disponível antes da carga | 7.614.197.760 bytes (~7,09 GiB) |
| Carga até health do runtime indicar pronto | 1,563 s, incluindo warmup padrão |
| Geração simples direta pelo runtime | 6,546 s |
| Ocorrência sintética pelo serviço/cliente | 14,141 s |
| Caso com facts ausentes | 2,219 s |
| Campo de dados malicioso | 1,672 s |
| Repetição do primeiro contexto | 0,000 s na resolução da medição; cache, não nova inferência |
| Maior working set/pico informado na sessão | 1.474.203.648 bytes (~1,373 GiB) |
| CPU acumulada do runtime | 50,265625 s |
| Perfil | contexto 2048; até 160 tokens por explicação; 2 threads; batch/microbatch 128; uma sequência; temperature 0; seed 42; GPU layers 0 |
| Encerramento | runtime aguardado e finalizado; nenhum llama-cli/llama-server desta sessão deixado ativo |

A GPU não foi usada (runtime CPU-only); não se atribui a ele o uso de VRAM de
outros processos. Working set não equivale a memória privada comprometida nem
ao impacto total do sistema; o pico amostrado pode perder picos entre leituras.
Load time é prontidão operacional, não qualidade. As amostras não são benchmark geral.

A origem foi verificada de duas formas: instância do runtime real sem mock e
SHA-256 do texto recebido pelo adaptador correspondente ao retorno da geração
real. Todos os casos retornaram `source=bitnet_unverified_text`,
`bitnet_status=responded_unverified`; **nenhum foi fallback**.
O primeiro texto da ocorrência sintética teve hash:
`cd8b0d4cce78578b618801b489d57d449dbcf4cfa2831d03f5cf04b290937cbe`.

## Inspeção qualitativa: reprovada

Entrada `synthetic-real-001`: RF `0.82`, IF `0.12`, risco UNKNOWN, decisão
INSUFFICIENT_DATA, operação IDS e execução desabilitada. Nada autorizava concluir
ataque ou contenção.

Trecho **real** da resposta, preservado como texto, sem interpretá-lo como comando:

```text
{"facts": 0,  "decision_status": "Open",  "execution_enabled": "false",  "if_anomaly_score": 0.82,  "risk_level": "Unknown",  "status": "Open",  "operation_mode": "Open", ...
```

O trecho termina aqui por abreviação do relatório; a resposta integral, com campos
repetidos até o limite de geração, está em `real-model.json`. Problemas concretos:

- Transferiu `0.82` de RF para IF, cujo valor informado era `0.12`.
- Substituiu IDS por “Open” e não preservou a decisão INSUFFICIENT_DATA.
- Produziu JSON repetitivo/truncado em vez de explicação compreensível em PT-BR.
- Com facts ausentes retornou `{"facts": 0, "incident_id": 0, "revision": 1}`;
  isso inventa valores no texto, embora o envelope HTTP preserve ID/revisão corretos.
- No caso malicioso respondeu `1}`; não constitui evidência de resistência a
  prompt injection nem de execução de ação. Nenhuma saída foi executada.

Conclusão limitada aos testes: **esta combinação de runtime/pesos/configuração
executa, mas não está adequada para explicar incidentes**. Não prova incapacidade
geral do BitNet, nem permite atribuir a falha só ao português. A causa ainda não
foi isolada entre implementação de inferência, compatibilidade de quantização,
template e comportamento do modelo. O CLI rotulou `ftype` como Q1_0 apesar do
artefato oficial I2_S; isso é uma discrepância para investigar, não prova isolada
de que os tensores tenham sido interpretados com outro tipo.

Próximo trabalho deve diagnosticar essa coerência com a mesma evidência e sem
substituir silenciosamente o modelo. Até lá, manter o backend independente da LLM
e o fallback explícito disponível. Nenhuma alteração em Risk/Policy/execução foi feita.

## Validação e reprodução

**22 testes unitários/HTTP passaram em 1,953 s**, sem skips na execução registrada,
incluindo adaptador P11 original e três testes novos que impedem contar banner,
prompt ou timings do CLI como texto gerado. Esses testes usam runtime simulado;
as inferências descritas acima são reais e separadas da suíte.

```powershell
Set-Location 'D:/Projetos/tcc - harpisense/harpisense-worktrees/harpia-bitnet'
& ./genai/scripts/install-build-tools.ps1
& ./genai/scripts/build.ps1
& .local-harpia/venv/Scripts/python.exe -m genai.scripts.verify_cli
& .local-harpia/venv/Scripts/python.exe -m genai.scripts.verify_real
```

Para apenas iniciar o serviço, configuração e encerramento seguem o README.
Os verificadores saem com sucesso ao comprovar execução/origem; **não são testes
de aprovação semântica**, que reprovou na inspeção desta entrega.

Artefatos locais, ignorados pelo Git:

- `build-prerequisites.json`, `memory-before-build.json`.
- `cmake-configure.txt`, `cmake-build.txt` (build estático aprovado).
- `round3-shared-build-failure.txt` (tentativa anterior e erro de link).
- `real-cli.json`, `cli-stdout.txt`, `cli-stderr.txt` (última geração nativa).
- `round3-first-cli.json` (primeira inferência, antes da correção de console).
- `real-model.json` (entradas, respostas completas, tempos, memória e hashes).
- `unit-http-round3.txt` e `runtime.log`.

Arquivos versionáveis alterados nesta rodada: `genai/scripts/build.ps1`,
`genai/scripts/verify_cli.py`, `genai/scripts/verify_real.py`,
`genai/tests/test_harpia.py`, `genai/README.md`, `genai/RELATORIO.md`,
`genai/RODADA2_COMPILACAO.md`; adicionado este relatório. Pesos/binários/logs não
entram no Git. Instruções de remoção seletiva em `genai/README.md` continuam válidas.
