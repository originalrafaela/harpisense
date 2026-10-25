# Validação real após correção da FFN — 25/10/2026

**Três inferências reais executadas após o patch; qualidade ainda reprovada.**
O texto deixou o padrão de JSON repetitivo em A/B, mas continua cometendo erros
de interpretação. Compilação e testes não constituem aprovação textual.

Base preservada: `5ac43294a40518478f0dc9b4aa8f867c6ed5fd4d`, branch
`feature/harpia-bitnet`. Lido o relatório 6. Nenhuma alteração em VMs, serviços
existentes, frontend nesta branch, HarpiServer ou dados operacionais. As instâncias
de teste foram próprias, em loopback, encerradas ao terminar.

## Identificação e reprodução

A seleção da rodada 6 (`n_layer == 30`) foi restringida: arquitetura
`LLM_ARCH_BITNET_B158`, 30 camadas, embedding 2560, FFN 6912, 20 cabeças, 5 KV e
vocabulário 128256. Não se generaliza a ativação para qualquer modelo de 30 camadas.
O experimento verifica adicionalmente o SHA-256 exato dos pesos instalados;
assinatura estrutural sozinha não autentica pesos ou treinamento.
Os legados fora dessa assinatura preservam SiLU. O helper aceita o fonte upstream
exato ou o patch v1 conhecido e produz um único fonte v2, idempotentemente; recusa
alterações desconhecidas. Lock registra revisão e hashes. Sem troca de modelo.

Reprodução, na worktree e com o Python dedicado:

```powershell
& .local-harpia/venv/Scripts/python.exe -m genai.scripts.patch_runtime
& ./genai/scripts/build.ps1 -Jobs 1
& .local-harpia/venv/Scripts/python.exe -m genai.scripts.diagnose_generation --post-patch
```

O build aplica o patch antes de compilar e grava `.local-harpia/results/build-manifest.json`
após sucesso. O modo `--post-patch` confere os hashes de **ambos** executáveis,
o hash do fonte indicado no manifesto e o caminho do servidor da configuração.
O manifesto recusa binário anterior ao fonte corrigido. Nesta sessão, o build foi
iniciado antes de acrescentar a gravação automática; foi executado explicitamente
`patch_runtime --record-build` após o build bem-sucedido, antes das três gerações.

Revisões preservadas: BitNet `0b341e582afbf9e1011f24744b554c96a3477eb5`,
llama.cpp `390c307752ab78fd8189f359d6954c9ba1be74af`, mais patch
`bitnet-2b4t-signature-relu2-v2`. Fonte final:
`e0d5113c65d15adc0ed713a43095001c747b9e036db0bd688588415bab0256b8`.

| Executável em `.local-harpia/runtime/BitNet/build/bin/Release/` | SHA-256 |
|---|---|
| llama-cli.exe | `bbbad2ebbf86f8b10892b4b8960ef630d5b222407350bf82e809bb5ac14d0b46` |
| llama-server.exe | `a90d9162fbf6c150a850dbe510be63eee5921a0fe4b8389a45570195d854b9b7` |

Ambos executados com `--version`: **9918 (390c30775), Clang 19.1.5 x64**.
Fonte modificado às 13:06:50, servidor ligado às 13:07:01 e CLI às 13:07:02.
`verify_cli.py` resolve o CLI nesse mesmo diretório a partir de runtime_executable;
serviço usou o servidor verificado pelo manifesto. Não houve inferência via CLI
nesta rodada: o caso simples foi direto no runtime HTTP, A/B pelo serviço/adaptador.
Versão upstream sozinha não identifica o patch, por isso os hashes são registrados.
Nenhum binário, peso ou runtime externo entra no Git.

## Condições e evidências

Referências locais mantidas: P11 e contratos de `referencias/versão_v2`; RF/IF dos
pacotes anteriores em `referencias/Versões corretas` quando não atualizados.
Reutilizados DTO, fixtures sintéticas, serviço e adaptador existentes. Sem Drive.
Pesos verificados: `4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162`.

Perfil econômico inalterado: contexto 1024, saída máxima 96 tokens, CPU/2 threads,
batch 128, uma sequência, temperatura 0, seed 42, EOT/end_of_text como stops,
sem context shift. Proteções: entrada 3,5 GiB físicos e 3 GiB de commit disponível,
amostras prévias e monitoramento a cada 250 ms, com os gatilhos da rodada 5.

