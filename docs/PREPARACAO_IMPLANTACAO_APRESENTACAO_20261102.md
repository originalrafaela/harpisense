# HarpiServer — preparação e recuperação verificadas em 02/11/2026

## Pausa solicitada pelo operador

Trabalho pausado por limite de créditos. **Não continuar a implantação até
nova solicitação do operador.** Ponto publicado anterior: `34a63a2`, branch
`feat/frontend-backend-autonomia`. Trabalhos dos demais agentes preservados.
Edge publicada em `a2e7a2f`; IoT/Wokwi em `69cd62d` (não é execução física).

Confirmado pelo operador: `deploy.py migrate` **NÃO foi executado por ele**.
Conferência final somente leitura: recibo `migration.json` ausente e bootstrap
ativo ainda com SHA-256
`81950f60a288a95777da73c64ffdf28fa5dd9f871fcd5cd243ebff6cc76947e7`.
Bootstrap novo não ativado; frontend novo não publicado; validação operacional
pendente. SSH restabelecido; comparação e recuperação isolada aprovadas nos
limites descritos abaixo; ensaio HTTP candidato aprovado. Restauração de
proprietário/grupo/modos permanece preparada para a etapa privilegiada, sem
ser confundida com a restauração de bytes já conferida.

Consumidor MQTT com reinícios preexistentes, **sem causa confirmada**. Não
houve alteração nem correção desse serviço. Não atribuir reinícios à candidata.

Encerramento: `pg_ctl status` confirmou que o cluster PostgreSQL isolado não
está rodando; não houve listener nas portas temporárias 18019/55449 nem processo
rehearse.py/snapshot.py/deploy.py na conferência final. O servidor HTTP de ensaio
foi encerrado pelo preparador. Não foi iniciado túnel ou preview local nesta
rodada; sessões de comando concluídas. Nenhum processo de outro agente foi
encerrado. Não há tarefa temporária desta rodada que impeça desligar as VMs;
usar desligamento normal do sistema para preservar os serviços/banco existentes.

### Primeira ação na retomada, antes de migrar

1. Conferir branch/worktree e alterações posteriores; restabelecer SSH estrito
   pela chave existente. Não presumir sobrevivência do agente após desligamento.
2. Na release privada da VM, executar apenas a verificação de guards:

   ```sh
   cd /opt/harpisense/staging/p11-postgresql/.presentation-releases/presentation-20261102-r1
   /opt/harpisense/venv/bin/python -c 'import deploy; deploy.checked(); print("GUARDS_AND_BACKUP_HASH_OK")'
   ```

   Isso confere hashes da release, arquivos ativos protegidos, dump e recibo de
   restauração; **não migra nem ativa**. Conferir também `rehearsal.json` e seu
   candidate_sha256 contra app.candidate.py, permissões/acesso ao backup, espaço
   em disco, unidades/dependências e ausência de alteração concorrente.
3. Ler o estado atual do banco em transação READ ONLY: confirmar que hs_config
   ainda não existe, autenticação permanece válida e avaliar novos dados desde
   o snapshot. Hash íntegro não garante atualidade do backup. Havendo mudanças
   relevantes, produzir novo backup consistente e ensaiar sua recuperação;
   atualizar de forma revisada a referência BACKUP do preparador e manifesto
   antes de pedir sudo. Não reutilizar cegamente o caminho fixo desta rodada.
4. Somente com guards, comparação e recuperação ainda válidos, solicitar ao
   operador o comando exato `sudo .../deploy.py migrate` registrado abaixo.
   Se qualquer divergência aparecer, parar antes de escrever e preparar a
   correção mínima. Não repetir a suíte local já aprovada sem motivo novo.
5. Após migração comprovada, ativar com guards, solicitar restart somente de
   harpisense-p11 e publicar/verificar o frontend correto. Realizar as validações
   operacionais pendentes, preservando o par registry/journal/artefato e todos
   os limites anteriores. Aprovação de apresentação não torna IDS/IPS operacional.

## Estado desta etapa

SSH restabelecido com a chave existente carregada pelo operador. Agente acessível
fora do sandbox; dentro dele, acesso ao agente/chave/rede continua restrito.
Conexão estrita confirmou host conhecido, usuário harpiserver e hostname gateway.
Branch limpa ao iniciar em `9ae9dae`; entregas desde `1be0503` preservadas.
Não houve troca de chave, alteração de known_hosts ou pedido de senha no chat.

