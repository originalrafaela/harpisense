# Continuidade P08/P09/P11 — 26/10/2026

**Investigação histórica posterior:** journal do boot de 23/10 recuperado;
rastros sudo/orquestrador e ens37 em modo promíscuo corroboram a sessão auto02.
As units MQTT/P11 não retornam eventos no intervalo, sem que isso comprove zero
eventos ou logs completos. A triagem dos demais 19 relatórios e o detalhamento
do heartbeat/PCAP dependem da saída root de triage_p08_history_readonly.py.
Decisão provisória: pendência histórica específica recuperável, sem motivo
demonstrado para exigir nova coleta. Ver P08_TRIAGEM_HISTORICA_2026-10-26.md;
não apresentar a triagem ainda bloqueada como concluída. Instalação e backup
não foram novamente verificados nesta investigação.

**Estado mais recente, após inspeção privilegiada fornecida pelo usuário às
18:01:44 UTC:** candidata 2de050e instalada; hashes dos backups originais e recibo
confirmados. Sessão existente p08-v4-persistencia-auto02 identificada: PCAP íntegro,
integração correspondente e quatro janelas vinculadas por session/sensor/interface.
Ela é aproveitável offline, mas permanece INCOMPLETE, sem comprovação de cobertura
ou vínculo com os lotes de 25/10 (sessão de 23/10). Foram listadas 20 sessões;
as demais não foram avaliadas em detalhe. Não se demonstrou necessidade de nova
coleta. Ver `IDENTIFICACAO_SESSAO_P08_APOS_APLICACAO.md` para os artefatos presentes
e a próxima pendência: logs históricos e contexto confiável do intervalo de 23/10.
Os registros abaixo documentam etapas anteriores e não substituem esse estado.

**Atualização posterior ao a7f8ad3:** a seção final deste documento registra a
primeira entrega de integração, implementada e testada na branch
`fix/p08-p09-validated-batch`, commit 2de050e. A aplicação em staging continua
pendente de privilégio root. As seções iniciais abaixo são o registro histórico
da conferência anterior; não interpretá-las como estado atualizado da candidata.

Conferência somente leitura da VM, concluída às 17:02 UTC (14:02 de São Paulo).
Nenhuma implementação, implantação, reinício, execução de coletor/adaptador,
consulta ao banco operacional ou avanço de checkpoint foi realizado nesta rodada.
Registro separado na branch local `docs/continuidade-p08-p09`, baseada em main
9d58e69. O trabalho de paginação permanece em sua própria branch.

## Referências e evidência

Referência prioritária: `referencias/versão_v2`, P08, P09 e P11/P13. Foram lidos
README do P08 V2, GUIA_INTEGRACAO, PENDENCIAS_PARA_EXECUCAO_E_INTEGRACAO e
`harpisense_contracts/auxiliary.py` do P09 V2. A fixture de API usada na validação
P11 corresponde ao componente P11 do P13 V2 (SHA256
`8cb67932cc2f7ef22ed357b0c94f7a8cb416cde164db60866dd6df5cf7fb8698`).

O P08 V2 preserva componentes v1 em `componentes/`: não interpretar a ausência de
uma atualização individual como componente ausente. `referencias/Versões corretas`
continua sendo a referência complementar dos componentes ainda não atualizados;
nenhum pacote anterior ou arquivo local foi usado para substituir código na VM.

A evidência do teste dos dois lotes foi fornecida pelo usuário. Nesta rodada,
confirmaram-se o código atual, seu hash e a ligação estática entre os componentes;
o teste não foi reexecutado. A saída colada repete o mesmo resultado três vezes:
isso não representa seis lotes distintos nem três eventos auxiliares.

O JSON ao lado registra 25 arquivos, hashes, tamanhos e mtimes, sem conteúdo de
lotes, cursores, configurações ou credenciais. Inclui os adaptadores P08/P09,
os dois lotes e manifestos, o checkpoint e Store/app P11. Dez hashes capturados
no início foram novamente conferidos ao final e permaneceram iguais. Os mtimes
dos lotes/manifestos/checkpoint também coincidem com a leitura inicial.
O inventário é uma fotografia do estado encontrado; não é um backup dos fontes.

## Diagnóstico atualizado: normalização demonstrada, integração pendente

Base remota: `/opt/harpisense/staging/p09-deteccao-decisao`.

O arquivo `adaptador_logs_p08_p09/auxiliary_audit_adapter.py` mantém o hash testado:
`a6e2747e9cf857216297db1a9557fa12925e4e1c088b27152a0fcfbea8c827ff`.
Sua alteração mais recente observada foi em 26/10 às 16:51:59 UTC (13:51:59 -03).
Não foi sobrescrito nem substituído por uma cópia local.

O teste informado demonstra, para os dois lotes existentes:

