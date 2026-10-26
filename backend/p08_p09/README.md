# Entrada de lote validado P08/P09 — primeira entrega

Branch `fix/p08-p09-validated-batch`, baseada em main 9d58e69. Continuação do
registro `a7f8ad3` em `docs/continuidade-p08-p09`. Escopo: adulteração em cópias,
ligação do validador de lote ao pipeline e regressões. Não é entrega de cobertura,
contagens operacionais, compatibilidade RF/IF ou sessão completa.

## Base preservada

Fontes Python obtidos individualmente do diretório vigente da VM
`/opt/harpisense/staging/p09-deteccao-decisao/adaptador_logs_p08_p09`, após conferir
os hashes com o registro de continuidade. Não foram copiados lotes, checkpoints,
credenciais ou configurações. `tests/fixtures/previous_*.py` preserva as duas
fontes anteriores byte a byte; as demais fontes/testes são snapshots sem alteração.

Referência prioritária: `referencias/versão_v2`, P08/P09, contratos e topologia V2.
Foram conferidos guia de integração P09, catálogo oficial, contratos auxiliares,
`harpisense_data/windows.py`, envelopes RF/IF e roteiro de topologia. Os tipos
telemetry_validation_failure/telemetry_duplicate constam do catálogo. A evidência
auxiliar deste adaptador não equivale por si só ao contrato normalized_evidence
completo. Os componentes v1 preservados no P08 V2 e os pacotes de
`referencias/Versões corretas` continuam válidos para itens ainda não atualizados;
nenhum componente foi considerado ausente só por não ter atualização na V2.

Dois arquivos de runtime têm alteração:

| Arquivo | SHA256 anterior | SHA256 candidato testado |
|---|---|---|
| auxiliary_audit_adapter.py | a6e2747e9cf857216297db1a9557fa12925e4e1c088b27152a0fcfbea8c827ff | 04b58d66d5d6d9cd513bff4b559c187bca4a2d13ea370e80fcbfc97bb9eb5416 |
| p08_p09_pipeline.py | a43d0db34a5c6bca409248d8b464bdacafa3ed93e7eddd34da0fa2de1f4b85cf | 4ec9ed8c2fb5b068ebdae4b6cd7643d1aca5a5c0fcc5d9c354e28f5f7f12d8dc |

O adapter apenas expõe `previous_cursor`, `next_cursor` e `continuity_verified=False`
do manifesto já validado, inclusive para lote vazio. Não muda sua verificação ou
normalização. O pipeline seleciona uma entrada e retém o retorno inteiro do
adapter, sem reler JSON/manifesto e sem normalizar duas vezes. Os gates de
artefatos e cobertura e o normalizador de eventos avulsos não foram alterados.

## Como selecionar a entrada

Com o diretório dos adaptadores no sys.path, mantém-se a assinatura posicional
anterior, acrescida somente da opção keyword-only `batch_path`:

```python
from p08_p09_pipeline import run_pipeline

# Caminho anterior: lista de eventos, sem garantia de integridade de lote.
result = run_pipeline(base_dir, session_name, events, windows,
                      coverage_records, required_sources)

# Entrada de lote: não carregar os eventos por fora nem fornecê-los novamente.
result = run_pipeline(base_dir, session_name, None, windows,
                      coverage_records, required_sources, batch_path=batch_path)
```

Fornecer batch_path e events diferente de None, **inclusive events=[]**, retorna
input_mode=conflict antes de I/O ou gates, auxiliary_audit=None, integridade False
e autorizações False. Não há merge, soma ou preferência silenciosa entre entradas.
Nenhuma entrada válida (events=None sem batch_path) conserva a rejeição anterior.

Resultados anteriores mantêm os mesmos valores, inclusive mensagens de erro no
caminho antigo. Os novos campos de topo são aditivos: `input_mode`,
`batch_reference`, `batch_integrity_verified` e `limitations`. Eventos avulsos
sempre têm integridade de lote False no topo e nunca recebem a marca de lote
verificado no retorno auxiliar, mesmo se uma entrada tentar fornecê-la.

