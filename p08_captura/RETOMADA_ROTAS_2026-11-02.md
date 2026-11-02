# Leituras pendentes para fechar o percurso — 02/11

Continuidade de `d2ddbdc`; proposta e comparação anteriores reutilizadas, sem repetir diagnóstico. Referências V2 e componentes anteriores não substituídos de “Versões corretas” mantidos. Coletor, contratos, testes e integrador legado sem alterações.

## Delta obtido

Leitura local no Windows `ACER`, `2026-11-02T05:25:22Z`, registrada em `WINDOWS_NETWORK_READONLY_2026-11-02.json`: VMnet8 `192.168.155.1/24`, índice 17; VMnet1 `192.168.180.1/24`, índice 12; Ethernet `192.168.1.5/24`, índice 20, default via `192.168.1.1`. Não há rota específica `10.20.30.0/24` nessa tabela. Para uma origem nessa rede, a tabela disponível aponta ao default, não ao HarpiServer; fechar a seleção com `Find-NetRoute` após identificar a origem real. Para origem na VMnet8 há rota conectada, sem necessidade de retorno via HarpiServer. Isso não estabelece a rota do Poste 2.

Mosquitto **Stopped**, consulta TCP completa bem-sucedida sem endpoints locais 1883. A observação de listener/consumidor de 31/10 não representa disponibilidade atual. Nenhum start/restart efetuado; verificar com o arquiteto se esse é o processo/host destinado à próxima sessão, sem habilitá-lo nesta rodada.

SSH `harpiserver@192.168.155.144`, BatchMode, chave existente `harpiserver_ed25519`, host key estrita: conexão alcançou autenticação, recusada com `Permission denied (publickey,password)`. Nenhuma leitura remota foi obtida; não inferir estado das NICs/forwarding a partir desse resultado. `maestri list` identificou somente portais, sem arquiteto conectado. Solicitado ao usuário conectar o arquiteto ou indicar canal autorizado; nenhuma mensagem foi entregue a outro agente.

## Delta sanitizado recebido do arquiteto — retomada de 02/11

Relato recebido nesta conversa, sem nova execução ou leitura remota por esta entrega; não altera o recibo JSON das 05:25 UTC:

- SSH: host confere com `known_hosts`; servidor aceita a chave pública Maestri, mas a assinatura local não conclui e o `ssh-agent` Windows está parado. É uma tentativa distinta da anterior: não classificar este resultado como recusa da chave pelo servidor, nem como login concluído. Nenhuma leitura remota disponível. Não iniciar agente, trocar chaves ou relaxar verificação de host nesta rodada.
- Windows às 18:43 UTC: VMnet1 ifIndex12 `192.168.180.1`, VMnet8 ifIndex17 `192.168.155.1`, Ethernet ifIndex20 `192.168.1.5`. Endereços/índices coincidem com o recibo anterior; não foram relatadas novas máscaras, rotas ou seleção de retorno.
- `w32tm` informa relógio não sincronizado, fonte `Local CMOS Clock`. Os horários Windows são horários reportados, sem garantia de alinhamento UTC com as demais fontes, inclusive para comparar recibos desta rodada. Não inferir desvio numérico nem ordem entre hosts. Falta comprovar offset/última sincronização e limite de erro aceitável antes da correlação fim a fim; não ajustar relógio ou serviço agora.
- Às 17:17 UTC reportadas: Mosquitto `Stopped`, consulta 1883 sem entradas. Confirma o estado relatado naquele instante; não garante disponibilidade posterior ou ausência de broker em outra porta.

Leituras adicionais mínimas do Windows para a pendência temporal, sem sincronizar ou reconfigurar: `w32tm /query /status /verbose`, `w32tm /query /source`, `Get-Service W32Time` e `Get-Date -AsUTC` (PowerShell 7). Anexar somente estado, fonte, último sincronismo, erro/offset disponível e horário reportado, com operador/host; se offset confiável não estiver disponível, registrar desconhecido. Não executar `/resync`, `/config` ou start/restart. Uma comparação independente de relógios permanece requisito para aceite futuro; UTC formatado sozinho não prova sincronismo.

Os dois documentos de evidência foram referenciados pelo arquiteto no worktree `p08-evidence-coverage`, conforme relato; isso não acrescenta leituras das VMs. Pendências de percurso, integrador, Wi-Fi e continuidade de fontes abaixo permanecem. A proposta roteada segue sem confirmação e sem comandos mutantes/inversos concretos até as leituras decisivas. Nenhuma mudança de rede, captura ou checkpoint autorizada.