| Lote, prefixo do identificador | Integridade | Eventos auxiliares | Rejeitados |
|---|---|---:|---:|
| mqtt_v4_acabf4a909f0… | verificada | 1 | 0 |
| mqtt_v4_d94cc2181f59… | verificada | 0 | 0 |

O evento resultante é `telemetry_validation_failure`, com `journal_cursor` e
`journal_boot_id`. Ambos os resultados mantêm `coverage=UNKNOWN`,
`authorized_for_inference=False`, `authorized_for_ips=False` e `log_counts={}`.
Assim, a hipótese de que a normalização desses lotes ainda não foi demonstrada
está superada pelo teste do usuário. Não estender essa conclusão a outros lotes,
ao caminho completo de execução ou à validação do contrato canônico inteiro.

O código lido confirma:

- Linhas 8–11: mapeamento `validation_failure` para
  `telemetry_validation_failure` e `duplicate_message` para `telemetry_duplicate`.
- Linhas 26–33 e 55–57: tratamento do envelope e preservação da rastreabilidade.
- Linhas 72–167: `prepare_auxiliary_audit_batch(batch_path)` valida nome, JSON,
  SHA256, manifesto 4.0, contagens, cursores, identificador, modo conservador e
  envelopes; somente depois chama `prepare_auxiliary_audit(events)`.
- A verificação de integridade local não comprova autenticidade, continuidade,
  cobertura completa, vínculo com janela ou autorização para inferência/IPS.

## Caminho atualmente ligado ao pipeline

`adaptador_logs_p08_p09/p08_p09_pipeline.py`, hash
`a43d0db34a5c6bca409248d8b464bdacafa3ed93e7eddd34da0fa2de1f4b85cf`:

1. Linha 9 importa **prepare_auxiliary_audit**, não a função de lote.
2. `run_pipeline(base_dir, session_name, events, windows, coverage_records,
   required_sources)`, linhas 12–19, recebe eventos já carregados, não batch_path.
3. Linha 32 chama **prepare_auxiliary_audit(events)**. Essa chamada usa o
   normalizador atualizado, mas não verifica a integridade do lote/manifesto
   pela função `prepare_auxiliary_audit_batch`.
4. Linhas 39–64 validam os artefatos P08 e chamam
   `prepare_verified_log_counts`. Essa validação de artefatos é outra etapa;
   não substituir nem presumir que equivale à validação de lote MQTT.
5. O resultado mantém `authorized_for_inference=False`,
   `authorized_for_ips=False` e `log_counts={}`. A integração de cobertura lida
   também não libera contagens por falta de procedência independente.

**Conclusão:** o pipeline ainda usa a entrada antiga de lista. O normalizador
atualizado está acessível por ela; a validação nova de lote não está ligada ao
pipeline. Não confundir essa lacuna com ausência da normalização em si.

A busca estática em fontes `.py`/`.sh`, units/timers sob staging e
`/etc/systemd/system`, e arquivos legíveis de `/etc/cron.d` não encontrou chamada
externa a `run_pipeline` nem a `prepare_auxiliary_audit_batch`. A função de lote
foi encontrada na própria definição; o teste manual fornecido não é um chamador
persistido nesses locais. Isso não prova ausência de chamadas dinâmicas,
comandos manuais, crontabs de usuário ou caminhos fora do escopo pesquisado.
O fluxo contínuo completo não foi demonstrado e não foi executado nesta rodada.

Separadamente, `adaptador_p08_p09/ler_janelas.py`, hash
`d1b8c80d0252837093247b1fa6e296b6f9b016bf51ce2762c4a64c30386eea8d`,
está preservado com a alteração de 26/10 às 16:27:23 UTC (13:27:23 -03). É um leitor/validador
separado: não chama o pipeline de logs nem a entrada de lote. Linhas 53–66 fazem
SQL próprio parametrizado por sessão, não `Store.list()`; o filtro de sessão
ocorre antes de DISTINCT ON. A eventual diferença entre última revisão da
entidade e última revisão dentro da sessão precisa de análise própria, sem
alterar esse leitor nesta rodada ou incluí-lo na próxima tarefa mínima.

## Paginação PostgreSQL: não implantada

O serviço `harpisense-p11` foi encontrado ativo, PID 1787, com WorkingDirectory
`/opt/harpisense/staging/p11-postgresql`; início informado pelo systemd:
26/10/2026 12:53:53 -03. Não houve reinício nesta conferência.

`app.py` desse diretório importa `PostgresStore` local e o injeta na API aprovada
do P13 e na HarpIA determinística. Hash do app:
`52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2`.