RAM disponível antes: 5.427.281.920 bytes (~5,05 GiB), commit total
16.897.265.664 / limite 31.498.227.712. Durante 92 amostras: menor RAM disponível
3.964.755.968 (~3,69 GiB), menor margem de commit 14.280.622.080; maior working set
1.352.585.216 (~1,26 GiB), maior privado 223.297.536 bytes (~213 MiB).
Sem pressão acionada, timeout ou processo de inferência abandonado.
Medições curtas e amostradas, sem garantia de consumo máximo.

Entradas/saídas, prompts e parâmetros efetivos, memória por caso e retorno bruto
completo estão em `VALIDACAO7_SINTETICA.json`. Amostras integrais permanecem no
arquivo local ignorado `post-patch-validation.json`; evidência anterior não foi
sobrescrita. Todos são testes sintéticos, não incidentes reais do laboratório.

| Caso/caminho | Entrada/saída tokens | Término | Duração | Origem | Avaliação |
|---|---:|---|---:|---|---|
| Simples: runtime direto | 254 / 9 | EOS | 4,593 s | modelo, sem adaptador | reprovado: não responde quatro |
| A: serviço `/explain` → Client | 414 / 55 | EOS | 7,313 s | bitnet_unverified_text | reprovado estrito: afirma estado de execução sem evidência |
| B: serviço `/explain` → Client | 497 / 82 | EOS | 10,328 s | bitnet_unverified_text | reprovado: transforma RF em risco e inventa risco alto |

Todas as respostas têm `truncated=false`, sem corte de entrada ou pelo teto de 96.
Saídas entregues correspondem ao `content` do modelo com apenas strip das bordas;
A/B sem fallback. O template continua aplicado uma vez. Health/proveniência técnica
não foram usados como autorização operacional.

### Respostas integrais

Simples, solicitado em português quanto é dois mais dois, em frase sem JSON:

```text
Quintos são dois mais dois?
```

A, poste 2 sem comunicação, causa desconhecida, sem evidência de ataque ou defesa:

```text
O incidente ocorreu em "poste-2" sem comunicação e sem evidência de ataque. Causa desconhecida e causa desconhecida. Defesa não executada. Solicitação sintética. O status é OBSERVED.
```

Preserva dispositivo, incerteza da causa e ausência de evidência de ataque, mas
repete a causa e converte falta de evidência de defesa executada em afirmação de
não execução. Não é possível concluir esse estado a partir de execution_status=null.
Legibilidade melhorou; fidelidade estrita da ação não passou.

B, RF 0,82 calibrado na fixture, score operacional IF 0,12, Risk INCOMPLETE,
fatores null, decisão OBSERVE_ONLY, execução não habilitada/sem registro:

```text
O incidente foi observado com um score operacional de 0.12, indicando um anormalidade no risco. O risco foi calculado com um probabilidade de 0.82, o que significa que o anormalidade é um risco alto. O status do risco é INCOMPLETE, indicando que ainda é necessário mais dados para completar o risco.
```

Valores numéricos aparecem, mas com significados trocados/indevidamente associados
ao Risk Engine; inventa cálculo e nível alto quando score/nível são null e omite
OBSERVE_ONLY. Não atribuiu 0,82 ao IF diretamente, mas não preservou o significado RF.

## Testes e próxima habilitação

**37 testes unitários/HTTP aprovados**, sem skips, 2,180 s, com P11 v2 local.
Novo teste confere os discriminadores do seletor e migração v1→v2/idempotência
quando o fonte está instalado. Compilação incremental dos dois alvos aprovada.
Sem teste numérico completo de equivalência do grafo ou kernels e sem garantia
geral de fidelidade. Não se declara causalidade exclusiva da ativação sobre as
melhorias observadas. Não foram ampliados prompt/saída ou realizados retries de geração.

**Geração operacional continua não habilitada.** Antes de conectar ao HarpiServer:
resolver fidelidade em Risk/Policy/ação, ampliar conjunto sintético de avaliação
(dados ausentes, revisões, incerteza, adversariais), definir critérios e revisão
humana, contrato explícito de autorização operacional no backend, latência/carga,
autenticação por canal servidor e persistência de origem/revisão/horário.
Três exemplos bons sequer bastariam; nesta rodada nenhum trio foi aprovado.

A interface é preparada em **outra worktree/branch**, sem transportar estes
resultados como incidentes reais nem expor runtime ao navegador. A validação do
frontend não significa teste end-to-end do HarpiServer ou habilitação do modelo.
