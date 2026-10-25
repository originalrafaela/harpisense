# Atualização mais recente — rodada 5

[RODADA5_PERFIL_ECONOMICO.md](RODADA5_PERFIL_ECONOMICO.md): orçamento real por
tokenizer, resumo P11 limitado, proteção de RAM/commit monitorada e duas gerações
reais A/B. Transporte aprovado; ambas as respostas reprovadas em qualidade textual.
Geração permanece fora do caminho operacional.

## Histórico — rodada 4

Consulte [RODADA4_TEMPLATE.md](RODADA4_TEMPLATE.md): template explícito preservado,
24 testes aprovados e smoke sem modelo aprovado. Inferência nova bloqueada pela
proteção de RAM; qualidade textual continua sem aprovação. Detalhes da diferença
de templates em [AUDITORIA_PROMPT.md](AUDITORIA_PROMPT.md).

# Verificações HarpIA / BitNet — 24/10/2026

**Registro histórico da primeira entrega.** Consulte a atualização
[RODADA2_COMPILACAO.md](RODADA2_COMPILACAO.md), incluindo a correção da medição
de memória do wrapper: os 4,22 MiB abaixo mediam o launcher da venv, não o
interpretador completo. O commit original `63f1c18` permanece preservado.
O estado mais recente está em [RODADA3_INFERENCIA_REAL.md](RODADA3_INFERENCIA_REAL.md):
runtime compilado e inferência real comprovada, com qualidade reprovada nos casos observados.

Entrega independente do P08–P11 em execução com outro agente. Branch
`feature/harpia-bitnet`, base `9d58e69` (`main`), worktree
`D:\Projetos\tcc - harpisense\harpisense-worktrees\harpia-bitnet`.
A base foi escolhida por conter a arquitetura compartilhada e o diretório `genai`
reservado, sem importar alterações em desenvolvimento das branches de backend ou
frontend. Referências P03/P11 v2 foram lidas no disco, fora da nova worktree.
Nenhum merge, push, publicação ou alteração nas VMs/serviços existentes.

## Resultado objetivo

| Pergunta | Resultado observado |
|---|---|
| BitNet foi baixado? | Sim: fonte oficial, submódulo fixado e pesos oficiais íntegros. Não há executável compilado. |
| Modelo foi carregado? | Não. Falta ClangCL; RAM livre também abaixo da margem conservadora. |
| Inferência real? | Não executada. O verificador real registrou bloqueio. |
| Serviço local? | Implementado e iniciado/testado em loopback sem modelo. Saúde 200, prontidão 503. Encerrado ao final. |
| Alternativa testada? | Sim: cliente real HTTP → wrapper indisponível → fallback identificado com ID/revisão. |
| Consumo? | Apenas wrapper medido: working set pontual 4.427.776 bytes (~4,22 MiB), início ~0,547 s e fallback ~0,032 s. Sem medição de inferência. |
| Integração HarpiServer? | Pendente: compilação/RAM/inferência, conexão autenticada futura e ligação/persistência do adaptador na API. |

## Ambiente observado

- Windows 11 Home Single Language, versão 10.0.26300, 64 bits.
- Intel Core i7-10750H @ 2,60 GHz, 6 núcleos/12 processadores lógicos.
- RAM visível: 17.002.713.088 bytes (~15,84 GiB). Os ~26 GB informados pelo usuário
  não foram confirmados como RAM física utilizável. Não alteramos alocação de VMs.
- RAM livre: primeira inspeção CIM 750.720 KiB (~733 MiB); leituras posteriores
  via GlobalMemoryStatusEx ~0,90–1,46 GiB durante o trabalho. São amostras, não
  monitoramento contínuo nem capacidade reservável para BitNet.
- D: ~228,47 GiB livres inicialmente; C: ~39,00 GiB. Download foi para D:.
- NVIDIA GeForce GTX 1650, VRAM 4096 MiB, driver 581.57. Amostra inicial mostrou
  1414 MiB em uso por aplicações existentes e GPU util 13%; não é consumo de BitNet.
- GPU não foi usada por esta entrega; execução de modelo em CPU ainda pendente.
- VS2022 Build Tools 17.14.37806.7, MSVC 14.44.35207, Windows SDK 10.0.26100.0,
  CMake 3.31.6-msvc6 e VS2026 Community também presentes. Clang format/tidy presentes;
  compilador ClangCL e integração LLVM no VS2022 ausentes.
- `py` informava nenhum Python instalado no contexto inicial. Venv antiga de
  backend apontava para Python312 removido/inacessível. Nenhuma foi alterada.
- Python 3.12.13 dedicado foi obtido e venv criada; biblioteca padrão basta para
  serviço, cliente e testes. uv existente foi usado como instalador, sem atualização.
- Nenhuma instalação BitNet prévia foi encontrada nas áreas do projeto inspecionadas.
  Isso não equivale a inventário completo de todos os discos ou serviços do host.

## Aquisição, integridade e falhas diagnosticadas

Fontes e revisões completas em [artifacts.lock.json](artifacts.lock.json):