| Arquivo/entrega | SHA256 / commit | Situação |
|---|---|---|
| Store no diretório usado pelo serviço | cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c | implementação anterior |
| Store candidato na branch | 92b30e1d5cbdbfe10a6b186bbefca46f52096054da37d8de627360134fe28ffc | paginação SQL |
| Implementação | 45603a9, fix/p11-postgres-pagination | commit/push concluídos |
| Evidências PostgreSQL 18.6 | 70ab079, mesma branch | commit/push concluídos |

O hash remoto é exatamente o da fixture anterior e difere do candidato. Portanto,
a correção **permanece na branch e não está instalada no caminho do serviço**.
Esta conclusão usa metadados do serviço e arquivos em disco, sem introspecção do
bytecode em memória, sem requisições ao banco e sem reiniciar o processo.

Qualificação já concluída em PostgreSQL 18.6 isolado: seis testes aprovados;
60 mil revisões/20 mil IDs; resultados equivalentes; linhas recebidas no Python
20.000 → 50. As duas consultas continuam percorrendo 60 mil revisões no servidor.
Memória, tempos e planos estão registrados na entrega 70ab079. Nenhuma migração
ou índice novo foi incluído. A validação não autoriza implantação automática.

## Ponto de continuidade

Concluído:

- Teste manual dos dois lotes pelo adaptador, informado pelo usuário, com um
  evento normalizado e restrições conservadoras preservadas.
- Hash desse adaptador confirmado na VM, alterações do outro chat preservadas.
- Ligação estática do pipeline identificada: lista de eventos, sem validação do
  lote pela nova função.
- Situação da paginação separada e confirmada: implementada/testada na branch,
  ausente do arquivo de Store usado pelo serviço.
- Inventário local de continuidade; hashes de lote/manifesto/checkpoint
  inalterados entre as leituras desta rodada.

Pendente:

- Ligar explicitamente a entrada de lote validado ao pipeline e testar esse
  caminho, sem depender de carregamento prévio de eventos não verificados.
- Identificar/definir o chamador real antes de declarar integração completa;
  evidência atual é estática e o teste do usuário chamou o adaptador diretamente.
- Cobertura, continuidade/autenticidade e vínculos com sessão/janela continuam
  não demonstrados para autorizar contagens/inferência/IPS.
- Implantação da paginação permanece uma tarefa separada, ainda não executada.

**Próxima alteração mínima proposta, não implementada:** conectar uma entrada
explícita de lote MQTT ao pipeline usando `prepare_auxiliary_audit_batch`,
preservando o caminho de eventos existente para seus consumidores e deixando
explícita a distinção entre lista e lote verificado. Não basta trocar o nome da
função: a assinatura atual recebe lista, a nova recebe caminho, e seu resultado
inclui metadados de integridade que não devem ser descartados nem substituídos
por uma segunda normalização. Usar o código atual da VM como base, comparar
novamente os hashes antes de editar e limitar a mudança à ligação necessária.

Na próxima tarefa, validar essa ligação com fixtures sintéticas fora da operação:
um lote com evento, lote vazio e rejeição de manifesto/lote/rastreabilidade
inválidos, mantendo `UNKNOWN`, ambas as autorizações False e `log_counts={}`.
Não implementar coletor, não avançar checkpoint, não inserir essa evidência em
features e não habilitar inferência/IPS. Preservar os gates de artefatos/cobertura.

Esta rodada termina no registro. Não foram alterados arquivos da VM, MQTT,
serviços, banco operacional, Risk/Policy/executor, frontend ou geração BitNet.

## Primeira entrega: lote validado ligado ao pipeline (atualização)

Implementação e evidências: branch `fix/p08-p09-validated-batch`, commit
`2de050e`, enviado ao origin sem force ou merge. Fontes atuais da VM foram
conferidos contra a7f8ad3 antes da cópia. Apenas dois arquivos de runtime mudam:

| Arquivo | Hash candidato |
|---|---|
| auxiliary_audit_adapter.py | 04b58d66d5d6d9cd513bff4b559c187bca4a2d13ea370e80fcbfc97bb9eb5416 |
| p08_p09_pipeline.py | 4ec9ed8c2fb5b068ebdae4b6cd7643d1aca5a5c0fcc5d9c354e28f5f7f12d8dc |

Selecionar lote com `run_pipeline(base_dir, session_name, None, windows,
coverage_records, required_sources, batch_path=batch_path)`. A assinatura antiga
de eventos permanece. Ambos fornecidos (mesmo events=[]) são rejeitados antes de
I/O, sem combinação nem duplicação. O pipeline chama o validador existente uma
vez e conserva o retorno auxiliar inteiro. O adapter só acrescenta ao resultado
os cursores do manifesto já validado e continuity_verified=False.

Novos campos de topo indicam modo de entrada, referência de lote, integridade e
limitações. Eventos avulsos nunca recebem integridade de lote verificada. Lote
inválido falha sem publicar evidência parcial. Lote válido não dispensa artefatos,
vínculo ou cobertura. As evidências auxiliares continuam fora das features,
UNKNOWN, autorizações False e log_counts={}; os gates existentes são preservados.

