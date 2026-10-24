# Retomada da compilação — 24/10/2026

Branch `feature/harpia-bitnet`, mesma worktree, iniciada limpa no commit `63f1c18`.
Esse commit não foi reescrito. README/relatório/código existentes foram conferidos.
Nenhum download de Python, runtime ou pesos foi repetido. Nenhuma alteração em
VMs, frontend, API P11, Mosquitto ou processos de outros trabalhos. Loopback mantido.
BitNet continua exclusivamente explicativo; S3/IAM não participam da operação local.

## Bloqueio concreto e intervenção necessária

O cache CMake existente registra:

```text
CMAKE_GENERATOR=Visual Studio 17 2022
CMAKE_GENERATOR_INSTANCE=C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools
CMAKE_GENERATOR_TOOLSET=ClangCL
```

Instalação confirmada pelo `vswhere`: Build Tools 2022, instância `695b5bcc`, versão
`17.14.37806.7` (produto 17.14.42). O VS2026 também instalado não é o selecionado.

Dois componentes estão **ausentes no registro do instalador e no disco**:

| ID oficial | Componente | Arquivo esperado ausente |
|---|---|---|
| `Microsoft.VisualStudio.Component.VC.Llvm.Clang` | C++ Clang Compiler for Windows (catálogo VS2022: 19.1.5) | `VC/Tools/Llvm/x64/bin/clang-cl.exe` |
| `Microsoft.VisualStudio.Component.VC.Llvm.ClangToolset` | MSBuild support for LLVM (clang-cl) toolset | `MSBuild/Microsoft/VC/v170/Platforms/x64/PlatformToolsets/ClangCL/Toolset.props` |

