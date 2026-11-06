# Ensaio real da candidata 2 — Ubuntu limpo — 2026-11-06

**Resultado: candidata não aprovada.** Instalação, serviços após reboot e
MQTT até PostgreSQL passaram; primeiro acesso falhou em `503 AUTH_UNAVAILABLE`.
Login/MFA, configuração persistida e leitura autenticada da telemetria pela API
não podem ser declarados aprovados.

## Alvos e preservação

Consulta real `vmrun listSnapshots ... showTree`: zero snapshots tanto em
`Ubuntu CLLONE TESTE` (OneDrive/Documentos/Virtual Machines) quanto na VM
`.native-test/clean-os/ubuntu2404/HarpiSense-Clean.vmx`. Nenhuma delas foi
iniciada, restaurada, limpa ou reinstalada. A tentativa parcial foi mantida
intacta; o traceback anterior permanece em `../ubuntu-candidate1-failure.txt`.
Não foram coletados novos logs privados daquela máquina desligada.

Inventário elevado encontrou somente a VM do laboratório `Harpisense-Server`
ligada. Nenhum comando de alteração foi dirigido a ela ou ao Poste2/Kali.
Uma única VM de ensaio foi iniciada e usada durante esta rodada.

Novo alvo criado em `.native-test/candidate2-clean-20261106/Candidate2-Clean.vmx`,
com disco independente de 24 GB, 2 GiB de RAM e NAT. Imagem oficial Ubuntu
24.04, origem e SHA-256 em `image-origin.json`; hash conferido antes da conversão
do VMDK. A imagem foi inicializada por cloud-init com usuário `trial` e chave
SSH exclusiva. Chave privada e arquivos de acesso ficam apenas em `.native-test/`,
ignorados pelo Git. Sem autenticação por senha SSH.

O IP `192.168.155.148` foi obtido do console da VM nova. A chave SSH de host
foi fixada a partir desse mesmo console; a conexão usou verificação estrita.
Hostname confirmado: `harpisense-candidate2-clean`. `/etc/os-release` informou
Ubuntu 24.04.5 LTS, `VERSION_ID=24.04`; x86_64. Cloud-init concluído, sem
`/opt/harpisense`, `/var/lib/harpisense`, PostgreSQL16 ou Mosquitto antes do ensaio.

Criado e confirmado snapshot **`clean-before-candidate2-20261106`** na VM nova
antes da instalação. A operação demorou cerca de quatro minutos; aguardamos
o callback VMware de sucesso antes de iniciar o instalador.

## Instalação e reinício

Download da release publicada `native-installers-20261106-candidate.2` por HTTPS
feito dentro do guest em `/home/trial/harpisense-trial`.
`sha256sum -c` retornou `OK` para o `.run`:
`a72c5966c1a53fac95c314ffe810aae6916c63dc381d2db666cc39a6d315daca`.
Instalação executada uma única vez por `sudo sh`, sem checkout ou Docker no guest.
Terminou com `HarpiSense instalado`; stdout sanitizado em `install.txt`.

Os quatro serviços estavam ativos e habilitados. O teste de primeiro acesso
falhou; a renovação oficial do grant (`entry.py grant`) não resolveu. Nenhuma
conta foi criada. O diagnóstico com rollback retornou SQLSTATE `22008`.

Executado `sudo reboot` somente nessa VM nova. Depois, `vmrun getGuestIPAddress`
confirmou novamente `192.168.155.148`, e a identidade SSH fixada foi mantida.
Boot ID mudou de `8b5544a4-3dbc-49a5-8a5c-e3fcf2db08b8` para
`6f8e95bc-3852-44ce-b381-8e24f4d63a06`: reboot real, sem reinício manual dos serviços.

## Resultados efetivos

| Verificação | Resultado |
|---|---|
| Download/SHA-256/instalação limpa | Passou |
| Serviços PostgreSQL/broker/API/consumidor ativos e habilitados | Passou antes e após reboot |
| Frontend HTTP após reboot | 200 |
| API telemetria sem autenticação | 401, acesso continua negado |
| Bootstrap administrativo | Falhou: 503 AUTH_UNAVAILABLE |
| Login/MFA | Bloqueado no bootstrap; enrollment/login não executados |
| Configuração persistida após reboot | Não executado; exige login que falhou |
| MQTT TLS autenticado, QoS 1 | Passou após reboot |
| Consumidor MQTT → PostgreSQL | Uma projeção correspondente ao message_id |
| PostgreSQL → API autenticada | Não executado; exige login que falhou |

Publicação identificável: `ubuntu-candidate2-d2251c3db80d495fa671c831d360978f`.
Mensagem sintética explícita para ensaio do instalador; não comprova sensor físico,
captura, detecção ou contenção. PostgreSQL observado: 16.15.
Resultados legíveis por máquina em `before-reboot.json` e `after-reboot.json`.

## Falha e coordenação

`bootstrap-diagnostic.json` preserva classe e SQLSTATE sem parâmetros, DSN,
senhas, grants ou material MFA. O diagnóstico usa os módulos instalados em
processo separado e força rollback; não modifica o runtime nem persiste conta.

O cálculo de throttle em `backend/admin_auth/service.py` subtrai
`clock_timestamp()` do valor inicial `blocked_until=-infinity`. PostgreSQL16
rejeita essa subtração com `DatetimeFieldOverflow`, mascarado como AUTH_UNAVAILABLE.
Backend Data foi acionado pela skill Maestri para corrigir e testar essa
compatibilidade em fonte, numa worktree separada. Nenhum patch foi aplicado
à VM ou ao artefato da candidata 2; nenhum valor do banco foi trocado como contorno.

## Estado e próximo passo

VM nova permanece ligada com os serviços normais, que continuam gravando
heartbeats/dados no seu próprio disco. Não há instalação apt/HarpiSense em andamento.
A VM parcial e o laboratório permanecem intactos.

Preservar estes resultados antes de qualquer restauração. Depois da correção
do Backend, gerar outra candidata imutável e retestar partindo do snapshot limpo
ou de outro disco novo. Não atualizar o binário da candidata 2 nem instalar por cima
desta tentativa para alegar homologação. A rodada atual não aprova login/MFA,
persistência da configuração ou leitura autenticada da mensagem pela API.