Resultados concluídos:

- 58/58 testes locais, Python 3.12.15, contêiner sem rede/banco.
- 58/58 testes no Python 3.14.4 da VM, em pacote temporário: regressões antigas,
  adulteração em cópias, erro de manifesto, lote vazio, evento desconhecido,
  entradas exclusivas, normalização única e gates. Três testes exercitam backup,
  recusa de alteração inesperada e recuperação em cópias sintéticas.
- Candidata em `/tmp/harpisense-p08p09-validated-batch.grdSWc/p08_p09` validada
  contra os dois lotes originais por leitura: 1 e 0 eventos, zero rejeitados,
  integridade e rastreabilidade preservadas. Seis adulterações de cópias reais
  temporárias foram rejeitadas. Os originais, manifestos e checkpoint mantiveram
  hashes e mtimes; as cópias de teste foram removidas.
- Aplicador em dry-run conferiu hashes esperados dos dois arquivos e dos três
  gates dependentes, sem aplicar ou criar backup no staging.

**Alcance parcial:** o teste do pipeline real usa um rótulo diagnóstico explícito
UNBOUND-AUXILIARY-AUDIT, sem fingir vínculo de sessão. O gate real de artefatos
retorna FileNotFoundError e o gate de cobertura não é alcançado. Não se declara
fluxo completo ou cobertura real validada. Não foram encontrados session/coverage
nos diretórios legíveis pesquisados; /opt/harpisense/capturas teve Permission
denied, logo a existência de sessões nesse local continua não esclarecida.

**Aplicação ainda bloqueada:** staging é root:root (arquivos 0644, diretório
0755); o usuário harpiserver não pode escrever, e `sudo -n -l` pede autenticação
interativa. Não se mudou permissão nem se usou outro mecanismo de privilégio.
O usuário recebeu o comando abaixo para seu próprio terminal:

```sh
sudo /usr/bin/python3 -B /tmp/harpisense-p08p09-validated-batch.grdSWc/p08_p09/apply_staging.py --apply
```

O aplicador faz backup somente dos dois arquivos, recusa hashes inesperados,
preserva metadados, verifica hashes finais e guarda recibo no backup. Não reinicia
serviços. Após aplicação, falta repetir a validação apontando para o diretório
instalado, registrar backup/recibo e atualizar o estado — a validação temporária
não deve ser apresentada como aplicação concluída. Na última conferência, a VM
ainda tinha os hashes originais do pipeline/adapter, gates e leitor inalterados,
P11 PID 1787 sem restart e Store antigo cba6be…643c. Paginação não implantada.

Dependências registradas para as próximas entregas, **não executadas**:

1. Identificar sessão P08 real acessível, seus artefatos, janelas e inventário de
   vínculos; definir evidence_id, collection_session_id, sensor_id e target_ref
   sem derivá-los de nomes de arquivo ou promover contexto não autenticado.
2. Comprovar continuidade por fonte: intervalo, retenção/rotação, boot/cursor,
   lacunas, relógios e verificação independente. Integridade local não substitui
   cobertura; ausência de evento não vira zero sem prova de completude.
3. Reconciliar tipos e contagens com o catálogo/feature schema oficial. Os eventos
   telemetry_validation_failure/telemetry_duplicate não são novas features de
   contagem previstas. Não inventar colunas nem converter desconhecido para zero.
4. Validar metadados, hashes e dependências dos bundles RF/IF e os contratos de
   features, perfil, duração/ordem de janela, antes de qualquer execução futura.
5. Definir chamador e sessão completa com gates e evidências reais. Modelos,
   ataques e defesa continuam fora desta rodada.

Máquinas/fontes: para o próximo vínculo offline, HarpiServer com acesso autorizado
aos artefatos P08 e inventário pode bastar. Para comprovar fontes, disponibilizar
journal do consumidor de telemetria, logs do broker Mosquitto e da API FastAPI
conforme required_sources, no intervalo da sessão. Para nova sessão completa
futura, disponibilizar o host de captura/gateway inline e produtores legítimos
(ESP32/Poste 02) no percurso validado. Confirmar onde cada papel roda: não supor
VM separada ou endereço baseado na topologia candidata. Windows/VMware e
intermediário Tailscale são necessários somente se hospedarem/transportarem esses
papéis. Não é necessário executar Kali/ataques para o próximo vínculo offline.

Os relatórios, seleção de entrada, procedimento de aplicação/recuperação e
dependências detalhadas ficam em `backend/p08_p09/README.md` da branch de
implementação. Nenhum lote original, checkpoint, coletor, PostgreSQL, P11,
modelo ou ação de defesa foi modificado/executado nesta primeira entrega.
