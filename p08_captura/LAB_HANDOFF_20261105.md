# Laboratório P08 → detecção → P11: bloqueio verificável

Branch isolada existente `feat/p08-evidence-coverage`, início limpo `a59a8c0`.
Composição consultada somente em leitura: `f719188`, descendente de `7fe8294` e
`4c30d59`. Reutilizada a implementação dessa linha; nenhum cherry-pick, treino ou
reescrita de `backend/p08_p09`. Main permaneceu `9d58e69`. Nenhum acesso à VM
operacional nesta rodada. Recibos anteriores permanecem datados, sem atualização
artificial de sua validade. O aceite PostgreSQL/visual da mensagem terminada em
`a8395129f67e9b` é preservado; não houve republicação.

## Resultado do ensaio solicitado

**BLOCKED antes da captura:** falta recibo de ferramenta/link type/permissão no
Poste2/ens33. Não existe nova sessão real assinada disponível nesta entrega;
features observadas ficam desconhecidas, sem vetor de zeros. A janela de 120 s
não foi iniciada: faltam também fontes/fronteiras, relógios e início UTC combinado.
Nenhum dado sintético foi contado como laboratório; não houve inferência ou
escrita P11. O caminho `process_p08` reutilizado de `7fe8294` continua bloqueando
inferência mesmo com cobertura assinada. A liberação desse gate pertence à
composição e não foi simulada nem implementada nesta frente.

Leituras locais às `2026-11-05T14:30:45.1438446Z`: Mosquitto Running,
**W32Time Stopped**, consultas status/peers retornam `0x80070426`. VMnet8 confirmada
UP, ifIndex17, por leitura fora do sandbox. Configuração consultada mantém apenas
`listener 1883 192.168.155.1` entre as diretivas listener/log/include pesquisadas;
nenhum `*.log` retornou na pasta `D:/Programas/Mosquitto`. Isso não prova ausência
global de logs. Não se iniciou serviço nem se alterou configuração.

Docker: tanto a tentativa no sandbox quanto fora dele falharam; fora, pipe
`dockerDesktopLinuxEngine` inexistente. `py -0p` não encontrou instalação no
contexto atual; o caminho Python313 do PATH também não foi executável. Logo o
auditor Python existente não foi executado nesta rodada e os testes históricos
não são apresentados como testes novos. Não se iniciou Docker Desktop nem VM.

## Comparação concreta com RF/IF

`LAB_INVENTORY_20261105.json` foi gerado lendo fontes e os oito metadados/bundles
locais preservados de quatro execuções da composição. Nenhum joblib foi carregado.
Os hashes de arquivos correspondem aos declarados nos metadados, sem afirmar pin
externo confiável. Todos usam `demo_tcp_ingress`, nove colunas na ordem abaixo,
10 s, versões Python3.12.15/sklearn1.8.0/scipy1.17.0/numpy2.3.5/pandas2.2.3/joblib1.5.3.
RF artifact_version1; IF2. São estimadores ajustados com dados sintéticos segundo
a procedência da composição. Não renomear perfil nem apresentá-los como operacionais.

| Ordem | Nome | Tipo P08 → RF/IF | Unidade/origem |
|---|---|---|---|
|1|packet_count|int → float32|pacotes TCP selecionados|
|2|bytes_total|int → float32|soma IPv4.total_length, sem Ethernet|
|3|packets_per_second|float → float32|pacotes / 10 s|
|4|connections_per_second|float → float32|pares de portas distintos com SYN sem ACK / 10 s|
|5|syn_count|int → float32|SYN sem ACK, incluindo retransmissões|
|6|rst_count|int → float32|pacotes RST|
|7|unique_dst_ports|int → float32|cardinalidade de portas destino|
|8|avg_packet_size|float → float32|bytes IP / pacotes|
|9|mean_interarrival_ms|float → float32|diferença último−primeiro ×1000/(n−1)|

Contrato `harpisense.if.window.v1`, buckets UTC alinhados de 10 s, [início,fim),
sensor/origem/destino, destino=broker. Float32 é a transformação do validador
oficial na ordem de metadata.features. Tipos acima são derivados do código,
**não medidos numa janela nova**. Interarrival=0 somente para n≤1 observado.
Ausências opcionais permanecem ausentes; broker/consumidor/API não são extraíveis
do PCAP. Perfil P08 `tcp-observacao` diverge dos oito bundles: incompatibilidade
de distribuição/proveniência, sem correção segura por renomeação.

O inventário compara byte a byte V2 com os arquivos da composição: agregador P08,
validador P09, RF e IF todos iguais. As referências `Versões corretas` continuam
válidas para componentes não substituídos; esta comparação usa os quatro
componentes efetivamente substituídos pela V2. Integrador legado não é alterado;
seu hash remoto é somente o recibo histórico `f1537b54...e5f06a5`.

## Cobertura e desbloqueio por fonte

