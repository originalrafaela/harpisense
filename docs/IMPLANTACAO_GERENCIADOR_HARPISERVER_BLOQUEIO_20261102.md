# Implantação controlada do gerenciador — 02/11/2026

## Resultado desta retomada

**Implantação não iniciada.** O worktree candidato foi conferido sem alterações
em `feat/frontend-backend-autonomia`, commit base
`1be05034e6e8540e3f3b70db3fe6ad7cf475aba3`, igual ao tracking remoto observado
naquele momento. Este relatório foi publicado depois como commit `3a27920`.
O worktree da branch `main` não foi usado nem alterado; nele havia arquivos não
rastreados preexistentes, preservados.

O endpoint SSH previamente aprovado foi testado em modo Batch, somente leitura,
com `StrictHostKeyChecking=yes`, `IdentitiesOnly=yes` e timeout. As duas chaves
existentes testadas para `harpiserver@100.66.89.7` foram recusadas com
`Permission denied (publickey,password)`. `ssh-add -l` retornou que não havia
agente SSH disponível nesta sessão. Isso **não prova** que a chave perdeu
autorização. Não houve prompt de senha, criação/troca de chave, aceitação de host
novo, acesso remoto, backup, escrita, reinício ou mudança de serviço. Portanto,
estado atual da VM, fingerprint de host alcançado, alterações remotas concorrentes,
backup e versão implantada são **não verificados**. Não alegar comparação ou
recuperação remota aprovada.

Ordem da próxima retomada: primeiro conferir a chave existente e seu fingerprint,
verificar se ela está carregada no agente SSH e se o agente/chave estão disponíveis
na sessão Maestri usada para acessar o host; só então repetir a conexão SSH estrita.
Não propor alteração em `authorized_keys` antes desse diagnóstico. Manter a
entrada `known_hosts` aprovada. Se o fingerprint do host divergir, parar e conferir
por canal independente. Não enviar chave privada, senha ou token no chat. Se a
implantação posteriormente exigir `sudo` interativo, será preparado o comando
concreto e aguardada sua execução pelo operador no terminal.

## Inventário candidato conhecido, ainda sem comparação com a VM

- Bootstrap de composição: `backend/delivery/app.py`; a factory candidata
  preserva `build_app`, adiciona auth e API explicitamente, e só monta o aplicador
  quando o instalador fornece o diretório persistente.
- Autenticação existente: `backend/admin_auth/` e suas dependências registradas
  no pacote backend.
- API, contratos, store, recuperação e aplicador: `backend/config_manager/`,
  em especial `PRESENTATION.md`; migrações existentes 001/002, sem SQL novo.
- Dependências de runtime e consumidores preservados: `backend/delivery/`,
  `backend/domain/`, `backend/p11_postgresql/`, `genai/harpia/` e os consumidores
  atualmente carregados pelo serviço P11. A instalação exige comparar esses
  módulos e suas dependências com o bootstrap real, não substituir a árvore ativa.
- Frontend compatível: fonte/artefato construído de `frontend/`, incluindo o
  assistente e o painel de apresentação; conferir o servidor e proxy atualmente
  servido antes de trocar qualquer artefato. A entrega `40908b3` já foi integrada
  e validada nas rodadas posteriores; não repetir cherry-pick nem tratá-la como
  pendência. A origem e o mecanismo de hospedagem da VM permanecem não verificados
  nesta retomada.
- Persistência do aplicador: PostgreSQL existente para propostas, revisão efetiva,
  recibos e auditoria; diretório privado por instalação contendo
  `presentation.json` e `presentation-journal.json`. Nenhuma migração automática,
  seed ou alteração de fuso do sistema é permitida.

Esse inventário é o conjunto candidato a comparar, não prova que cada arquivo,
dependência ou frontend já esteja instalado na VM. P11, PostgreSQL, HarpIA,
consumidor MQTT e integrações P08/P09 devem ser comparados e preservados. Não
incluir alterações de MQTT, rotas, VPN, nftables, firmware, autonomia ou modelos.

## Backup e restauração que ainda precisam ser executados

Nenhum backup remoto foi criado nesta retomada. Antes da implantação, a preparação
deve:

1. Ler unidades/systemd, comandos de inicialização, diretórios, versões de Python,
   pacotes, frontend/proxy e hashes dos arquivos ativos; conferir que não mudaram
   desde a leitura de preflight antes de cada substituição.
2. Confirmar instalação, database PostgreSQL, proprietários/permissões e diretório
   de apresentação configurado. Observar operação ativa e journal; bloquear
   temporariamente novas aplicações do gerenciador durante o snapshot coordenado,
   sem parar MQTT, PostgreSQL ou consumidores de telemetria.
3. Criar backup restrito, datado e com manifesto SHA-256 do conjunto de arquivos
   que será substituído, unidades/configuração sem segredos, artefato/frontend
   servido e diretório de apresentação (ambos os arquivos, inclusive journal).
   Fazer dump consistente do banco afetado e registrar versão/roles necessárias
   por canal seguro. Não registrar credenciais em manifesto ou evidência.
4. Ensaiar restauração do dump em instância/database isolado, sem apontar a
   restauração ao database operacional. Restaurar também cópia dos arquivos em
   diretório temporário isolado e conferir hashes, proprietário, modo, conteúdo,
   identidade/revisão/fingerprint e leitura do consumidor. Nunca misturar snapshot
   de outra instalação.