Fonte: [catálogo oficial VS2022](https://learn.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-build-tools?view=vs-2022).
Isso explica o `MSB8020` anterior; alterar apenas PATH não instala o toolset.

A sessão atual retorna `IsInRole(Administrator)=false`. A instalação programática
silenciosa não está disponível a usuário padrão, conforme a
[documentação oficial](https://learn.microsoft.com/en-us/visualstudio/install/use-command-line-parameters-to-install-visual-studio).
Não tentamos elevar, alterar políticas ou contornar UAC. Não iniciamos uma instalação
que não pudesse concluir com as permissões atuais.

Ação exata no **Visual Studio Installer**:

1. Localizar **Ferramentas de Build do Visual Studio 2022**, não VS2026 Community.
2. Escolher **Modificar → Componentes individuais**.
3. Marcar **C++ Clang Compiler for Windows** e **MSBuild support for LLVM (clang-cl) toolset**.
4. Manter os componentes já selecionados. Confirmar **Modificar** e atender UAC,
   caso solicitado. Não forçar fechamento de aplicações nem reiniciar automaticamente.

Alternativa reproduzível: abrir **PowerShell como administrador** e executar:

```powershell
Set-Location 'D:/Projetos/tcc - harpisense/harpisense-worktrees/harpia-bitnet'
& ./genai/scripts/install-build-tools.ps1 -Install
```

Esse script primeiro verifica a instância e os dois componentes. Só adiciona os
dois IDs e dependências obrigatórias, via `setup.exe modify --quiet --norestart`.
Não usa `--force`, remoção ou update; saída 3010 exige combinar reinício, sem fazê-lo.
Executado sem `-Install`, apenas gera diagnóstico em
`.local-harpia/results/build-prerequisites.json`, como foi feito nesta rodada.

## Recursos e execução

RAM física visível permaneceu 17.002.713.088 bytes (~15,84 GiB). Leituras desta
rodada: 2.211.893.248 a 2.393.329.664 bytes livres (~2,06–2,23 GiB), oscilando com
os outros trabalhos. Nenhum processo foi encerrado para obter memória.

O build passa a ter um job por padrão, mínimo conservador de 1536 MiB livres e
nova leitura de RAM antes de configurar/compilar. A instalação VS2022 fica fixa
explicitamente no CMake e os logs são persistidos. O limiar não garante que todo
build caiba nessa RAM; deve-se acompanhar a pressão do sistema.

O perfil de inferência mantém sua margem original: 4096 MiB reservados + 2560 MiB
de provisão para runtime, total 6656 MiB livres para iniciar. A memória atual não
atingiu essa margem; não foi reduzida silenciosamente. O administrador deve
disponibilizar recursos compatíveis antes da inferência, sem automação que pare VMs.

O verificador CLI foi executado e registrou `native_cli_or_model_missing`: os
pesos existem com 1.187.801.280 bytes, mas `llama-cli.exe` ainda não foi produzido.
Portanto **não houve compilação bem-sucedida, carregamento nem inferência real**.
Nenhum texto sintético de fake runtime é apresentado como saída de BitNet.
O build atualizado detecta a falta do compilador antes de tentar repetir o CMake.

Após resolver instalação e RAM, os comandos preparados são:

```powershell
& ./genai/scripts/install-build-tools.ps1
& ./genai/scripts/build.ps1
& .local-harpia/venv/Scripts/python.exe -m genai.scripts.verify_cli
& .local-harpia/venv/Scripts/python.exe -m genai.scripts.verify_real
```

`verify_cli` usa o executável nativo oficial, confere SHA-256 dos pesos sem baixar
novamente, gera até 48 tokens com contexto 1024, 2 threads, GPU layers 0,
temperature 0 e seed 42. Dados explicitamente **sintéticos**: poste-2 offline,
horário 2026-10-24T14:00:00Z e causa desconhecida. Não há serviço nem fallback nesse
teste. Registra stdout/stderr, tempo total de carga+geração e pico amostrado de RAM;
os timings internos de carga/avaliação ficam no stderr nativo.

Somente após um CLI real bem-sucedido, `verify_real` carrega o runtime residente,
mede sua prontidão/carga e faz chamadas pelo serviço/cliente. Correlaciona o hash
do texto retornado pelo adaptador com respostas recebidas diretamente de chamadas
reais do runtime. Exige `source=bitnet_unverified_text` e hash correspondente;
fallback não passa como inferência. Casos sintéticos e respectivas saídas ficam
em `real-model.json`, para revisão explícita de português e fidelidade.
Nenhum desses passos é integração com HarpiServer ou frontend.

## Verificação independente concluída

- Suíte existente: **19 testes aprovados em 1,911 s**, com adaptador P11 v2 original;
  runtime simulado nesses testes. Sintaxe Python e scripts PowerShell conferida.
- Smoke do serviço real sem modelo: saúde 200, prontidão 503, alternativa
  `deterministic_fallback`, motivo `http_503`, saída 0 e porta fechada após encerramento.
- Início do wrapper: ~0,547 s; fallback HTTP: ~0,047 s.
- Medição corrigida do **interpretador**: working set 25.681.920 bytes (~24,49 MiB),
  pico informado 25.710.592 bytes (~24,52 MiB), CPU 0,140625 s.
- Correção da entrega anterior: o Windows usa um launcher no `python.exe` da venv.
  Os 4,22 MiB / CPU 0 daquela execução se referiam ao launcher e subestimavam o
  processo completo. O smoke agora usa diretamente o Python base dedicado, seguro
  porque o serviço só depende da biblioteca padrão. Não são métricas do modelo.
- Qualidade de português e fidelidade **do BitNet real permanecem não avaliadas**.
  Não há texto gerado por BitNet para revisar nesta rodada até resolver os bloqueios.

Artefatos locais: `build-prerequisites.json`, `real-cli.json`, `unit-http-round2.txt`,
`local-smoke.json`, `smoke-service.log`, além dos arquivos da rodada anterior.
Os resultados novos continuam fora do Git. Downloads e pesos foram preservados.

## Referências e arquivos

Confirmadas nesta rodada ambas as pastas reais:
`D:/Projetos/tcc - harpisense/referencias/versão_v2` e
`D:/Projetos/tcc - harpisense/referencias/Versões corretas`.
Esta última contém backend operacional v1, contratos unificados, base consolidada,
adaptadores, modelos RF/IF e outros pacotes anteriores. Não foi necessário substituir
o P11 v2 por um deles; nenhuma referência obrigatória desta etapa foi declarada
ausente pela simples falta na v2.

Alterados: `genai/README.md`, `genai/RELATORIO.md`, `genai/scripts/build.ps1`,
`genai/scripts/verify_real.py`, `genai/scripts/verify_local.py`.
Adicionados: este relatório, `genai/scripts/install-build-tools.ps1` e
`genai/scripts/verify_cli.py`. Sem alterações nos contratos operacionais ou pesos.
