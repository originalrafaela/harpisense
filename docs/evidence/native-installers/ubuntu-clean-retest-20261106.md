# Nova VM descartável para repetição — 2026-11-06

Solicitação: criar outro alvo limpo, preservando a `Ubuntu CLLONE TESTE`
aberta pelo usuário em `192.168.155.147`. Nesse clone, o usuário observou
`/opt/harpisense` e `/var/lib/harpisense`, quatro serviços inativos e zero
units HarpiSense registradas: tentativa incompleta. Não houve acesso SSH
autenticado do agente ao clone, reinstalação, limpeza ou exclusão dele.

Nova VM criada em
`.native-test/ubuntu-clean-retest-20261106/Ubuntu-Clean-Retest.vmx`,
display name **HarpiSense Ubuntu LIMPO RETESTE**.
Ubuntu Server 24.04 x86_64, NAT, 2 vCPU, 2048 MiB RAM, disco independente
de 24 GB, sem HarpiSense instalado. Hostname a provisionar:
`harpisense-ubuntu-reteste`; usuário SSH `trial`, chave exclusiva local
`trial_ed25519` no mesmo diretório, fora do Git. Login SSH por senha desativado.
Sem pastas compartilhadas com o host.

Imagem oficial reutilizada do cache e novamente conferida contra o
`SHA256SUMS` preservado da obtenção original:
`https://cloud-images.ubuntu.com/noble/20261017/noble-server-cloudimg-amd64.vmdk`.
SHA-256 `9a1e3959c9f4ad9d4752101fd4ff9a43191fb7d72e61fa20e033f9fd235ce794`.
Conversão e expansão do novo disco concluídas com sucesso. A nova VM não
depende dos discos do clone antigo ou da VM do ensaio aprovado.

A tentativa inicial de clone completo do snapshot limpo foi recusada pelo
VMware com `The virtual machine should not be powered on. It is already running`.
Inventário confirmou somente `Ubuntu CLLONE TESTE` em execução; a origem
permanecia desligada. Nenhuma restauração ou alteração foi feita na origem.
Foi usada imagem oficial limpa para a criação independente.

**Estado ao criar:** nova VM desligada, primeiro boot/SSH/snapshot limpo ainda
pendentes. Clone antigo ainda ligado, RAM livre aproximada de 2036 MiB;
nenhuma segunda VM iniciada. O usuário foi orientado a desligar o clone antes
de iniciar a nova, mantendo uma VM por vez. Após o primeiro boot, confirmar IP,
UUID e chave SSH pelo console, esperar cloud-init e criar snapshot anterior
à instalação. Usar candidata 3 e conferir seu hash; resultados do ensaio
anterior não aprovam automaticamente esta nova execução.

O script `packaging/native/prepare_ubuntu_trial.py` agora permite destino,
hostname e imagem em cache com checksum explícito. Continua recusando destino
existente e valida nomes para mantê-los em `.native-test`. Nenhum runtime ou
artefato publicado foi alterado.