- Runtime: `https://github.com/microsoft/BitNet.git`, revisão
  `0b341e582afbf9e1011f24744b554c96a3477eb5`.
- Submódulo: `https://github.com/isHuangXin/llama.cpp.git`, commit
  `390c307752ab78fd8189f359d6954c9ba1be74af`, exatamente como referenciado pelo runtime oficial.
- Modelo: `https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf`, revisão
  `a1f2f1c765812aa8af3f6eda4a313707064bba15`, `ggml-model-i2_s.gguf`.
- Tamanho esperado e observado: **1.187.801.280 bytes**.
- SHA-256 esperado (metadados LFS oficiais) e observado (Get-FileHash):
  `4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162`.
- Python via uv, pacote oficial de dependência:
  `https://github.com/astral-sh/python-build-standalone/releases/download/20260602/cpython-3.12.13%2B20260602-x86_64-pc-windows-msvc-install_only_stripped.tar.gz`.
- Template conferido em
  `https://huggingface.co/microsoft/bitnet-b1.58-2B-4T/raw/main/tokenizer_config.json`.
  Essa consulta foi da versão main na data do relatório; o template em código foi
  registrado e não acompanha atualizações automaticamente.
- Licenças runtime/modelo: MIT, consultadas nos respectivos repositórios oficiais.
- Total de arquivos da instalação dedicada na amostra: 1.429.555.503 bytes
  (~1,33 GiB), incluindo runtime, Python/venv e pesos; pequenos resultados posteriores
  podem alterar esse total. Nenhum arquivo grande entrou no Git.

Primeira tentativa de rede no sandbox foi negada; comandos necessários foram
reexecutados com autorização de acesso externo, sem alterar políticas de rede.
Checkout do submódulo falhou por nomes longos no Windows; resolvido com
`git -c core.longpaths=true submodule update --init --recursive`, **sem mudar Git global**.
O servidor da ferramenta reiniciou durante aquisição; estado foi conferido e o
download retomado de 46.395.392 bytes. Hash final confirmou integridade.

Configuração CMake inicialmente encontrou leitura de SDK negada pelo sandbox.
Reexecutada fora do sandbox, revelou o bloqueio efetivo:

```text
error MSB8020: Não foi possível encontrar as ferramentas de compilação para
ClangCL (Conjunto de Ferramentas de Plataforma = 'ClangCL').
```

Comando diagnóstico executado com CMake do VS2022:

```powershell
& 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe' -S .local-harpia/runtime/BitNet -B .local-harpia/runtime/BitNet/build -G 'Visual Studio 17 2022' -A x64 -T ClangCL
```

Não houve reinstalações repetidas, substituição por outro modelo ou tentativa de
usar MSVC sem Clang contra a exigência do upstream. O script `build.ps1` detecta
o pré-requisito ausente antes de repetir a configuração.

**Ação do administrador:** adicionar pelo Visual Studio Installer, ao Build Tools
2022, C++ Clang Compiler for Windows >=18 e MSBuild support for LLVM (clang-cl)
toolset. Pode exigir UAC. Essa modificação global não foi aplicada.
Depois, disponibilizar RAM suficiente sem interromper automaticamente as VMs,
compilar e executar o verificador real. O serviço exige por padrão 6656 MiB livres
(4096 MiB de reserva + 2560 MiB de margem de execução); não confundir isso com
consumo medido ou requisito mínimo oficial do modelo.

## Verificações executadas

Última suíte: **19 testes aprovados em 1,863 s**, sem skips na execução registrada.
`HARPIA_P11_REFERENCE` foi apontada ao `backend11/bitnet.py` original do pacote v2;
o teste importou esse arquivo sem editá-lo e chamou o HTTP `/complete` deste serviço.
Em outra máquina, esse teste específico pula se a referência não for configurada.

| Verificação solicitada | Execução / evidência |
|---|---|
| Runtime e modelo | Fonte e pesos íntegros; configuração CMake bloqueada em ClangCL. `verify_real`: `runtime_or_model_missing`, modelo não carregado, nenhuma inferência. |
| Inferência simples real | Pendente, sem resultado simulado apresentado como real. Script preparado. |
| Ocorrência sintética identificada | HTTP real com runtime simulado; ID/revisão preservados. Caso real preparado no verificador. |
| Campos ausentes | Contexto sem facts aceito no HTTP simulado; campos ausentes não viram métricas zero. Fallback real sem facts testado. |
| Entrada inválida/excessiva | Revisão bool, NaN, envelope inesperado, texto excessivo, corpo >16 KiB e tokens inválidos rejeitados antes de geração. |
| Timeout/indisponibilidade | 504 simulado do runtime, timeout real de socket do cliente e prontidão 503 real sem modelo; fallback explícito. |
| Explicação alternativa | Origem `deterministic_fallback`, rótulo em PT-BR, ID/revisão, motivo `http_503`; verificada no processo real. |
| Texto malicioso | Teste de serialização/neutralização de delimitadores e exclusão de password/log; sem avaliação de resistência do modelo real. |
| Repetição/concorrência | 4 chamadas no cliente resultam em 1 geração simulada; cache do servidor também testado. Rajada de 5 requisições distintas: máximo 1 geração simultânea, excesso 429. |
| Encerramento/liberação | Wrapper real recebeu stop por stdin, saiu 0 e porta fechou. Término do processo de runtime em falha foi testado com mock; liberação de pesos reais pendente. |
| Autenticação e browser | Token inválido 401, Origin e Host indevidos 403, bind não loopback rejeitado. Sem testes externos/LAN. |
| Validação de resposta | Texto >3000 e ID divergente causam fallback; origem/source validada. |