**Release preparada, ainda não ativada nesta etapa.** A execução privilegiada
da migração foi solicitada ao operador. Nenhum restart de serviço operacional
foi executado pelo agente. Os resultados abaixo distinguem preparação isolada
de validação no banco operacional.

## Comparação real

P11 usa `/opt/harpisense/staging/p11-postgresql/app.py`, composição da fábrica
P11 V2 em `integration-v2`, Store instalado e complemento `harpia_deterministic`.
Não será substituído por `backend/delivery/app.py`, que é composição local.
O bootstrap real já instala sessão administrativa; existe uma conta provisionada
e schema de autenticação versão 1. Health real sem sessão retornou 401.
Não existia `hs_config` nem diretório de apresentação instalado.

| Componente preservado | SHA-256 observado |
| --- | --- |
| Bootstrap ativo anterior | `81950f60a288a95777da73c64ffdf28fa5dd9f871fcd5cd243ebff6cc76947e7` |
| Store | `cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c` |
| Consumidor MQTT | `188490130d89a3eebe6370bd23e645cd5089ef18f80364624b3f3e0ce0da8f30` |
| Integrador P08 | `f1537b54ba721153b3daf8a09a09ba1e7aef24aee4a513828302ca237e5f06a5` |

Runtime: Python 3.14.4, FastAPI 0.143.3, psycopg 3.3.6, jsonschema 4.26.0,
Uvicorn 0.54.0, PostgreSQL 18. A lista instalada foi comparada às dependências
candidatas; nenhuma instalação/downgrade de pacote foi necessária. Linux já
oferece ZoneInfo para os fusos ensaiados; tzdata Windows não se aplica à VM.

Os dois fontes de autenticação divergentes foram copiados sem credenciais e
comparados: `api.py` acrescenta `app.state.require_admin_token`; `service.py`
acrescenta `reauthenticate`, reutilizando conta, senha scrypt, throttle e auditoria.
Demais fontes e SQL de autenticação conferem. Não há reprovisionamento de conta.

As migrações aprovadas 001/002 do gerenciador serão aditivas em `hs_config`,
com checksum. Proposta: proprietário postgres, runtime existente com USAGE,
SELECT e DML limitado por tabela; sem CREATE/DELETE/TRUNCATE concedidos no novo
schema. O usuário existente é não superuser e não createdb, proprietário das
tabelas públicas preexistentes; seus privilégios anteriores não serão alterados.

Precedência das referências preservada: entregas aprovadas `referencias/versão_v2`
e pacotes `referencias/Versões corretas` onde ainda não substituídos. Ausência
em V2 não foi usada para descartar componentes. Nenhuma revisão de MQTT, P08/P09,
modelos, firmware, autonomia ou execução foi incluída na release.

## Release e recuperação

Release privada na VM:
`/opt/harpisense/staging/p11-postgresql/.presentation-releases/presentation-20261102-r1`.
Contém autenticação compatível, config_manager, dependências de contrato aprovadas,
bootstrap candidato separado, preparadores e manifesto de hashes. O catálogo
de constantes é dependência transitiva do contrato; não é executado como motor.

O candidato mantém fábrica P11, Store, HarpIA e credenciais/origens existentes;
acrescenta ConfigStore, API e PresentationApplicator. Identidade explícita:
`harpiserver-presentation`; capabilities `harpiserver-presentation-only-20261102`,
sem referências operacionais habilitadas. Diretório persistente previsto:
`/opt/harpisense/staging/p11-postgresql/presentation-state`, exclusivo e 0700.
Nome/fuso são os únicos efeitos permitidos; `operational=false` permanece.

Bootstrap candidato SHA-256:
`d8dc01de8ee14ca4daa31d34408882ef2a22a1d7858cad46abdd308bb0e957a9`.
Manifesto sanitizado em `evidence/presentation-deployment-20261102/release-manifest.json`.
`source_commit=9ae9dae...` identifica os módulos de produto; os utilitários
de implantação foram preparados nesta rodada e têm hashes próprios no manifesto.

Backup privado:
`/opt/harpisense/staging/p11-postgresql/.presentation-backups/20261102T200522453566Z`.
Dump SHA-256: `47c60fcc3db5ad100b50a57090f38a233fc420bf0f4399391ee61b1067222e9a`.
Inclui snapshot PostgreSQL consistente, bootstrap, Store, consumidor, HarpIA,
release de autenticação, configuração técnica privada e unidade P11, com manifesto
de hashes/proprietário/grupo/modo. Credenciais, dump, conteúdo de contas e
sessões ficaram exclusivamente na VM. Registry e arquivos de apresentação
estavam ausentes, fato registrado explicitamente, sem simular backup de arquivos
inexistentes. Para snapshots futuros com aplicador ativo é necessária coordenação
das escritas e inclusão de presentation.json e presentation-journal.json.