| Fonte | Estado da nova sessão | Leitura necessária |
|---|---|---|
|captura endpoint Poste2/ens33|UNKNOWN|ferramenta, EN10MB, permissão; depois PCAP e perdas|
|broker Windows|UNKNOWN|destino real, geração/rotação, offsets inicial/final e exportação integral|
|consumidor MQTT|UNKNOWN|recibos antigos não são fronteiras novas; boot/cursores/exportação da janela|
|API/P11 leitura|UNKNOWN|mesmas fronteiras, retenção e intervalo integral|
|tempo entre hosts|UNKNOWN|fonte, offset/incerteza e estabilidade; Windows atualmente sem serviço NTP ativo|

Sensor viável: **Poste2/ens33**, endpoint do fluxo direto já descrito nos recibos.
Não presumir visibilidade na ens37. Menor mudança de rede necessária: nenhuma.
Reversão da futura coleta: encerrar só o processo da sessão nova pelo controle/PID
registrado, reter artefatos e marcar INCOMPLETE. Não tocar rota, firewall ou
checkpoints. Se faltar privilégio, registrar a falha e revisar delegação mínima
com o responsável; não aplicar setcap/sudo/instalação automaticamente.

**Operador: executar no console já autenticado do Poste2**, sem publicar:

```sh
hostname
id
date -u '+%Y-%m-%dT%H:%M:%SZ'
ip -br link show ens33
ip -4 route get 192.168.155.1
command -v tcpdump
tcpdump --version
tcpdump -i ens33 -L
timedatectl show -p NTPSynchronized -p TimeUSec -p Timezone
cat /proc/sys/kernel/random/boot_id
```

A saída decide se o endpoint pode produzir PCAP clássico Ethernet com permissão
existente. `-L` não captura nem demonstra o conteúdo futuro. Enviar erro literal
se houver falha. Não iniciar `demo_poste2.sh`. O limite de erro temporal ainda
exige referência e incerteza do dono dos relógios, além desse status.

**Dono do broker: PowerShell na máquina Windows do Mosquitto**, somente leitura:

```powershell
Get-Date -AsUTC -Format o
Get-Service W32Time,mosquitto
w32tm /query /status /verbose
w32tm /query /peers
Select-String -Path 'D:/Programas/Mosquitto/mosquitto.conf' -Pattern '^\s*(log_dest|log_type|log_timestamp|log_timestamp_format|include_dir)\b'
Get-ChildItem 'D:/Programas/Mosquitto' -File -Filter '*.log' | Select-Object Name,Length,LastWriteTimeUtc
```

Decisão: há sincronismo e um destino exportável? Se log estiver fora dessa pasta,
o dono precisa informar o caminho efetivo e método de geração/offset/rotação,
sem fornecer credenciais. Não pedir nem executar resync/reinício por conta própria.
Não consultar HarpiServer nesta rodada por restrição à VM operacional. Os comandos
de journal já constam de `ENCAMINHAMENTO_SENSOR_POSTE2_20261104.md`; só produzir
fronteiras novas no ambiente isolado acordado, antes/depois da futura coleta.

## Reprodução local

Na raiz da worktree P08, com destino novo:

```powershell
./p08_captura/inventariar_laboratorio.ps1 -RepositoryRoot 'D:/Projetos/tcc - harpisense' -CompositionRoot 'D:/Projetos/tcc - harpisense/harpisense-worktrees/detection-composition' -OutputPath './p08_captura/LAB_INVENTORY_novo.json'
```

Esse comando foi executado com sucesso; quatro comparações byte_equal=True e
oito bundles inventariados. Não é auditoria numérica. Recusa sobrescrita e falha
se git rev-parse falhar; safe.directory é restrito à chamada, sem mudar config.

Quando Docker estiver disponível, na worktree **da composição**, executar seu
auditor existente sem modificar o código; saída nova somente na worktree P08:

```powershell
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,nosuid,nodev,size=128m -e PYTHONDONTWRITEBYTECODE=1 -v "${PWD}:/work:ro" -v 'D:/Projetos/tcc - harpisense/harpisense-worktrees/p08-evidence-coverage/p08_captura:/out' harpisense-detection:integration python -B -m p08_p09.compatibility_audit --profile docs/evidence/p08-compatibility-20261105/observation-plan.json --output /out/LAB_AUDIT_novo.json
```

É esperado código2/BLOCKED sem sessão. Com uma sessão real, acrescentar PCAP,
sessão, perfil aprovado e bundles de fontes, conforme COMPATIBILITY.md existente;
pins RF/IF devem vir de origem confiável. O plano rascunho não é perfil aprovado.
Não executar composição sintética para substituir a falta de captura real.

## Repasse

`maestri list` identifica este terminal como o próprio `HarpiSense Arquiteto`.
Tentativa de coordenação falhou com `No connection ... Connect terminals first`;
`maestri debug` comprovou transporte/list funcionando. Nenhuma janela foi acordada
pela falha. Este arquivo, o JSON e o commit constituem repasse local: branch
`feat/p08-evidence-coverage`, contrato `harpisense.if.window.v1`, primeiro bloqueio
console Poste2/ens33. O hash final será informado na mensagem de entrega.