## HarpiServer — delta recebido de 2026-11-02T21:02:09Z

Evidência sanitizada informada pelo arquiteto nesta conversa; incorporada documentalmente, sem nova execução por esta entrega. SSH restabelecido, por canal administrativo Tailscale com verificação estrita preservada. Supera a pendência de autenticação das tentativas anteriores, que permanecem históricas.

| Leitura | Resultado informado |
|---|---|
| ens33 | UP, `192.168.155.144/24` |
| ens37 | UP, `10.20.30.1/24` |
| Rota default | via `192.168.155.2`, dev ens33 |
| Rede de campo | `10.20.30.0/24`, conectada, dev ens37 |
| `route get 192.168.155.1` | dev ens33, src `192.168.155.144` |
| `net.ipv4.ip_forward` | `0` |
| `NTPSynchronized` | `yes` |
| SHA256 do integrador legado | `f1537b54ba721153b3daf8a09a09ba1e7aef24aee4a513828302ca237e5f06a5`, preservado |
| Consumidor MQTT | `active`; `NRestarts` passou de 731 para 1266 entre leituras |

O contador cresceu 535; não foram fornecidos os dois instantes nem um intervalo suficiente para calcular taxa ou causa. O arquiteto informa condição preexistente e nenhum restart solicitado por ele; não atribuir a variação a esta rodada. `active` não comprova estabilidade, conexão ao broker ou continuidade do consumidor. Não corrigir MQTT, reiniciar serviços ou coletar tráfego nesta rodada. Para aceite futuro, continuidade do consumidor continua pendente de evidência por intervalo, sem repetir o diagnóstico operacional.

O indicador NTP do HarpiServer não resolve a pendência temporal do Windows nem fornece, isoladamente, limite numérico de erro entre fontes. A rota local ao broker não demonstra percurso do Poste 2. Forwarding IPv4 desabilitado impede confirmar o desenho candidato como gateway IPv4 encaminhando esse tráfego no estado relatado. Captura em ens33/ens37 continua sem visibilidade garantida de fluxos de terceiros.

Não repetir como pendentes as leituras de interfaces, default, rede conectada, rota local ao broker, forwarding, indicador NTP e hash acima. Permanecem Poste 2, retorno Windows para sua origem real, ESP32/AP e continuidade/tempo das fontes. MAC/VMnet, regras/tabelas completas, IPv6, `stat` do integrador e detalhes da rota administrativa não constam deste delta: se necessários ao plano exato, solicitar somente esses complementos. Preservar o canal Tailscale informado; comandos e inversas de implantação seguem sem fechamento por falta do percurso completo. Perfil parametrizado mantém placeholders; não preencher origem ou NIC do produtor com dados do consumidor/HarpiServer.

## Somente dados ainda necessários e comandos

**Poste 2**, console autenticado pelo arquiteto; registrar UTC e executar sem sudo:

```sh
date -u
hostname
ip -br link
ip -br -4 addr
ip -4 rule show
ip -4 route show table all
ip -4 route get 192.168.155.1
ip -6 route show table all
ss -nt
```

Anexar correspondência MAC/NIC → VMnet/modo e destino MQTT efetivo/porta/client_id/tópico sanitizados. Se o destino não for `.155.1`, obter `ip -4 route get` para o IPv4 realmente utilizado. Isso fecha dev/src/via e possíveis desvios, sem supor `.142`.

**HarpiServer**: o bloco abaixo é o roteiro anterior, parcialmente atendido pelo delta das 21:02:09Z. Não reexecutar os itens já atendidos; obter somente complementos necessários indicados acima, pelo canal estrito preservado:

```sh
date -u
hostname
ip -br link
ip -br -4 addr
ip -4 rule show
ip -4 route show table all
ip -4 route get 192.168.155.1
ip -6 route show table all
sysctl net.ipv4.ip_forward
ss -nt
stat /opt/harpisense/staging/p08-captura/integracao/integrar_p08.py
sha256sum /opt/harpisense/staging/p08-captura/integracao/integrar_p08.py
```