`verify_local` iniciou um subprocesso real do serviço sem modelo, em porta efêmera
loopback, e observou:

```text
/health: 200 {service: active}
/ready: 503 {model_loaded: false, ready: false}
início do wrapper: ~0,547 s
fallback HTTP: ~0,032 s
working set / pico informado pela API do processo: 4.427.776 bytes
CPU do wrapper informada por GetProcessTimes: 0,0 s
exit_code: 0; shutdown_verified: true; port_closed: true
```

Memória é uma leitura pontual do working set sob pressão de RAM, não memória
privada comprometida nem estimativa do modelo. CPU retornou zero nessa amostra
curta; não permite concluir custo zero. Não houve perfil contínuo de CPU/GPU,
medição de energia ou tokens/s. Qualidade em português de BitNet **não avaliada**;
os textos do fake runtime são declaradamente simulados. O fallback contém português
UTF-8, conferido no JSON persistido; a renderização do terminal pode mostrar mojibake.

Artefatos locais não versionados:

- `.local-harpia/results/unit-http.txt`: saída da suíte com 19 testes.
- `.local-harpia/results/local-smoke.json`: métricas e resultado HTTP real sem modelo.
- `.local-harpia/results/smoke-service.log` e `smoke-config.json`: processo de teste.
- `.local-harpia/results/real-model.json`: bloqueio do verificador real.
- `.local-harpia/runtime/BitNet/build/CMakeFiles/CMakeConfigureLog.yaml`: diagnóstico CMake.

Compilação Python (`compileall`), análise sintática dos scripts PowerShell e
`git diff --check` passaram. `prepare.ps1 -PythonPath <Python dedicado> -DownloadModel`
foi executado e confirmou pesos íntegros/Python 3.12.13. O build não passou do
pré-requisito; os argumentos do servidor foram conferidos no código do upstream,
mas seu funcionamento só poderá ser confirmado com binário compilado.

## Integração pendente e limites

Não há teste com HarpiServer, frontend integrado, incidentes reais ou executor.
Não houve alteração de Risk/Policy/autonomia/operação, banco, Mosquitto, firewall,
rede ou arquivos das VMs. O modelo não possui ferramentas ou acesso administrativo.
Defesas de prompt não autorizam afirmar proteção completa.

O contrato público `explanation` continua pertencendo ao XAI. A extensão `/explain`
é DTO de transporte auxiliar do contexto P11; `/complete` preserva compatibilidade.
O cliente novo é opt-in, ainda não importado por P11. O adaptador P11 antigo limita
timeout a 3 s e não suporta o token deste serviço: adotar o cliente novo quando
habilitar autenticação e ajustar o orçamento de latência, mantendo compatibilidade
do chamador e controle de carga. O fallback usa a redação existente, adaptada com
rótulo e vínculo explícito, sem duplicar o Policy Engine.

O backend deverá montar resumos validados, usar cliente com URL/token próprios,
persistir o resultado com revisão/origem e expor pela API já escolhida para P11.
O frontend em `integration-p11` já diferencia origens e lê histórico/projeções;
o GET explain da referência não persiste esse histórico automaticamente.
O README enumera os arquivos reais e mapeamentos a ajustar. Não há confirmação
da árvore implantada na VM; sua integração deverá ser feita pelo responsável P08–P11.
Uma ligação autenticada/túnel será necessária: localhost da VM não é o Windows.
Nenhuma dessas mudanças de acesso foi aplicada.

## Arquivos da entrega

Alterado: `.gitignore` (somente regra `.local-harpia/`). Adicionados:

- `genai/__init__.py`
- `genai/harpia/__init__.py`
- `genai/harpia/contracts.py`
- `genai/harpia/client.py`
- `genai/harpia/runtime.py`
- `genai/harpia/server.py`
- `genai/harpia/__main__.py`
- `genai/config.example.json`
- `genai/.env.example`
- `genai/artifacts.lock.json`
- `genai/scripts/prepare.ps1`
- `genai/scripts/build.ps1`
- `genai/scripts/verify_local.py`
- `genai/scripts/verify_real.py`
- `genai/tests/test_harpia.py`
- `genai/README.md`
- `genai/RELATORIO.md`

Nenhum peso, venv, credencial, runtime externo ou resultado volumoso foi incluído
no código versionável. Remoção seletiva e comandos exatos estão no README.
