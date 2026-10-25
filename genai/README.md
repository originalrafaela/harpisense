# HarpIA / BitNet local no Windows

**Branch isolada de comparação:** `experiment/harpia-model-comparison`, baseada em
650d1cd, sem substituir a entrega BitNet ou a interface. Resultado e reprodução em
[COMPARACAO_MODELOS.md](COMPARACAO_MODELOS.md): doze inferências reais BitNet/Qwen
Q4_K_M; ambos reprovam nos casos críticos. Recomenda-se somente fallback no caminho
operacional enquanto a fidelidade não for suficiente. Artefatos novos são ignorados
em `.local-harpia/comparison/`; perfil Qwen é explicitamente opt-in.

Implementação isolada em `feature/harpia-bitnet`, base `9d58e69`, worktree
`D:\Projetos\tcc - harpisense\harpisense-worktrees\harpia-bitnet`.
Código em `genai/`; runtime, Python/venv, pesos, configuração local e resultados em
`.local-harpia/`, ignorada pelo Git. Sem integração ao fluxo operacional.

**Estado atual:** runtime compilado e inferência real executada no CLI e no fluxo
serviço → adaptador. A origem no modelo foi comprovada, mas as respostas falharam
em compreensão/fidelidade e **não estão aprovadas para explicar incidentes**.
Diagnóstico mais recente: [RODADA6_DIAGNOSTICO.md](RODADA6_DIAGNOSTICO.md).
Validação após o patch: [RODADA7_VALIDACAO_PATCH.md](RODADA7_VALIDACAO_PATCH.md).
Seletor restrito por arquitetura e dimensões, três inferências reais com EOS;
fidelidade continua reprovada. Build grava manifesto local com hashes CLI/servidor.
O grafo da FFN usava SiLU onde o modelo de 30 camadas exige ReLU². O build agora
aplica um patch local mínimo, fixado por hash em `artifacts.lock.json`, antes de
compilar. Build corrigido e inferência após o patch executados; fidelidade reprovada. Não basta
conferir `--version`: a revisão upstream permanece a mesma, acrescida do patch.
Perfil econômico e duas novas respostas reais reprovadas em
[RODADA5_PERFIL_ECONOMICO.md](RODADA5_PERFIL_ECONOMICO.md); histórico em
[RODADA3_INFERENCIA_REAL.md](RODADA3_INFERENCIA_REAL.md).
Um HTTP 200 de `/health` não significa que o modelo esteja carregado; prontidão
também não constitui aprovação de qualidade.

Diagnóstico atualizado da retomada, IDs exatos para instalação e correção da
medição de memória do wrapper: [RODADA2_COMPILACAO.md](RODADA2_COMPILACAO.md).

## Referências e escolha

Referências reais disponíveis na pasta principal `referencias/versão_v2/`:

- `03_Contratos/HarpiSense_Etapa03_Contratos_Catalogo_V2/03_Contratos/CONTRATOS_OFICIAIS.md`,
  sua fonte `base_consolidada_atualizada/harpisense_contracts/schema_source.py` e catálogo.
- `11_Backend_Dashboard_BitNet/HarpiSense_Pacote11_Backend_Dashboard_BitNet_v2/backend11/bitnet.py`,
  `service.py`, `BITNET_INTEGRACAO_LIMITES_E_FALLBACK.md` e contratos API.
- Backend/frontend legados estão preservados **dentro do pacote P11**. Na segunda
  rodada foi confirmada também `D:\Projetos\tcc - harpisense\referencias\Versões corretas`,
  com os pacotes anteriores. Priorizar sempre `versão_v2`; consultar os anteriores
  somente quando o componente necessário ainda não estiver atualizado. Nenhum acesso ao Drive foi usado.
- `docs/DECISOES_ARQUITETURAIS.md` e `docs/CONTRATOS_COMPARTILHADOS.md` da base Git.

