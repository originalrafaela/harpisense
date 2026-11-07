# Retomada amanhã — instaladores Ubuntu — pausa em 2026-11-06

Prioridade atual: [consolidação do produto](PRODUCT_CONSOLIDATION_20261106.md).
Candidata 5 publicada, build `8b9c9ef`, 68 verificações reais com runtime
congelado aprovadas; Windows limpo e novo aceite Ubuntu continuam pendentes.
A VM do usuário permanece na candidata 4, sem migração ou alteração dos dados.
Entregas externas conflitantes e XAI sem hash final ainda não incorporados.

Atualização mais recente: reteste manual da candidata 3 revelou corrida MQTT
na instalação. [Falha preservada e candidata 4 pronta](evidence/native-installers/ubuntu-candidate3-retest-failure/README.md).
Nova VM `harpisense-ubuntu-reteste`, `192.168.155.149`, restaurada ao snapshot
limpo `Snapshot 1`; falha guardada em snapshot separado. Candidata 4 baixada
e conferida em `~/harpisense-teste/candidate4`, aguardando instalação
interativa pelo usuário. Não executar bootstrap de aceitação em paralelo.

Atualização após retomada autorizada em 2026-11-06:
[candidata 3 e ensaio Ubuntu aprovado](evidence/native-installers/ubuntu-candidate3-trial/README.md).
Backend integrado, nova release publicada, VM Ubuntu encerrada e snapshots
preservados. Windows limpo pendente: RAM livre 5115 MiB, mínimo com reserva
padrão 6144 MiB. Medir novamente antes de iniciar uma única VM Windows.
O registro original da pausa abaixo permanece como histórico.

Pausa solicitada pelo usuário: salvar o estado para continuar amanhã.
Nenhum teste, build, instalação, reboot ou restauração iniciado nesta pausa.

## Código e registros salvos

- Worktree: `harpisense-worktrees/native-installers`; branch `feat/native-installers`.
- `589ed25`: inclui catálogo Ubuntu e verificação de imports antes do banco.
- `84809df`: recibo/hashes da candidata 2 publicada.
- `24aff47`: ensaio real Ubuntu limpo, scripts e evidências sanitizadas.
- Release: `native-installers-20261106-candidate.2`, **não aprovada**;
  notas públicas atualizadas com o bloqueio. Assets e candidata 1 preservados.
- Evidências: `docs/evidence/native-installers/ubuntu-candidate2-trial/README.md`
  e arquivos JSON/TXT da mesma pasta. Traceback da primeira tentativa em
  `docs/evidence/native-installers/ubuntu-candidate1-failure.txt`.

Backend preparou o commit **`6587e00`**, `fix(auth): handle infinite throttle
sentinel on PostgreSQL 16`, na worktree `harpisense-worktrees/admin-throttle-pg16`,
branch `fix/admin-throttle-pg16`. Sua worktree estava limpa na consulta desta pausa.
O commit ainda **não foi integrado** à branch do instalador nem ao runtime da VM.
Consultar `docs/ADMIN_THROTTLE_PG16_REGRESSAO.md` dessa worktree para a validação
direcionada já executada pelo Backend. Não repetir testes aprovados sem motivo.
Confirmar publicação remota desse commit antes de depender dela; esta pausa não
modificou nem fez push da branch de outro agente.

## VM de ensaio e preservação

As VMs descartáveis anteriores não tinham snapshots. Não foram restauradas,
iniciadas, apagadas ou reinstaladas; a tentativa parcial ficou intacta.

Foi criada outra VM independente:

- VMX: `.native-test/candidate2-clean-20261106/Candidate2-Clean.vmx` nesta worktree.
- Hostname: `harpisense-candidate2-clean`; Ubuntu 24.04.5 x86_64; RAM 2 GiB;
  disco novo de 24 GB; rede NAT.
- Snapshot anterior à instalação, criado e concluído: **`clean-before-candidate2-20261106`**.
- Último IP confirmado antes e depois do reboot: **`192.168.155.148`**.
  **Consultar novamente VMware/console antes de acessar; não presumir IP amanhã.**
- SSH: usuário `trial`, chave exclusiva em
  `.native-test/candidate2-clean-20261106/trial_ed25519`; known_hosts adjacente.
  A chave privada não está no Git. Preservar a pasta local; commit/push não fazem
  backup dos discos, snapshot nem da chave. Nenhum segredo foi incluído nos registros.
- Instalador baixado no guest em `/home/trial/harpisense-trial`.
- Instalação em `/opt/harpisense`, estado em `/var/lib/harpisense`.
- A VM nova foi deixada ligada após o ensaio. Não houve consulta ou mudança
  de energia nesta pausa. Serviços normais podem continuar gravando heartbeats;
  não havia apt ou instalador em execução ao concluir o ensaio.
- Laboratório (`Harpisense-Server`, Poste2, Kali) não foi alterado nem desligado.
  Usar somente uma VM de ensaio por vez, preservando o laboratório.

## Resultado real da candidata 2

Passaram: download/SHA-256, instalação limpa, reboot real, quatro serviços
ativos/habilitados automaticamente, frontend HTTP 200, MQTT TLS autenticado
QoS 1 e persistência de uma projeção identificável no PostgreSQL 16.15.

SHA-256 Ubuntu publicado:
`a72c5966c1a53fac95c314ffe810aae6916c63dc381d2db666cc39a6d315daca`.
Mensagem do ensaio: `ubuntu-candidate2-d2251c3db80d495fa671c831d360978f`.

Falhou: bootstrap administrativo, HTTP **503 AUTH_UNAVAILABLE**.
Diagnóstico real com rollback: **DatetimeFieldOverflow / SQLSTATE 22008**.
O throttle subtrai `clock_timestamp()` de `blocked_until=-infinity`, operação
rejeitada no PostgreSQL16. Renovar o grant pelo comando oficial não resolveu.
Nenhuma conta foi criada; nenhum patch manual de módulo ou banco foi aplicado.

Login/MFA, configuração persistida e leitura autenticada da mensagem pela API
**não foram aprovados nem concluídos**, pois dependem do bootstrap.
API anônima retornou 401 corretamente; isso não substitui leitura autenticada.
A dificuldade inicial de copiar/colar é independente das duas falhas reais:
catálogo ausente na candidata 1; throttle PostgreSQL16 na candidata 2.

## Próxima ação ao retomar

1. Conferir branch/worktree, retorno do Backend e commit `6587e00`; integrar
   a correção revisada sem alterar trabalhos de outros agentes.
2. Gerar outra candidata com versão/release e SHA-256 novos, mantendo os assets
   das candidatas 1/2. Não modificar a candidata 2 publicada para aparentar aprovação.
3. Preservar os resultados atuais antes de restaurar o snapshot limpo da VM nova
   (ou usar outro disco novo). Não reinstalar sobre a tentativa nem apagar
   `/opt/harpisense` ou `/var/lib/harpisense` para simular alvo limpo.
4. Confirmar novamente IP e identidade SSH, baixar/conferir/instalar a nova
   candidata. Validar bootstrap/MFA, configuração salva, reboot, serviços
   automáticos, conta/configuração preservadas e MQTT→PostgreSQL→API autenticada.
5. Registrar apenas testes realmente executados e salvar commit/push sanitizados.

Não restaurar snapshot nem executar testes só por abrir este documento:
aguardar a retomada do usuário.