No lote válido, auxiliary_audit conserva nome e hashes do lote/manifesto,
journal_records_read, cursores do manifesto, rastreabilidade por evento,
rejected_records, auxiliary_event_count e auxiliary_evidence. Em lote inválido,
não se publica evidência parcial: auxiliary_audit=None, integridade False e erro
de preparação em reasons. Evento desconhecido é rejeitado no lote; nos eventos
avulsos continua ignorado conforme comportamento anterior.

Integridade de lote é independente de aprovação do gate de artefatos. Se o lote
é válido e a sessão não está disponível, sua proveniência permanece no resultado,
mas artifact_consistent=False e coverage_diagnostic=None. O campo session é o
contexto **solicitado pelo chamador**, não um vínculo autenticado com o lote.

Esses eventos auxiliares continuam com cobertura UNKNOWN e não seguem para a
entrada de features: no modo lote o gate de cobertura recebe events=[], mantendo
windows, coverage_records e required_sources originais. O gate continua sendo
executado somente após artefatos consistentes. Não há promoção de confiança,
autorização para RF/IF/IPS nem contagens: log_counts={} em todos os caminhos.

A prevenção de duplicidade desta mudança é por chamada (entradas mutuamente
exclusivas, uma normalização). Não cria ledger de lotes, deduplicação global,
checkpoint ou persistência; repetir uma chamada retorna novamente a evidência,
sem gravar ou somar contagens. Os cursores não certificam continuidade/autenticidade.

## Testes e alcance

- `LOCAL_TEST_RESULTS.json`: **58 testes aprovados**, Python 3.12.15 em contêiner
  local sem rede, sem banco e sem lotes reais.
- `VM_TEST_RESULTS.json`: os mesmos **58 testes aprovados**, Python 3.14.4 da VM,
  executados no diretório temporário do pacote, sem alterar staging.
- São 44 regressões existentes, 11 testes de lote/pipeline e 3 de aplicação segura.
  Subcasos incluem 12 alterações de manifesto, mudanças de bytes, JSON/envelope
  inválidos, rastreabilidade ausente, tipo desconhecido, lote vazio, exclusão de
  entradas, normalização única, resultados legados e gates reais com fixtures
  sintéticas. Fixtures de pcap são apenas bytes sintéticos para consistência,
  nunca comprovação de captura/cobertura real.
- Aplicador testado em cópias sintéticas: dry-run sem backup/escrita, recusa de
  hash inesperado, backup exato e recuperação dos dois arquivos após falha na
  segunda substituição.

`REAL_BATCH_CANDIDATE_RESULTS.json`: candidata executada em
`/tmp/harpisense-p08p09-validated-batch.grdSWc/p08_p09` com os dois lotes originais
em modo leitura. O lote acabf4… produziu 1 telemetry_validation_failure; d94cc2…
produziu 0. Ambos tiveram integridade verificada, cursores presentes, zero
rejeitados, UNKNOWN, inferência/IPS False e log_counts={}. A saída sanitizada
registra presença de rastreabilidade, não valores de cursores/boot IDs.

Também foram feitas **seis adulterações em cópias reais isoladas**: por lote,
bytes alterados, digest divergente no manifesto e manifesto removido. Todas
rejeitadas; hashes e mtimes dos cinco arquivos originais (2 lotes, 2 manifestos,
checkpoint) são idênticos antes/depois. Os temporários dessas cópias foram removidos.

**Validação parcial, explicitamente:** não há vínculo verificado com uma sessão
P08. O script usa UNBOUND-AUXILIARY-AUDIT como rótulo diagnóstico, windows=[],
coverage_records=[] e required_sources=[], sem inventar uma sessão ou simular
aprovação. O gate de artefatos real retorna FileNotFoundError e interrompe antes
da cobertura. Esse resultado confirma integração/proveniência e bloqueio; não
confirma fluxo completo. Nenhum manifesto .session.json/.coverage.json foi
encontrado nos diretórios legíveis de /opt/harpisense. A busca teve Permission
denied em /opt/harpisense/capturas: não se declara inexistência desses artefatos
nem indisponibilidade física das máquinas com base nessa limitação de acesso.