5. Aprovar recuperação coordenada do par PostgreSQL + diretório de apresentação.
   Em rollback de código, preservar o código anterior e restaurar o artefato
   anterior conforme o journal/estado efetivo; não editar revisão, fence,
   recibos ou auditoria diretamente no SQL. Para `RECOVERY_REQUIRED`, manter o
   serviço bloqueado e seguir `backend/config_manager/PRESENTATION.md`.

Como a VM não pôde ser lida, ainda não há comando remoto de backup/restauração
validado contra os caminhos/versões reais. Não executar comandos genéricos de
`pg_restore` sobre banco operacional.

## Validações e limites

- **Local já validado** (não repetido): navegador → HTTP real → PostgreSQL
  descartável, incluindo aplicação, consumo, restart, idempotência, conflito,
  falha/rollback, recuperação desconhecida, auditoria, autorização e timestamps.
  Evidência: `docs/VALIDACAO_APLICADOR_APRESENTACAO_20261101.md` e
  `docs/evidence/presentation-20261101/`.
- **Real na VM nesta retomada:** somente tentativas de SSH sem autenticação
  concluída; nenhuma leitura de serviços ou dados. Não houve telemetria autenticada,
  retomada do assistente, proposta, aplicação ou auditoria real verificada.
- `operational=false` continua obrigatório. Aplicação confirmada de nome/fuso não
  torna MQTT, captura, P08/P09, detecção, defesa ou inferência operacionais.
- Gerenciador e aplicador de nome/fuso estão validados localmente, mas ainda não
  implantados no HarpiServer.

## Processos temporários locais ao encerrar

Conferência rápida em 02/11/2026: nenhuma escuta nas portas locais usadas pelos
previews/backend/túnel (4174, 4175, 8000, 18000–18002, 5174), nenhuma conexão TCP
associada aos processos Node/Python listados e nenhuma conexão associada ao
processo `ssh` observado (PID 34480). `docker ps` não retornou containers ativos.
A consulta filtrada de tarefas agendadas não retornou tarefa em execução.

Ainda existem processos Node/Python no host local; como não foi possível inspecionar
suas linhas de comando por restrição do sistema, não atribuir propriedade nem
encerrá-los às cegas. Não há evidência de túnel ativo que precise ser encerrado
antes de desligar as VMs. Isso não inspeciona processos dentro das VMs e não
substitui o procedimento normal de desligamento dos serviços nelas.

## Leituras de rede ainda solicitadas pela Edge

Reutilizar os relatórios e capturas históricos já disponíveis; não os rotular como
observação atual. Após restabelecer acesso, recolher uma vez, sanitizar e
compartilhar apenas os resultados necessários:

- **HarpiServer/Poste 2 (Ubuntu):** `hostname`; `ip -br addr`;
  `ip route get <BROKER_IPV4>`; `ss -nt`; `timedatectl show -p NTPSynchronized`;
  `cat /proc/sys/kernel/random/boot_id`;
  `systemctl show harpisense-mqtt -p ActiveState -p MainPID -p NRestarts`;
  `journalctl -u harpisense-mqtt --no-pager -n 1 -o json` (sanitizar endereço,
  usuário e conteúdo sensível; não exportar Environment).
- **Windows broker:** `Get-NetIPConfiguration`; `Get-NetRoute -AddressFamily IPv4`;
  `Get-NetTCPConnection -LocalPort 1883`; `Get-Service mosquitto`;
  `w32tm /query /status`. Consultar somente listener/configuração e retenção
  sanitizadas; não publicar mensagem nem iniciar captura nesta rodada.
- **ESP32/intermediário:** anexar configuração não secreta de Wi-Fi/destino,
  modo proxy/subnet e firmware/perfil instalado, se já disponível. Não revelar
  SSID privado, senha, token, chave, payload ou credencial.

Estado do Mosquitto já observado pela Edge em 01/11/2026: serviço Windows parado
(`Stopped`), sem conexão retornada na porta 1883. É um dado datado; conferir o
estado corrente na próxima retomada. A lista única das leituras pendentes está em
`docs/EDGE_LEITURAS_PENDENTES_20261101.md` (console Poste 2, rotas Windows após
identificar o IP real, delta HarpiServer e dados sanitizados ESP32/intermediário/
fontes). Reutilizar essa lista e as evidências históricas; não repetir inventários
já lidos nem presumir que Wokwi represente a rede física. O inventário de rotas e
conexões não prova percurso fim a fim. A proposta Edge de visibilidade/contenção
continua separada e não autoriza mudar rede, broker, firewall ou iniciar captura.

## Poste 1 — ensaio e próxima etapa física

Entrega IoT/Wokwi informada como validada no commit `69cd62d`; não confundir essa
simulação com ensaio na placa. Hardware atual: ESP32-WROOM-32 com LDR e LED.
Próximo passo físico é reconhecer o dispositivo por USB/COM e confirmar que a
porta corresponde à placa. Nenhuma placa foi gravada; não gravar firmware sem
autorização e checklist próprios.

## Próxima ação objetiva

Diagnosticar primeiro a sessão SSH: conferir a chave existente, carregamento no
agente e disponibilidade pela sessão Maestri; não presumir perda de autorização e
não propor `authorized_keys` antes disso. Em seguida, conferir Mosquitto e obter
as rotas pendentes da lista Edge antes de qualquer alteração de rede. A validação
local do gerenciador/aplicador e a integração do frontend `40908b3` estão
concluídas; nenhum cherry-pick frontend é necessário. Só depois do preflight
remoto, comparação dos módulos/dependências, backup e ensaio isolado de recuperação
podem começar a implantação controlada. Se qualquer hash, unidade, diretório,
esquema ou versão divergir, parar e preparar substituição mínima que preserve a
adaptação remota.