Informar canal administrativo, IP de origem do administrador, NIC/rota usada e disponibilidade de console fora do caminho experimental. Com esses IPs reais, obter `ip -4 route get <IP_ADMIN>`; se encaminhamento roteado for candidato, consultar também `ip -4 route get <BROKER_REAL> from <ORIGEM_POSTE2> iif <NIC_CAMPO_REAL>` e `ip -4 route get <ORIGEM_POSTE2>`. Os valores entre sinais são dados faltantes, não comandos executáveis como estão. Não ler conteúdo do integrador nem substituí-lo.

**Windows**, apenas retorno específico após a origem do Poste 2 ser conhecida:

```powershell
# Substituir pelo IP efetivamente selecionado no Poste 2; não pelo histórico .142.
Find-NetRoute -RemoteIPAddress <ORIGEM_REAL_POSTE2>
# Se a proposta mudar a origem para a rede de campo, repetir para essa origem candidata.
```

Confirmar com o arquiteto o broker/processo destinado ao ensaio e configuração sanitizada de bind/porta/log/rotação. Não repetir inventário geral do Windows. Para eventual futura janela autorizada, consultar novamente apenas `Get-Service mosquitto` e `Get-NetTCPConnection -LocalPort 1883` para comprovar disponibilidade naquele instante; esta entrega não autoriza iniciar o serviço.

**ESP32-WROOM-32**: obter AP e localização, sub-rede/IP/máscara/gateway/DNS atribuídos, uplink e VLAN/isolamento de clientes do AP, possibilidade de chegar ao segmento de campo, destino MQTT efetivo/porta e identidade sanitizada do firmware em uso. Ler configuração existente ou concessão DHCP do AP, sem instalar firmware, reiniciar ou iniciar monitor/coletor. Se houver intermediário Linux, usar `ip -br -4 addr`, `ip -4 rule show`, `ip -4 route show table all`, `ip -4 route get <BROKER_REAL>` e informar modo proxy/subnet-router/NAT/VPN e origem vista no broker. Sem intermediário, não pedir esse inventário. A interface Wi-Fi link-local do Windows não identifica a rede do ESP32.

**Fontes de cobertura**: continuam pendentes método de exportação íntegra por intervalo/rotação dos logs Mosquitto Windows, relógios UTC, identidade dos hosts e fingerprints públicos e fronteiras/cursores do consumidor/API. Usar configuração/logs existentes sanitizados; não criar exportador ou coleta operacional nesta rodada. Não solicitar novamente pacotes de referência já lidos.

## Decisão e perfil após essas leituras

A recomendação roteada permanece candidata, não confirmada: a tabela Windows atual não contém o retorno de campo necessário ao desenho sem SNAT. Sem origem/NIC de campo e canal administrativo reais não emitir `ip route`, `New-NetRoute`, sysctl mutante ou inversas com valores presumidos. As mudanças e suas inversas serão pares por objeto exato, preservando configuração anterior; nenhuma regra FORWARD pode conter caminho que contorne o gateway.

O perfil `examples/lab-gateway-routed.profile.candidate.json` identifica agora o host Windows observado como `ACER`; destino/interface/origem/identidade do sensor e chaves permanecem bloqueados por placeholders. `ACER` identifica host, não disponibilidade de listener nem prova criptográfica. Não transformar `.155.1` observado em destino MQTT validado sem configuração do produtor. Perfil separado por produtor; nenhuma sessão de ens33 pode representar automaticamente publisher → broker. Encaminhamento comprovado exige ida/retorno pela NIC correta; capacidade de defesa exige ponto de aplicação e escopo homologados separadamente.

Coleta controlada posterior somente após: destino e origem reais fechados; disponibilidade do broker naquele instante; perfil sem placeholders e autenticado; integrador legado preservado por hash; fonte PCAP no trecho demonstrado; broker/consumidor/API com continuidade comprovável; acesso administrativo e inversas revisados. As leituras de rota preparam a hipótese; confirmação por pacotes/mensagem legítima fica para a rodada de coleta autorizada. Inferência, IPS e persistência/checkpoints continuam desabilitados. Não executar captura para suprir a falta de leitura nesta rodada.

Verificação desta atualização: JSON legível, mesmos campos do contrato de perfil, placeholders mantidos e diff sem alterações em código. Os 81 testes Linux da base permanecem evidência isolada; não reexecutados nem apresentados como comprovação nas VMs. Não houve implantação a reverter.