Reprodução local, a partir desta pasta, com a imagem Python já disponível:

```powershell
$testSource = (Get-Location).Path
docker run --rm --network none --mount "type=bind,source=$testSource,target=/work" --workdir /work --entrypoint python harpisense-backend:integration -B tests/run_local.py
```

As rotinas usam biblioteca padrão Python. A imagem não conecta ao backend/banco.
Não executar o script de lotes reais contra arquivos desconhecidos: ele confere
os cinco hashes confirmados antes de testar e termina se divergirem.

## Aplicação em staging e recuperação

**Situação atual: aplicação executada pelo usuário e hashes instalados
confirmados por SSH.** Os dois arquivos correspondem exatamente à candidata
testada do commit 2de050e (tabela acima); root:root 0644, diretório 0755.
`INSTALLED_READONLY_RESULTS.json` registra a verificação e o estado dos originais.
O backup `.validated-batch-backup-5jgd2gmh` foi criado, root:root 0700. O acesso
SSH não consegue ler seu conteúdo/receipt.json: sua existência está confirmada,
mas hashes internos e recibo ainda dependem da inspeção privilegiada solicitada.
Não interpretar a restrição de acesso como divergência do backup.

O comando abaixo foi executado pelo usuário. Não deve ser repetido: os hashes
antigos já foram substituídos e o aplicador recusará a nova base.

```sh
sudo /usr/bin/python3 -B /tmp/harpisense-p08p09-validated-batch.grdSWc/p08_p09/apply_staging.py --apply
```

`apply_staging.py` recusa divergência de hash nos dois arquivos e nos três gates
dependentes, valida sintaxe, faz backup em `.validated-batch-backup-*` no próprio
diretório e substitui somente os dois arquivos por renomeação individual,
preservando proprietário/permissões. Confere hashes ao final e grava receipt.json
no backup. Se uma substituição falhar, tenta restaurar ambos e propaga o erro.
Uma interrupção irrecuperável do processo/host entre os dois renames pode exigir
recuperação manual; o backup deve ser preservado. Não substitui os demais snapshots
do pacote, não reinicia serviço e não modifica P11/PostgresStore.

A rodada posterior à aplicação limitou-se à identificação e à conferência de
arquivos. Os hashes/mtimes dos originais/checkpoint permanecem iguais. Não se
reexecutou pipeline, coletores ou SQL. A igualdade de hashes identifica o código
instalado como o testado; a validação anterior com lotes reais continua sendo
da candidata temporária, sem sessão P08 vinculada, não um fluxo completo validado.

Para concluir a leitura do backup e identificar as sessões existentes, o usuário
recebeu um script somente leitura, preservado na branch de continuidade:

```sh
sudo /usr/bin/python3 -B /tmp/harpisense-p08p09-validated-batch.grdSWc/p08_p09/inspect_p08_applied_readonly.py
```

Não é preciso alterar permissões ou fornecer senha no chat. /opt/harpisense/capturas
continua protegido; sem essa leitura não se afirma qual sessão existe nem que
seus arquivos estejam ausentes. Os lotes antigos continuam sem vínculo comprovado.

Recuperação, se necessária: com privilégio autorizado, verificar que os arquivos
instalados ainda têm os hashes candidatos acima, conferir os hashes originais no
backup registrado no recibo e restaurar somente os dois arquivos desse backup,
preservando metadados e usando temporários no mesmo filesystem com rename. Se
qualquer hash divergir, interromper e reconciliar antes de restaurar. Nenhum
rollback de banco ou restart é necessário para esses módulos de staging.

## Dependências das próximas entregas (não executadas)

