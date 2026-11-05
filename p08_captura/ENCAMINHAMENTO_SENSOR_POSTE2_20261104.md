# P08 — sensor mínimo e ações específicas para a próxima janela

Base desta rodada: `d6a2380d51c4c98558f5eb8679c1e9fd04967979`, worktree P08 preservada. Composição `7fe8294` consultada por `git show`, sem merge ou alteração de seus arquivos. A instrução mais recente restringe esta rodada a leituras/preparação: **não executar ensaio, publicação ou ataque**. `backend/p08_p09/` é exclusivo da composição; `p08_captura/` permanece com Edge/P08.

## Decisão de sensor e contrato recebido

Preferência técnica combinada na mensagem do arquiteto: **Poste2/ens33**, origem `192.168.155.142`, destino broker Windows `192.168.155.1:1883`. Capturar no endpoint do produtor não exige mudar rota, firewall, topologia ou broker; não depende de observar unicast entre terceiros em modo promíscuo. O `route get` do operador e retorno Windows direto VMnet8 já estão registrados em `d6a2380`; não repetir o inventário inteiro.

O sensor é viável pela posição na conexão, mas ainda depende do **recibo de console** de ferramenta, link type e permissão. SSH ao Poste2 foi recusado; isso não autoriza instalar chaves ou trocar autenticação. Não iniciar captura no gateway como substituto.

Compatibilidade recebida do arquiteto, **não uma nova medição executada por esta entrega**:

- Integrador legado SHA256 `f1537b54ba721153b3daf8a09a09ba1e7aef24aee4a513828302ca237e5f06a5`, já conferido tecnicamente na rodada anterior.
- `pcap_to_events.py` SHA256 `6a923456b580b15f0dafcc477192267dd35e355b603b52b732700b2ef9b10152`.
- Agregador SHA256 `5f92f1091dd8c381bd78dc234fccdf950dcffdc64a94d312bdbdd7bd68d080be`, idêntico ao P08 V2 segundo a comparação do arquiteto.
- Conversor aceita **PCAP clássico, link type Ethernet, sem VLAN, IPv4/TCP não fragmentado e sem truncamento**. Usa `IP.total_length`; não usar `len(bytes(packet))`/tamanho Ethernet como `bytes_total`. PCAPNG/PktMon não serve como entrada atual. Não criar conversor concorrente ao auditor do arquiteto.

Na captura futura, exigir interface `ens33`, não `any` (que pode produzir Linux cooked/SLL), snaplen integral e preservação do PCAP original. Não somar bytes L2 nem silenciosamente descartar VLAN/fragmentos/truncamento para passar o auditor. Filtro e ponto devem permitir ao auditor identificar condições não suportadas no fluxo selecionado. Link type/ausência dessas condições serão demonstrados no arquivo real; `tcpdump -L` sozinho não comprova conteúdo futuro.

## Ações mínimas por pendência

| Pendência | Ação mínima e resultado esperado | Responsável/limite |
|---|---|---|
| Sensor | Operador executa o bloco de console abaixo; confirmar tcpdump existente, EN10MB/ENET e permissão de leitura de ens33. Se não existir permissão/ferramenta, arquiteto revisa instalação/delegação mínima; não trocar rede. | Poste2, sem captura nesta rodada |
| Relógio Windows | Fonte atual time.windows.com responde ao stripchart, mas W32Time está não sincronizado. Solicitar resincronização pontual com o peer existente **antes** da sessão, após revisão operacional; não mudar peer, firewall ou rotas. Repetir status/stripchart e medir também referência do Poste2/HarpiServer; registrar erro/incerteza e estabilidade. | Operador Windows/arquitetura; nenhum ajuste executado aqui |
| Logs broker | Confirmar destino efetivo pela configuração/processo e arquivo/serviço de log. Não há log_dest explícito nem arquivo *.log na pasta consultada; isso não é prova de inexistência global. Se realmente não houver log persistente, arquiteto deve revisar habilitação de arquivo protegido com níveis suficientes antes da janela, backup do conf e interrupção/reconexão do broker. Não substituir log do broker por PUBACK ou log do consumidor. | Dono do Windows/Mosquitto; mudança não autorizada nesta rodada |
| Logs consumidor/API | Journals estão legíveis, unidades ativas e cursores presentes. Registrar fronteiras globais frescas e inventário por unidade na janela, conferir boot/PID/restarts, exportar intervalo integral e política de retenção/rotação. | HarpiServer, leitura sem checkpoint |
| Cursores/intervalo | Fronteira inicial antes de readiness; final depois do fim efetivo. Por arquivo, identidade/geração, offsets de bytes/linhas completos e rotação; por journal, boot e cursores reais. Exportar até o cursor final comprovado, depois filtrar unidades. Não exigir sequência numérica sem lacunas em um journal já filtrado por unidade. | Donos de cada fonte; assinar COMPLETE só com método comprovado |
| Janela | Arquiteto declara explicitamente início UTC, sensor, fontes, operador/publicador único e 120s efetivos após readiness. Fronteiras podem envolver margem, mas janelas de features ficam no intervalo efetivo. Bloquear execução enquanto faltar confirmação. | Sem ensaio nesta rodada |

