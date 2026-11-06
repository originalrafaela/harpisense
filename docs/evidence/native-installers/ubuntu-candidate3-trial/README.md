# Candidata 3 — Ubuntu limpo — 2026-11-06

**Ubuntu aprovado. Windows limpo pendente por RAM.** Somente o alvo descartável
foi operado. Nenhuma correção de fonte, SQL ou serviço foi aplicada dentro da VM.

## Fonte e artefatos

Branch `feat/native-installers`, inicialmente limpa em `89cabc2`, descendente
de `24aff47`. O registro posterior de retomada foi preservado. Backend
`6587e009a19bf152060eceeb9c4682ee501f2065` integrado sem conflitos como `cbdcb18`.
Os sete testes direcionados já aprovados em PostgreSQL16/18 pelo Backend não
foram repetidos; documentação em `docs/ADMIN_THROTTLE_PG16_REGRESSAO.md`.

Release [native-installers-20261106-candidate.3](https://github.com/originalrafaela/harpisense/releases/tag/native-installers-20261106-candidate.3),
quatro assets, anteriores preservados. Commit de publicação `a5b71b6`.
Os builds foram iniciados em `cbdcb18`; o commit seguinte altera somente
publicação e identificação das mensagens do roteiro de teste, sem modificar
o runtime do produto. O manifesto Windows identifica `cbdcb18` como origem.
Verificação de imports do novo runtime Windows: `RUNTIME_IMPORTS_OK`.
Builds e logs privados em `.native-build/candidate3-*`.

| Artefato | SHA-256 |
|---|---|
| Ubuntu `.run` | `72b0e0776d44ea2f6ad1b4dffbc3815932270177ba1c1f6de82e5ffd23468b65` |
| Windows `.exe` | `828c21db39a40d588b18afc13831908b8cbfbb5b821e3b6f05aa412d7170603d` |

Recibo independente: [published-assets-candidate3.json](../published-assets-candidate3.json).
Os quatro digests foram conferidos contra o GitHub depois da publicação.
Download dentro do guest por HTTPS, SHA-256 fixado e checksum publicado ambos
retornaram `OK`. Instalação única pelo `.run` oficial, sem checkout/Docker no guest.

## Identidade, snapshot e custódia

VMX `.native-test/candidate2-clean-20261106/Candidate2-Clean.vmx`.
Display name `HarpiSense candidate2 CLEAN 20261106`; RAM 2048 MiB; NAT.
UUID VMX `56 4d a1 d4 ae fd 78 20-5e a1 71 44 5a 76 a2 5f`;
UUID DMI na ordem SMBIOS `d4a14d56-fdae-2078-5ea1-71445a76a25f`.
MAC `00:0c:29:76:a2:5f`; hostname `harpisense-candidate2-clean`;
machine-id `5a20f376179e45b4914ea2b6d0dddb64`.
IP confirmado antes e após reboot: `192.168.155.148`.
SSH `trial`, chave exclusiva e `known_hosts` original, com verificação estrita.

Antes de alterar a VM, VMware confirmou snapshot
`clean-before-candidate2-20261106`. Os resultados da tentativa anterior em
`../ubuntu-candidate2-trial/` não foram alterados. Além disso, criado snapshot
`candidate2-failed-preserved-20261106`, incluindo disco/memória da tentativa
anterior. Aguardado callback VMware de sucesso, UID 2, às 18:03:56 UTC,
antes de restaurar UID 1. Nenhum snapshot ou disco foi removido.

A restauração terminou com sucesso e deixou a VM desligada. A retomada da
memória não restabeleceu SSH/Tools; foi feito reset VMware somente do alvo
restaurado, **antes de instalar**, para obter novo boot. IP/SSH/UUID foram
reconfirmados; preflight registrou Ubuntu 24.04.5 x86_64 e ausência de
`/opt/harpisense`, `/var/lib/harpisense`, PostgreSQL16 e Mosquitto.
Isso não foi usado como contorno de defeito do produto instalado.

O inventário inicial e final reportou zero VMs em execução. Durante o ensaio,
somente esta VM foi iniciada. Harpisense-Server, Poste2, Kali e as tentativas
parciais anteriores não receberam comandos de alteração.
Chaves e material administrativo permanecem privados, fora do Git.
Os snapshots/discos locais não são copiados pelo commit/push.

## Resultados efetivos

| Verificação | Resultado |
|---|---|
| Download, dois checksums, instalação oficial em alvo limpo | Passou |
| Bootstrap real criando conta | HTTP 200; falha 22008 anterior ausente |
| TOTP inválido recusado; válido confirmado; dez códigos de recuperação | Passou |
| Senha sozinha sem sessão; login TOTP pela API | Passou |
| Login TOTP e acesso ao painel pelo Chromium | Passou antes e após reboot |
| Configuração salva pela API e retomada no navegador | Passou |
| Reboot completo, boot ID diferente | Passou |
| PostgreSQL/broker/API/consumidor ativos e habilitados após reboot | Passou, sem início manual |
| Conta e configuração/versionamento preservados | Passou |
| Nova publicação MQTT com TLS/autenticação, QoS 1 | Passou |
| Uma projeção PostgreSQL identificada e leitura pela API autenticada | Passou |
| Observação MQTT identifica a mesma mensagem | Passou |
| Backend instalado corresponde ao hash da fonte corrigida | Passou |

Boot ID antes `694888f0-a4d7-4eac-9c69-761bde5cbfbc`;
depois `b041c732-5086-4cac-ab19-fabf7f53b572`.
PostgreSQL instalado: 16.15.
Mensagem: `ubuntu-candidate3-b2dccba795ab41bb99cd63251995c799`.
Publicação sintética de aceitação, sem alegação de sensor físico/captura/defesa.

Relatórios: [antes](before-reboot.json), [depois](after-reboot.json),
[navegador antes](before-reboot-browser.json), [navegador depois](after-reboot-browser.json).
Roteiros: `packaging/native/run_ubuntu_trial.py`, `acceptance_ubuntu_guest.py`
e `acceptance_ubuntu_browser.py`. A verificação guest usa somente runtime instalado;
o helper não altera módulos, SQL, configuração do produto ou serviços.

O primeiro roteiro de navegador escolheu porta local 28083 para o túnel e
recebeu `HOST_DENIED`, conforme a proteção Host/Origin do produto. Evidência
preservada em `browser-tunnel-host-denied.json`/`.png`. O roteiro foi corrigido
para manter o endereço oficial `127.0.0.1:18080`, sem mudar a instalação ou
enfraquecer a proteção. As verificações então passaram. As capturas de painel
mostram a configuração retomada; nenhuma captura de segredo/TOTP foi publicada.

## Encerramento e Windows

Ubuntu encerrado por `sudo shutdown -h now` após a aprovação. Disco atual e
ambos os snapshots preservados. Inventário final: **zero VMs em execução**.

[Medição de RAM](windows-memory-gate.json): 5115 MiB livres de 16215 MiB;
Windows requer 4096 MiB mais reserva padrão do host de 2048 MiB, total 6144 MiB.
**Windows não iniciado.** A VM existente em `.native-test/clean-os/windows11/`
tem disco novo e ISO Windows 11 Enterprise Evaluation; o sistema operacional
ainda não foi instalado. Não foi reduzida a reserva nem encerrado outro
processo/VM do usuário para forçar o avanço. Liberar ao menos cerca de 1 GiB
adicional e medir novamente antes de iniciar somente essa VM.

A candidata 3 está aprovada exclusivamente para este ensaio Ubuntu. Windows
limpo, experiência gráfica de entrega do grant Ubuntu e sensores físicos
não são homologados por estes resultados.