| Entrega futura | Evidência e dependência concreta |
|---|---|
| Vincular evidências a sessões/janelas | Acesso autorizado aos artefatos P08 reais (session/coverage/pcap e janelas), IDs estáveis de evidência, collection_session_id, sensor_id, target_ref, origem confiável dos vínculos e regras temporais. Hoje os eventos auxiliares não têm evidence_id canônico ou vínculo atestado; não derivar contexto do nome do arquivo. |
| Comprovar continuidade/cobertura | Definir fontes obrigatórias; intervalos início/fim por fonte; jornal/cursor/boot, retenção/rotação, reinícios, lacunas e sincronização de relógios. Manifesto local consistente e lote vazio não comprovam ausência de eventos. A marca verified exige verificação independente, não um booleano autodeclarado. |
| Produzir contagens oficiais | Aplicar tipos/campos e limites do catálogo/contratos oficiais. OPTIONAL_FEATURES inclui auth_failures, auth_successes, mqtt_publish_count, mqtt_acl_denials, api_auth_failures, admin_auth_failures, telemetry_identifier_conflicts e telemetry_stale_count. telemetry_validation_failure e telemetry_duplicate não são novas features previstas: não inventar colunas nem transformá-las em contagem de integridade. Sem cobertura suficiente, desconhecido não vira zero. |
| Validar compatibilidade RF/IF | Metadados confiáveis dos bundles, hashes, versões de dependências, lista/ordem das features, feature_schema_version, traffic_profile, window_seconds e invariantes numéricas. Conferir antes de carregar artefatos ou executar modelos. A ausência local de bundle não significa ausência no projeto. |
| Executar uma sessão completa | Arquivos/referências e permissões corretos, entrada/chamador definido, PCAP consistente, fontes e vínculos verificáveis, gates aprovados com evidência real e escopo autorizado próprio. Esta rodada não autoriza nova coleta, inferência ou defesa. |

Máquinas/fontes necessárias, por papel da topologia V2 (confirmar localização
efetiva; não presumir que cada papel exige uma VM separada):

- **HarpiServer:** staging P08/P09, armazenamento das capturas, acesso de leitura
  autorizado à sessão/janelas e jornal do consumidor MQTT/telemetria. Para a
  próxima tarefa mínima de vínculo offline, estes arquivos e o inventário de
  vínculos podem bastar, sem nova coleta nem produtores ligados.
- **Host gateway/captura P08:** PCAP e metadados das interfaces realmente usadas,
  sensor_id e intervalo/relógio da sessão. Confirmar se esse papel é o próprio
  HarpiServer; não assumir caminho de tráfego pela documentação candidata.
- **Host do broker Mosquitto:** logs de autenticação/ACL/publicação, intervalos,
  retenção e identidade da fonte, caso integrem required_sources. Confirmar host
  real (gateway/central/outro), sem transportar credenciais.
- **Host da API FastAPI e consumidor de telemetria:** logs das fontes escolhidas,
  rastreabilidade e limites de cobertura; disponibilidade dos processos atuais
  não substitui histórico íntegro do intervalo da sessão.
- Para uma **nova sessão completa futura**, ESP32 e Ubuntu Poste 02 ou os
  produtores legítimos aprovados, gateway e broker devem estar disponíveis no
  percurso verificado. Windows/VMware e intermediário Tailscale são dependências
  somente se hospedarem ou transportarem esses papéis. Kali/ataques não são
  necessários para o próximo vínculo offline nem estão autorizados aqui.

Próximo passo imediato: concluir a inspeção somente leitura do backup e de uma
sessão P08 real com o acesso adequado. Depois, tratar **uma tarefa por vez**:
demonstrar seus vínculos às janelas/evidências, mantendo UNKNOWN e ambas as
autorizações False enquanto faltarem comprovações. Uma nova coleta é apenas
uma alternativa condicional, cujo procedimento está na nota de continuidade;
não foi iniciada nem se tornou necessária só pela falta de permissão SSH.

Nenhum coletor, checkpoint, lote/manifesto original, PostgreSQL, serviço, modelo,
ataque ou ação de defesa foi executado/modificado por esta implementação.
Paginação P11 permanece fora do escopo e não foi implantada.