## Comandos somente leitura — console Poste2

Executar no console autenticado já existente. Enviar saída sem credenciais; não iniciar `demo_poste2.sh`.

```sh
hostname
id
date -u '+%Y-%m-%dT%H:%M:%SZ'
ip -br link show ens33
ip -4 rule show
ip -4 route get 192.168.155.1
command -v tcpdump
tcpdump --version
command -v openssl
openssl version
python3 --version
timedatectl show -p NTPSynchronized -p TimeUSec -p Timezone
cat /proc/sys/kernel/random/boot_id
```

Para consultar **somente os link types**, sem capturar pacotes, usar a permissão já existente no console:

```sh
tcpdump -i ens33 -L
```

Se isso falhar por privilégio, registrar a falha. Não executar sudo interativo, instalar ferramenta, setcap ou modificar grupos para contornar. O arquiteto escolhe a delegação mínima. Em instalação padrão, o operador pode também consultar `getcap /usr/bin/tcpdump` se o comando existir; ajustar o caminho ao retorno real de `command -v`.

## Comandos somente leitura — Windows do broker

```powershell
Get-Date -AsUTC -Format o
Get-NetAdapter -Name 'VMware Network Adapter VMnet8' |
  Select-Object Name,InterfaceIndex,MacAddress,Status
Find-NetRoute -RemoteIPAddress 192.168.155.142
Get-NetTCPConnection -LocalPort 1883 |
  Select-Object LocalAddress,RemoteAddress,RemotePort,State
Get-Service W32Time,mosquitto
w32tm /query /status /verbose
w32tm /query /peers
w32tm /stripchart /computer:time.windows.com /dataonly /samples:3
Select-String -Path 'D:/Programas/Mosquitto/mosquitto.conf' `
  -Pattern '^\s*(listener|log_dest|log_type|log_timestamp|log_timestamp_format|include_dir)\b'
Get-ChildItem 'D:/Programas/Mosquitto' -File -Filter '*.log' |
  Select-Object Name,Length,LastWriteTimeUtc
Get-WinEvent -ListProvider '*mosquitto*' -ErrorAction SilentlyContinue |
  Select-Object Name
