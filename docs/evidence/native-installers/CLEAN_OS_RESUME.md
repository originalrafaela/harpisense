# Retomada: instalação e reboot em sistemas limpos

Conferência inicial: branch `feat/native-installers`, HEAD local/remoto
`35dd646f35efa75c64eff95fc984af0429469176`, worktree limpa, sem alterações
pendentes. EXE e `.run` locais conferem com os SHA-256 publicados. As 23
verificações anteriores **não foram executadas novamente**.

Foram localizados VMware Workstation e mídias Windows 11 Enterprise Evaluation
25H2 e Ubuntu 24.04.4 Desktop. Foram criados dois discos VMDK novos e esparsos,
sem clonar discos/configurações/identidades das VMs do laboratório:

- Windows: `.native-test/clean-os/windows11/HarpiSense-Clean.vmx`.
- Ubuntu: `.native-test/clean-os/ubuntu2404/HarpiSense-Clean.vmx`.

Cada alvo tem configuração preparatória de 4 GiB RAM, dois vCPUs, disco esparso
de até 64 GB e NAT, sem pastas do host compartilhadas. Os arquivos privados de
VM ficam fora do Git. Nenhum SO foi instalado nesses discos e nenhuma capacidade
de boot, TPM ou instalação do produto está comprovada por essa preparação.

O procedimento recusa iniciar se não houver 6 GiB livres: 4 GiB para o convidado
e 2 GiB de reserva para o host. Ubuntu encontrou 2.288 MiB livres e Windows
2.588 MiB. Esse é um bloqueio do **preflight do procedimento**, anterior a
qualquer tentativa de boot do hipervisor; não é uma falha do instalador.

| Plataforma | Instalação do produto | Reboot + MFA | Configuração preservada | Telemetria sem iniciar serviços |
|---|---|---|---|---|
| Windows limpo | Não executada | Não executado | Não verificada | Não verificada |
| Ubuntu limpo | Não executada | Não executado | Não verificada | Não verificada |

Para retomar depois de disponibilizar memória, executar na raiz desta worktree,
um alvo de cada vez:

```powershell
& ./packaging/native/prepare-clean-guests.ps1 `
  -WindowsIso 'D:/Programas/26200.6584.250915-1905.25h2_ge_release_svc_refresh_CLIENTENTERPRISEEVAL_OEMRET_x64FRE_pt-br.iso' `
  -UbuntuIso 'D:/Programas/ubuntu-24.04.4-desktop-amd64.iso' `
  -StartPlatform Ubuntu
```

Para Windows trocar somente `-StartPlatform Windows`. O helper preserva os
discos existentes e não os reinicializa. Ele prepara/inicia hardware virtual;
não instala automaticamente o SO nem executa a validação da aplicação.

Depois: instalar o SO limpo, transferir o instalador publicado e verificar seu
hash; instalar a central; criar conta/TOTP e salvar configuração; reiniciar o
**sistema operacional**; comprovar serviços automáticos antes de iniciar qualquer
processo manualmente; login MFA; consultar configuração preservada; publicar uma
mensagem autenticada identificável e conferir PostgreSQL/API e status MQTT.
Registrar cada plataforma separadamente. Não substituir reboot por reinício de
processos nem os testes novos pela suíte anterior.

As únicas VMs em execução na inspeção eram `Harpisense-Server` e
`HarpiSense-Ubuntu-Poste2`; nenhuma foi iniciada, parada, clonada ou alterada.
Os serviços PostgreSQL/Mosquitto Windows existentes também foram preservados.

Resultado estruturado: [clean-os-validation.json](clean-os-validation.json).