O **runtime** escolhido é [microsoft/BitNet](https://github.com/microsoft/BitNet),
`bitnet.cpp`, revisão fixada em [artifacts.lock.json](artifacts.lock.json).
O submódulo llama.cpp vem do endereço e commit referenciados pelo próprio upstream,
não de uma distribuição binária alternativa. O **modelo** é
[microsoft/bitnet-b1.58-2B-4T-gguf](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf),
arquivo I2_S oficial de 1.187.801.280 bytes. Ambos têm licença MIT.
O **serviço HarpIA** é este código Python, que mantém um `llama-server.exe` residente
e se comunica por HTTP privado em loopback. Não é um modelo e não treina pesos.

CPU x86 é suportada oficialmente; o i7-10750H é compatível com esse perfil, mas a
compilação e execução já foram comprovadas, sem aprovação textual. Usamos 2 threads, GPU layers 0,
contexto 1024, batch/microbatch 128, uma sequência,
temperature 0, seed 42 e até 96 tokens gerados por padrão. Não usamos Transformers, CUDA ou
WSL. A ficha do modelo indica inglês; a qualidade em português exige avaliação real.
Não se extrapolam os números de benchmark publicados para esta máquina.

O template foi conferido no
[tokenizer_config.json oficial](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T/blob/main/tokenizer_config.json):
`System: ...<|eot_id|>User: ...<|eot_id|>Assistant: `.
Não é o template genérico com `start_header_id` do Llama 3. A aquisição de pesos
fica presa à revisão e ao SHA-256; atualizar a revisão requer revalidar template/runtime.

## Preparar e compilar

Abra PowerShell no diretório desta worktree:

```powershell
Set-Location 'D:\Projetos\tcc - harpisense\harpisense-worktrees\harpia-bitnet'
& ./genai/scripts/prepare.ps1 -DownloadModel
```

O script usa `uv` já existente para baixar Python 3.12.13 para `.local-harpia/python`,
cria venv dedicada, obtém o runtime fixado e confere tamanho/SHA-256 dos pesos.
Não reinstala arquivos íntegros. Downloads incompletos usam `.partial`; o download
feito nesta sessão já foi validado. Alternativa sem uv: informe
`-PythonPath 'C:/caminho/python.exe'` (Python >=3.10 com venv).
O serviço depende somente da biblioteca padrão. Não há instalação pip global.
Python dedicado foi distribuído pelo projeto oficial `astral-sh/python-build-standalone`
via uv; URL registrada no relatório. Nenhuma venv antiga foi reparada ou alterada.

**Ação necessária do administrador:** no Visual Studio Installer, modificar
**Build Tools 2022**, em `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools`,
adicionando **C++ Clang Compiler for Windows** (Clang >=18) e **MSBuild support for
LLVM (clang-cl) toolset**, mantendo Desktop development with C++/Windows SDK/CMake.
Essa alteração pode exigir elevação/UAC. O usuário instalou esses componentes antes
da terceira rodada; Clang 19.1.5 e toolset foram reconhecidos, resolvendo MSB8020.
Veja [instruções da Microsoft](https://learn.microsoft.com/en-us/cpp/build/clang-support-msbuild?view=msvc-170).

Depois:

```powershell
& ./genai/scripts/build.ps1
```

Para diagnóstico reproduzível, sem modificar Visual Studio:

```powershell
& ./genai/scripts/install-build-tools.ps1
```

Alternativa ao Installer gráfico: abrir **PowerShell como administrador**, ir à
worktree e executar `& ./genai/scripts/install-build-tools.ps1 -Install`. O script
usa a instalação VS2022 já existente e adiciona somente os dois IDs acima mais
dependências obrigatórias, com `--quiet --norestart`; sem `--force` ou update.
Não tenta obter elevação, mudar políticas ou reiniciar. Se sair 3010, a janela de
reinício deve ser combinada pelo administrador. Não repetir instalação com sucesso:
o diagnóstico verifica os dois componentes registrados e arquivos esperados.

O build usa o Developer Shell do VS2022 e compila apenas `llama-server` e
`llama-cli`, com paralelismo **1 por padrão**, ajustável para 2 com `-Jobs 2`.
Confere RAM novamente (mínimo conservador 1536 MiB livres para iniciar o build),
Clang >=18 e toolset; fixa explicitamente a instalação VS2022 no CMake.
Logs ficam em `.local-harpia/results/cmake-configure.txt` e `cmake-build.txt`.
O caminho padrão esperado é
`.local-harpia/runtime/BitNet/build/bin/Release/llama-server.exe`.
Esse build foi validado na terceira rodada com Clang 19.1.5 e AVX2.
Usa `BUILD_SHARED_LIBS=OFF` para resolver os símbolos I2_S que falharam no link de
DLLs, e `LLAMA_BUILD_UI=OFF` / `LLAMA_USE_PREBUILT_UI=OFF` para evitar provisionamento
opcional da UI. A execução do serviço mantém `--no-webui`.
O I2_S já está convertido; não é necessário baixar BF16 ou instalar PyTorch.
OpenSSL não foi encontrado, mas não é necessário ao HTTP exclusivo de loopback
desta entrega. Não habilitar acesso LAN/Internet com essa configuração.

## Iniciar e encerrar

```powershell
Copy-Item genai/config.example.json .local-harpia/config.json
# Opcional: definir HARPIA_TOKEN em ambos os processos, via segredo local.
# $env:HARPIA_TOKEN = '<segredo-local-não-versionado>'
& .local-harpia/venv/Scripts/python.exe -m genai.harpia --config .local-harpia/config.json
```

`Ctrl+C` encerra o HTTP e termina/aguarda o runtime que este processo iniciou.
Para um supervisor local, `--stdin-control` permite escrever `stop` + newline na
entrada padrão. Não há endpoint HTTP administrativo de shutdown. Não use múltiplos
workers ou múltiplas instâncias, pois cada uma carregaria outra cópia do modelo.

Na configuração local, porta do serviço 8091 e do runtime 8092 são ajustáveis;
ambos aceitam somente `127.0.0.1`. Se mudar a porta, ajuste a URL do cliente.
O host é validado explicitamente, não pode ser `0.0.0.0`. Não habilitamos CORS,
rede local, firewall, inicialização automática ou serviço do Windows.

Verifique RAM antes de iniciar:

```powershell
& .local-harpia/venv/Scripts/python.exe -m genai.harpia --inspect
```

O perfil experimental exige **3584 MiB (3,5 GiB) disponíveis**, em três amostras,
e 3072 MiB de margem de memória comprometida do Windows. Durante carga, geração
e ociosidade, monitora a cada 250 ms: interrompe somente o runtime próprio se RAM
livre cair abaixo de 768 MiB, ficar abaixo de 1024 MiB por três amostras, a margem
de commit cair abaixo de 1024 MiB ou working set/memória privada superar 2304 MiB.
Os limites estão em `memory_policy` no JSON; justificativa e limitações no relatório
da rodada 5. Não são requisitos oficiais ou máximos garantidos. Não desligue VMs.
Configuração antiga que informe `reserve_memory_mb` mantém também a proteção
legada `reserve_memory_mb + 2560 MiB` (mínimo 6,5 GiB); migre explicitamente para
o novo JSON se desejar o perfil experimental. O verificador CLI histórico mantém
6,5 GiB e não é o executor do novo perfil monitorado.
Threads 1–4 e contexto 512–4096 são os limites deste perfil. Se o executável/pesos
faltarem ou a margem falhar, o serviço continua vivo com prontidão negativa.

Sem modelo, para testar só o wrapper:

```powershell
& .local-harpia/venv/Scripts/python.exe -m genai.harpia --no-model
```

Em outro terminal (acrescente Bearer via header se configurar `HARPIA_TOKEN`):

```powershell
Invoke-RestMethod http://127.0.0.1:8091/health
Invoke-RestMethod http://127.0.0.1:8091/ready
```

`/health`: serviço ativo, 200. `/ready`: 200 apenas se o processo pertencente ao
wrapper está vivo e o `/health` do **runtime** informa `status=ok`; caso contrário
503 com `model_loaded=false`. Isso não é avaliação de qualidade nem warmup de geração.
O load time termina nessa prontidão; a primeira inferência é medida separadamente.

## Formatos e limites

`POST /complete` mantém o wire format do adaptador P11 aprovado:
`{"prompt":"Explique somente os fatos...", "max_tokens":160}` → `{"text":"..."}`.
O prompt legado é tratado como dado, encapsulado no template do serviço.

`POST /explain` é uma extensão **auxiliar local opt-in** para preservar o contexto
P11 `{incident_id,revision,facts}` de ponta a ponta. Não é um endpoint implantado
no HarpiServer, nem um novo contrato canônico `explanation` de XAI.

```json
{
  "incident_id": "synthetic-inc-001",
  "revision": 1,
  "facts": {
    "status": "OPEN",
    "operation_mode": "IDS",
    "execution_enabled": false,
    "autonomy_mode": 1,
    "risk_level": "UNKNOWN",
    "limitations": "Exemplo sintético; sem RF/IF/XAI e sem executor."
  }
}
```

Resultado do modelo: `incident_id`, `revision`, `source=bitnet_unverified_text`,
`bitnet_status=responded_unverified`, `text`. O cliente valida esses campos,
descarta campos extras e preserva origem. Falha HTTP, autenticação, timeout,
identidade divergente ou resposta inválida gera `source=deterministic_fallback`,
rótulo explícito de alternativa e motivo técnico (status HTTP ou classe do erro, sem payload).
O fallback adapta a redação do P11; não mantém um segundo motor de decisão.
Faltas de formato na entrada levantam erro de validação antes de consultar a LLM.

Corpo JSON até 16 KiB, contexto sanitizado até 12000 bytes, identificador ASCII até
128 caracteres, revisão inteira positiva, até 64 campos em facts. Campos
permitidos: [contracts.py](harpia/contracts.py), no máximo 500 caracteres por
texto, escalares finitos ou null. `observed_facts`, `evidence_summary`, `xai_summary`,
`risk_factors` e `limitations` também aceitam até 8 strings de 160 caracteres cada.
Campos desconhecidos em `facts` são descartados;
campos desconhecidos no envelope são rejeitados. Nunca envie segredos, PCAPs ou
logs brutos. O produtor deve minimizar e remover segredos **antes** de montar DTOs,
inclusive em textos permitidos; uma allowlist não identifica todos os segredos.
Padrões óbvios de credenciais em texto permitido são rejeitados, sem retornar o valor.

Antes da inferência, o serviço conta o prompt completo pelo `/tokenize` local com
BOS e tokens especiais, reservando saída e 16 tokens de margem. Limite de dados
para o modelo: 6000 bytes, além do orçamento de contexto configurado. Se exceder,
remove primeiro `xai_summary` e depois `evidence_summary` inteiros, em ordem fixa,
com aviso no prompt e `omitted_context_fields` no resultado do adaptador. Fatos
essenciais devem estar em `observed_facts`; decisões, RF/IF, fatores Risk e limitações
nunca são cortados. Se ainda não couber, HTTP 422 e fallback identificado no cliente.
Não há corte silencioso nem context shift. O backend valida os contratos canônicos
antes de projetar os resumos; esta camada não recalcula seus resultados.

Até 8 handlers HTTP; 1 geração e 2 lugares de espera; espera até 2 s; excesso
retorna 429 (503 no limite de conexões); socket de entrada 5 s; geração 45 s por
padrão; preparação limitada a 5 s; saída até 3000 caracteres/96 tokens por padrão.
`output_tokens` aceita 1–160 para manter a compatibilidade P11. `max_waiting` permite
0–2 esperas e `queue_wait_seconds` permite 0–2 s. Mutex Windows impede duas instâncias
controladas do runtime na mesma sessão Windows, mesmo em portas diferentes.
Timeout/falha de inferência termina
o runtime pertencente ao wrapper, evitando geração abandonada; reiniciar o wrapper
é necessário para recarregar após essa falha. Falha de carga tem limite de 90 s.
O HTTP do wrapper começa a atender depois dessa tentativa inicial.

Cache em memória de até 64 respostas por 5 minutos, hash do contexto sanitizado
completo (incluindo ID/revisão), por instância; não é persistência de auditoria.
Não cacheia fallback. Cliente serializa chamadas locais com espera limitada; não
faz retries. Timeout de cliente padrão 60 s divide orçamento entre espera e chamada
HTTP (os sockets usam timeout de I/O; não é garantia de deadline contra servidor
malicioso que envie bytes indefinidamente). Não usa proxies do ambiente nem segue
redirecionamentos. Logs do wrapper contêm duração/classe de erro, nunca prompt/token.
Logs detalhados do runtime ficam desabilitados para evitar registrar dados.

Dados de telemetria são serializados como JSON, delimitadores especiais são
neutralizados e o system prompt proíbe seguir instruções nos dados. Isso é defesa
em profundidade, não comprovação de imunidade a prompt injection. Nenhuma saída é
interpretada como comando/JSON operacional. O serviço não importa Risk, Policy,
executor nem ferramentas administrativas.

## Testar

```powershell
& .local-harpia/venv/Scripts/python.exe -m unittest discover -s genai/tests -v
& .local-harpia/venv/Scripts/python.exe -m genai.scripts.verify_local
# Depois de compilar e dispor de RAM: inferência real, seguida de encerramento
& .local-harpia/venv/Scripts/python.exe -m genai.scripts.verify_cli
& .local-harpia/venv/Scripts/python.exe -m genai.scripts.verify_real
```

`verify_cli` faz primeiro uma geração sintética curta diretamente no executável
oficial, sem serviço ou alternativa; confere SHA-256 e RAM e encerra o processo.
Na revisão fixada, `llama-cli` usa modo de conversa: o teste passa system/user
separadamente e usa `--single-turn`. O template embutido do GGUF é aplicado pelo
runtime; não passar um prompt já formatado como conteúdo de outra mensagem.
Salva texto nativo, tempo total de carga+geração, memória amostrada e timings nativos
em stderr. `verify_real` exige esse teste bem-sucedido antes de prosseguir.
O verificador do serviço também correlaciona SHA-256 dos textos recebidos pelo
adaptador com retornos diretos do runtime real, sem mock e sem aceitar fallback.
O sucesso desses verificadores comprova execução/origem, **não fidelidade semântica**.

Testes unitários/HTTP usam respostas **simuladas**. `verify_local` inicia um processo
real do wrapper sem modelo, testa saúde/prontidão, fallback e encerramento e mede
memória pontual. `verify_real` tenta carregar pesos reais, consulta simples, três
casos sintéticos (incluindo dados ausentes e texto malicioso) e repetição; salva
bloqueio ou respostas reais. Não substitui revisão humana de português/fidelidade.
O smoke usa diretamente o Python base dedicado para que os contadores Windows
meçam o interpretador, evitando medir apenas o launcher de uma venv.
Os cenários de timeout, concorrência, excesso e autenticação são exercitados
na suíte simulada. Artefatos em `.local-harpia/results/` não vão ao Git.

## Integração posterior

Para repetir somente os dois casos sintéticos com monitoramento e template
corrigido: `python -m genai.scripts.verify_ab` no Python dedicado da worktree.
Esse comando salva `.local-harpia/results/economic-ab.json`, incluindo entradas,
saídas, prompts, orçamentos e amostras Windows/processo. Não execute `verify_real`
completo para uma rodada limitada a duas gerações. Exit 0 comprova apenas transporte
e origem; a rodada 5 saiu 0 e **reprovou** na avaliação textual.

Fluxo pretendido: navegador → API HarpiServer → cliente HarpIA → Windows/BitNet → API
→ navegador. O navegador nunca recebe o segredo técnico nem acessa BitNet diretamente.
Exemplo preparatório de uso do cliente no futuro backend:

```python
from genai.harpia.client import Client
client = Client()  # HARPIA_URL / HARPIA_TOKEN; criar uma vez por processo
answer = client.explanation({"incident_id": incident_id, "revision": revision, "facts": safe_facts})
```

O cliente é síncrono: usar em worker/threadpool com capacidade limitada, não bloquear
um endpoint async diretamente. A API deve validar autorização do usuário e origem
das evidências, montar contexto mínimo, manter revisão imutável, persistir origem e
texto com vínculo ao incidente e então responder ao frontend. Não inserir texto em
campos numéricos de Risk nem reutilizar o contrato XAI como narrativa LLM.

Mapeamento a implementar pelo backend com validadores canônicos existentes:

| DTO auxiliar | Fonte canônica / regra |
|---|---|
| incident_id, revision, scenario_id | `incident` da revisão consultada |
| rf_attack_probability | `detection.classification.attack_probability`, somente RF |
| if_anomaly_score | `detection.anomaly.anomaly_score`, score operacional IF |
| rf_calibrated | informação do produtor RF; null se não comprovada |
| if_score_meaning | semântica do pacote IF: maior é mais anômalo, não probabilidade |
| asset_id, window_start, window_end | ativo e intervalo validados pelo backend; null quando ausentes |
| xai_summary | contribuições do `explanation` XAI vinculado à detecção |
| risk_status, risk_score, risk_level, risk_factors | snapshot `incident.risk`; preservar nulos e fatores ausentes |
| decision_id, decision_status, decision_action | `decision` já produzido por Policy |
| execution_status, verified_at | `execution` real; aceito ≠ mitigação confirmada |
| observed_at, observed_facts, evidence_summary, limitations | horários, fatos essenciais, evidências opcionais e cobertura |
| operation_mode, execution_enabled, autonomy_mode | controles independentes autenticados |

Esses resumos limitados são projeções auxiliares: não copiam schemas, não validam
relações canônicas e não comprovam autenticidade. O backend deverá verificar links,
janela/revisão, validação e confiança antes de preencher os campos.

Arquivos **reais** identificados para trabalho posterior (não alterados aqui):

- Referência P11 `backend11/bitnet.py`: substituir opt-in o transporte por `Client`,
  preservando `source` e compatibilidade do chamador.
- Referência P11 `backend11/service.py`: rota existente `GET /api/v1/p11/explain/{incident_id}`,
  armazenamento `Store`, projeções `bitnet` e `GET /api/v1/p11/bitnet/{id}/history`.
  Hoje explain retorna texto sem persistir automaticamente uma projeção bitnet;
  definir persistência/revisão e identidade do produtor antes da integração.
- Na worktree `integration-p11`: `frontend/src/api.ts` (`explanationHistory`),
  `dashboard.tsx` (`HarpiaCard`), `pages.tsx` e `main.tsx`. Já consultam projeções/
  histórico e diferenciam origens; não apontar `api.ts` ao Windows.
- Na worktree local `backend-data`: `backend/app/core/config.py`,
  `backend/app/api/v1/router.py` e `backend/app/services/` existem para a integração
  com FastAPI. A `main` desta entrega só contém a base documental e
  `backend/requirements.txt`; não trouxe módulos de outras branches.

Não há evidência local do caminho exato da instalação P08–P11 em execução na VM.
O responsável por essa entrega deve mapear a referência P11 à árvore implantada.
Não afirmamos que os endpoints da referência estejam ativos no HarpiServer.

`127.0.0.1` na VM aponta à VM. Para alcançar este serviço mantendo loopback, será
necessário planejar um túnel autenticado com encaminhamento do lado da VM até o
Windows, ou revisar arquitetura e política de acesso/TLS. O runtime 8092 deve
permanecer privado do wrapper. Não foram criados túnel, listener LAN, regra de
firewall ou credencial de VM. Integração HarpiServer/frontend/incidentes reais pendente.

## Remover apenas a instalação dedicada

Encerre o wrapper com Ctrl+C e confirme que seu `llama-server` terminou. Depois, no
diretório desta worktree, remova **somente** `.local-harpia` (inclui Python, venv,
cache, runtime, modelo, configuração e resultados). Exemplo com verificação de alvo:

```powershell
$worktree = (Resolve-Path 'D:/Projetos/tcc - harpisense/harpisense-worktrees/harpia-bitnet').Path
$target = [IO.Path]::GetFullPath((Join-Path $worktree '.local-harpia'))
if ($target -ne (Join-Path $worktree '.local-harpia')) { throw 'Alvo inesperado' }
if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Alvo é link/junction' }
Remove-Item -LiteralPath $target -Recurse -Force
```

Não remover a worktree enquanto precisar do código. Não apagar caches globais,
instalações Python existentes, Visual Studio, serviços ou VMs. Este comando de
remoção não foi executado na entrega.