```

Não enviar password_file, Environment, senha MQTT ou token. A consulta não retorna todas as possíveis pastas de log: o dono deve localizar o destino real, se configurado em outro lugar.

Nova leitura em `2026-11-05T01:04:05.8023009Z`: VMnet8 UP, ifIndex17, MAC00-50-56-C0-00-08; W32Time e Mosquitto Running. PktMon status/list recusaram acesso ao driver mesmo fora do sandbox: falta privilégio administrativo do Windows. IfIndex17 não é automaticamente component-id do PktMon. Além dessa permissão, PCAPNG não é aceito pelo conversor atual; portanto **não escolher PktMon nesta sessão**. Isso evita instalar sensor Windows ou alterar rede só para esta entrega.

Stripchart em 04/11 22:06:02–22:06:06 no relógio Windows (05/11 01:06:02–01:06:06 UTC reportado), peer resolvido40.119.6.228:123: `+0.3965910s`, `+0.3967258s`, `+0.3980179s`. O peer respondeu; nenhuma sincronização foi executada. São amostras de offset, não limite certificado de erro nem sincronismo de todos os hosts. Usar `time.windows.com` configurado, não fixar o IP resolvido temporariamente. Não subtrair esse valor de timestamps históricos.

## Comandos somente leitura — HarpiServer e cursores

Pelo canal administrativo já existente, sem reiniciar serviços:

```sh
date -u '+%Y-%m-%dT%H:%M:%SZ'
cat /proc/sys/kernel/random/boot_id
timedatectl show -p NTPSynchronized
systemctl show harpisense-mqtt harpisense-p11 -p Id -p ActiveState -p MainPID -p NRestarts
journalctl -n 1 --no-pager -o json --output-fields=__CURSOR,__REALTIME_TIMESTAMP,_BOOT_ID
journalctl -u harpisense-mqtt -n 1 --no-pager -o json --output-fields=__CURSOR,__REALTIME_TIMESTAMP,_BOOT_ID
journalctl -u harpisense-p11 -n 1 --no-pager -o json --output-fields=__CURSOR,__REALTIME_TIMESTAMP,_BOOT_ID
journalctl --disk-usage
```

As leituras desta rodada às `2026-11-05T01:12:40Z` estão no recibo JSON ao lado. **Não são fronteiras da sessão futura.** O último evento de uma unidade pode ser anterior ao início: para provar término do intervalo, capturar também fronteira global, verificar retenção e exportar até o fim real, sem fabricar evento de heartbeat no log do serviço. Leitura de journal não avança checkpoints; nunca usar `--cursor-file` apontando ao checkpoint legado.

Broker: ao identificar o arquivo real, guardar file ID/geração e offsets inicial/final, garantir linhas completas e retenção de arquivos rotacionados. Se houver rotação/truncamento não rastreado, continuidade INCOMPLETE. Assinatura não corrige exportação parcial. Manifestos e bundles de todas as fontes permanecem necessários; nomes semelhantes e horários próximos não vinculam fonte à sessão.

## Recuperação e mudanças que não serão feitas

**Nenhuma mudança de rede é necessária para o sensor Poste2/ens33.** Gateway futuro de contenção é outro trabalho, exigindo prova de encaminhamento e ausência de desvio, plano de ida/retorno e administração preservada. Não adicionar rota via10.20.30.1, habilitar ip_forward, NAT ou regras; observar no broker ou publicador não torna o gateway inline.

Se o arquiteto aprovar sincronização futura, aplicar antes das fronteiras e verificar estabilidade; se houver salto durante a coleta futura, encerrar e marcar INCOMPLETE. Não "reverter relógio" para valor velho nem corrigir timestamps históricos. Configuração NTP existente é preservada; qualquer mudança posterior de peer deve ter export/backup e inversa revisados antes de executar.

Se logging persistente exigir mudança futura, manter cópia protegida e hash do mosquitto.conf, configuração exata nova, donos/ACLs e impacto de reinício revisados. Recuperação: restaurar bytes anteriores, reiniciar pelo procedimento aprovado e verificar reconexão/contadores; preservar todos os logs/recibos da falha. Não apresentar como mudança sem impacto. Nenhum comando mutante de rede, relógio ou serviço foi incluído ou executado nesta rodada.

## Requisitos das features para o auditor de composição

Conferidos diretamente em `7fe8294:backend/domain/harpisense_data/windows.py` e README da composição:

1. Ordem: packet_count, bytes_total, packets_per_second, connections_per_second, syn_count, rst_count, unique_dst_ports, avg_packet_size, mean_interarrival_ms. Schema harpisense.if.window.v1; janelas10s; bytes de camada IP conforme conversor verificado pelo arquiteto.
2. Metadados: window_id único, collection_session_id, feature_schema_version, window_seconds, traffic_profile; envelope com sensor_id e início/fim com fuso. Na composição consultada, perfil dos bundles sintéticos é `demo_tcp_ingress`; candidata P08 usa `tcp-observacao`. **Não renomear perfis** para passar no auditor; comparar metadados reais e semântica, reportar incompatibilidade.
3. Validar contagens inteiras, números finitos/não negativos, pps=packet_count/10, avg=bytes_total/packet_count, conexões coerentes com SYN, interarrival em ms. Fórmulas devem ser auditadas em amostra numérica do PCAP válido; não completar feature auxiliar ausente com zero.
4. Preservar RF/IF reais de7fe8294: estimadores reais ajustados/calibrados com dados sintéticos, não modelos operacionais homologados. Hashes, features, perfil, janela e versões dos bundles reais precisam acompanhar o auditor. Nenhum treinamento ou inferência executado nesta rodada.
5. `process_p08` de7fe8294 termina em DependencyBlocked mesmo com cobertura assinada: auditor offline não libera gate nem autoriza persistência/inferência operacional. Nenhuma janela nova foi produzida aqui. Coleta futura válida e compatibilidade estrutural não demonstram eficácia de detecção.

Referências: P08/P09 aprovados em `referencias/versão_v2`; pacotes anteriores de `Versões corretas` para partes não substituídas. A composição reutiliza código desses pacotes; não declarar ausente um módulo por não aparecer no diretório V2.

## Entrega ao arquiteto e próxima ação única

Aguardamos **somente o recibo de console Poste2 acima** para fechar acesso/ferramenta/link type/permissão; em paralelo, donos resolvem relógio e destino/exportação do broker. Depois definir chaves de fontes/perfil, limites temporais e janela explícita120s com publicador único. Uma nova mensagem futura receberá session_id e recibo próprios, sem repetir o ID históricoa8395129f67e9b. Nesta rodada, nenhuma publicação ou coleta.

Maestri ask para HarpiSense Arquiteto falhou com No connection, pois list identifica o próprio terminal com esse nome. Encaminhamento manual: enviar este documento, recibo JSON e commit ao arquiteto. Não interpretar a falha como janela autorizada.

## Adendo — auditor recebido em 4c30d599

Lidos diretamente por `git show` os documentos `docs/COMPATIBILIDADE_P08_LAB_20261105.md` e `backend/p08_p09/COMPATIBILITY.md` do commit `4c30d599b987af8b3e3d63c017ace6a30a3d695f`, sem importar ou editar a composição. O encaminhamento desta worktree já foi publicado em `cb5bbef5414293d5d743f3bf18843c6ff41f6404`, posterior ao rascunho `d6a2380` referenciado na composição.

O auditor reutilizável é `python -m p08_p09.compatibility_audit`, na worktree/ambiente da composição. Não copiá-lo para recriar contrato nesta pasta. Oito testes offline foram relatados na entrega da composição; não foram repetidos pela Edge, nem houve treino, inferência ou coleta. BLOCKED continua sendo resultado esperado até a apresentação de sessão/fontes e artefatos operacionais confiáveis.

**Filtro preservado:** TCP entre os dois IPs, sem restringir à porta1883. A seleção destino=broker e o agrupamento sensor+origem+destino, buckets UTC alinhados à época com intervalos [início,fim), devem coincidir com integrador/treino. Captura pode conter os dois sentidos; não somar fluxos inversos ao mesmo vetor nem alterar silenciosamente o filtro de captura. Tentativas de conexão são pares distintos (porta origem,destino) com SYN sem ACK; syn_count conta pacotes SYN sem ACK, incluindo retransmissões. A ordem do bundle é a autoridade, mantendo todas as nove features base necessárias ao validador.

O auditor calcula alias v2 sem reescrever window_id legado; observation_id de cobertura não substitui ID de features. `gateway_capture` é identificador legado da fonte, com host_id=poste2 e posição=endpoint no futuro perfil aprovado, não evidência de trânsito pelo gateway. PCAP clássico Ethernet, IPv4/TCP íntegro sem VLAN/fragmentação/truncamento, bytes IP e perfil original permanecem obrigatórios.

As quatro fontes captura/broker/consumidor/API continuam obrigatórias. Nenhum cursor desta preparação será avançado ou reutilizado como fronteira da sessão futura. Não liberar gate, restringir população para parecer compatível ou preencher opcionais ausentes. Não iniciar coleta antes do recibo console, relógios/limites temporais, logs broker, fronteiras e janela coordenada. Sem nova rodada operacional nesta entrega.