Restauração integral feita no PostgreSQL descartável `presentation_restore`,
em cluster próprio dentro do backup, usando somente socket Unix em diretório
privado, sem listener TCP. Nenhum comando de restore apontou ao banco operacional.
As sete tabelas restauradas conferiram em contagem/digest UTC; 22 projeções
preservadas, digest `e1b9b661521848bac8f2e4790bf4bb3e`. Arquivos também restaurados
em `restore-files` e conferidos byte a byte. Propriedade/modos originais estão
no manifesto; seu ensaio completo requer a etapa privilegiada já preparada,
exclusivamente sobre essa cópia isolada. Cluster e servidor HTTP temporários
encerrados após o ensaio aprovado.

Recuperação operacional: nunca restaurar esse dump por cima do banco atual.
Preservar novas tabelas, revisões, recibos, auditoria e telemetria posterior.
O bootstrap anterior autenticado permanece no backup. Antes de eventual retorno
de código, conferir hashes e o estado atual; retorno de código não desfaz uma
apresentação efetivamente aplicada. Recuperação do par registry/journal/artefato
segue `backend/config_manager/PRESENTATION.md`, sem editar status/revisão/fence
no SQL ou apagar journal. Conservar diretório da mesma instalação e bloquear
aplicações se a recuperação não puder ser confirmada.

## Ensaios e limites

Não foi repetida a suíte local aprovada de 01/11. Houve ensaio curto de compatibilidade
da composição real no runtime da VM, por HTTP loopback 18019, **exclusivamente
contra o banco restaurado e diretório de apresentação isolado**:

- Sessão real de uma conta sintética criada somente na cópia restaurada;
  login/logout, recusa 401 sem sessão e após revogação.
- Health, current, setup, catálogo e apresentação via HTTP.
- Proposta, validação, reautenticação, aplicação, consumo, retry idempotente,
  revisão efetiva e sequência de auditoria confirmados.
- Original `2026-11-01T12:00:00Z` preservado; exibição em America/Sao_Paulo
  `2026-11-01T09:00:00-03:00`. Projeções preservadas integralmente.
- Rodada final usa runtime de teste sem CREATE no schema hs_config;
  não depende de privilégios de proprietário para o gerenciador funcionar.

O preparador foi corrigido durante esses ensaios: inclusão da dependência
transitiva `harpisense_catalog`, contexto fork explícito para Python 3.14,
limpeza dos auxiliares e diretório novo pareado a cada restauração de banco.
Reutilizar journal de outro ensaio provocou 409 de recuperação, como esperado;
não foi corrigido por edição de estado ou journal operacional. Tentativas
anteriores e artefatos de ensaio foram preservados. O recibo final aprovado
está em `evidence/presentation-deployment-20261102/rehearsal.json`.

Frontend candidato compilado com TypeScript/Vite em
`frontend/local-evidence/presentation-deploy/dist`; dist anterior preservado em
`frontend/local-evidence/presentation-deploy/frontend-backup`, com restauração
de arquivos conferida. Nenhuma publicação nesta etapa. Index candidato SHA-256
`9e00a85888e9a6ca343d34bd0d057e2923284f8127f3a5dc83e00a2007537fa9`;
JS `index-HZE-Vkio.js`, SHA-256
`f17c9979b3e2140c18e2e840f9c52d37414437b686a647babf1a8d7cdc2cb69a`.
Publicação posterior deve conferir processo/worktree e bytes servidos na porta
4174, com túnel SSH loopback para API real. Portal local antigo não é validação.

Validação no banco operacional ainda pendente: login real, telemetria,
retomada do assistente, proposta/validação, aplicação de nome/fuso, consumo,
revisão/auditoria e preservação dos timestamps, além da correspondência do
frontend aberto com o artefato publicado. O sucesso isolado não substitui isso.

## Próximo comando do operador

O sudo não interativo retornou `interactive authentication is required`.
Conforme instrução do usuário, aguarda-se execução no terminal SSH:

```sh
sudo /opt/harpisense/venv/bin/python /opt/harpisense/staging/p11-postgresql/.presentation-releases/presentation-20261102-r1/deploy.py migrate
```

Efeito: conferir hashes/recuperação, ensaiar proprietário/modos na cópia isolada
e executar 001/002 como postgres, com grants limitados ao runtime existente.
Não altera tabelas públicas, bootstrap ou serviços. Se falhar, conservar erro
sanitizado e log privado na VM; não repetir contra schema parcialmente divergente.
Após confirmação, o agente confere a migração e ativa o bootstrap com guards.
Só então será necessário ao operador reiniciar **apenas** harpisense-p11.service.
Não executar restart antecipado. Não enviar senha ao chat.

## Edge e condição preexistente de MQTT

Delta somente leitura em `2026-11-02T21:02:09Z`, compartilhado sanitizado via
Maestri com Edge Security: ens33 192.168.155.144/24, ens37 10.20.30.1/24,
default via 192.168.155.2 em ens33; destino candidato 192.168.155.1 alcança
ens33 com src 192.168.155.144; forwarding IPv4=0; NTPSynchronized=yes.
O destino candidato não foi declarado broker efetivo sem configuração do produtor.
Canal SSH estrito Tailscale preservado; integrador P08 com hash anterior.

Consumidor MQTT estava ativo, mas NRestarts passou de 731 para 1266 entre
leituras. Nenhum restart foi solicitado pelo agente. Registrar como instabilidade
preexistente, sem diagnosticar causa ou alterar MQTT nesta rodada. Telemetria
histórica no banco não comprova ingestão nova, broker disponível ou sensor físico.
Poste 2/retorno Windows/ESP32/AP/fontes e cursores continuam com Edge. Nenhuma
captura, contenção, inferência, BitNet, checkpoint ou alteração de rede foi feita.

## Retomada de 03/11/2026 — aguardando migração interativa

Conferência direcionada às 18:08 UTC: worktree limpo em `a6e4159`, branch
`feat/frontend-backend-autonomia`, sem commits posteriores. SSH estrito com a
chave existente confirmou usuário `harpiserver`, hostname `gateway` e fingerprint
ED25519 `SHA256:Uv4vgbxMChdUGjvlC8Dw+j/xQRZtVDPn5+17OpJPboA`.

`deploy.checked()` retornou `GUARDS_AND_BACKUP_HASH_OK`: hashes da release,
arquivos ativos protegidos, dump e recibo de recuperação conferem. Candidato
corresponde ao `candidate_sha256` do ensaio aprovado. Dependências FastAPI,
psycopg, jsonschema e Uvicorn mantêm as versões registradas acima. Unidade P11
ativa com o mesmo bootstrap, usuário e API loopback 8000.

Em transação REPEATABLE READ READ ONLY, todas as sete tabelas atuais coincidiram
em contagem e digest com o snapshot aprovado: inclusive 1 conta, 6 sessões,
11 eventos de autenticação e 22 projeções. Nenhum delta foi encontrado.
Backup privado com modo 0700 e aproximadamente 10,7 GB livres. Não foi necessário
novo backup, restore ou repetição do ensaio HTTP. A evidência é de telemetria
histórica preservada, sem comprovação de novas mensagens MQTT.

`hs_config` continua ausente; `migration.json` e `presentation-state` também.
Nenhuma migração, ativação ou reinicialização operacional foi executada nesta
retomada. Caminho e guards do comando sudo acima reconfirmados; aguardar a saída
do operador antes de prosseguir. A autenticação HTTP e demais validações reais
permanecem para depois da migração/ativação. Não houve delegação ou mudança de
rede, consumidores, P08/P09, firmware, modelos ou autonomia.

### Migração comprovada e bootstrap ativado — 03/11/2026

Operador informou `CONFIG_SCHEMA_READY; no service restarted; bootstrap unchanged`.
Conferência remota confirmou recibos migration.json/restore-metadata.json existentes,
root:0600; conteúdo privado não foi lido pelo usuário de serviço. Checksums SQL
001/002 instalados no banco conferem exatamente com a release, runtime sem CREATE
em hs_config e guards novamente aprovados. `deploy.activate()` concluiu:
`BOOTSTRAP_ACTIVATED; restart only harpisense-p11.service with operator sudo`.
Registry provisionado e diretório persistente criados pelo ativador aprovado;
bootstrap substituído atomicamente. Nenhum serviço foi reiniciado pelo agente.

Próxima ação interativa do operador: `sudo systemctl restart harpisense-p11.service`.
Aguardar confirmação para validar o processo carregado e executar os checks HTTP
operacionais. Frontend candidato permanece preparado, ainda sem publicação nesta
retomada. Nenhuma alteração de conta, consumidor ou rede foi realizada.
