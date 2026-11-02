# Captura e contenção — candidata para revisão

Delta da retomada recebido do arquiteto em 02/11: endereços/índices Windows reafirmados às 18:43 UTC reportadas; Mosquitto parado/1883 sem entradas às 17:17 UTC reportadas. `w32tm` indica não sincronizado, fonte `Local CMOS Clock`: correlação temporal entre fontes permanece sem aceite. SSH reconhece host e aceita chave pública Maestri, mas assinatura local não conclui, com agente Windows parado; nenhuma leitura remota obtida. Detalhes e leituras incrementais em `RETOMADA_ROTAS_2026-11-02.md`. Não houve alteração de rede, serviço ou captura.

Atualização de 02/11: ver `RETOMADA_ROTAS_2026-11-02.md` e o recibo Windows associado. Mosquitto estava **Stopped**, sem endpoints TCP locais 1883 na consulta bem-sucedida. O estado de 31/10 abaixo é histórico. Rotas das VMs ainda não obtidas por falta de autenticação SSH; proposta roteada não confirmada, comandos mutantes/inversos ainda não fechados. Nenhum serviço foi iniciado.

Base: `feat/p08-evidence-coverage`, `1cf058e1b1ffbf08a954d56ee082759be2eae49e`. Esta entrega acrescenta documentação e perfil; não refaz o coletor. Nenhuma operação nas VMs, captura, ataque, checkpoint, inferência ou IPS foi executada. Os 81 testes Linux isolados pertencem à base, conforme `LINUX_VALIDATION_RESULTS.json`; não comprovam implantação, cobertura ou contenção.

## Evidência reutilizada e lacuna decisiva

Prioridade às entregas em `referencias/versão_v2`: P02 (`PENDENCIAS_E_IMPACTOS_v2.md`), P05/P06, P08 (`LIMITACOES_DE_VISIBILIDADE.md`, mapa de fontes e identidades), P09 e P10 (`README.md`: protótipo fail-closed, não instalar automaticamente). Componentes preservados e pacotes de `referencias/Versões corretas` continuam válidos quando não substituídos, incluindo RF/IF, inventário e nftables legado. Presença de pacote não prova implantação.

O procedimento de 31/10 nesta pasta e a inspeção `../frontend-backend-autonomia/docs/INSPECAO_PERCURSO_POSTE2_20261031.md` (relativa à worktree) registram broker Windows `192.168.155.1:1883` na VMnet8, HarpiServer `ens33=192.168.155.144/24`, `ens37=10.20.30.1/24`, rota ao broker pela ens33, forwarding IPv4 0 e consumidor conectado pela ens33. Conferência documental em 01/11, sem nova leitura remota: são observações datadas, não configuração fixa. A nota antiga de testes pendentes foi superada pelos 81 testes da base publicada; a implantação permanece não comprovada.

Poste 2 `.142` é histórico. Faltam rotas atuais do produtor e retorno do Windows, regras de seleção de rota e associação NIC/MAC/VMnet. Não é possível fechar endereços, comandos de mudança e ausência de desvio sem essas evidências. ESP32-WROOM-32: faltam AP/sub-rede/gateway, destino MQTT efetivo e eventual intermediário/proxy/VPN. O pedido exato está em `PEDIDO_EVIDENCIAS_ARQUITETO.md`.

## Pontos e limites

| Ponto | O que pode observar | Onde poderia conter, após homologação | Invisível/limite |
|---|---|---|---|
| ens33 atual | conexões do HarpiServer ao broker, inclusive consumidor | INPUT/OUTPUT para tráfego local; FORWARD somente trânsito demonstrado | não vê automaticamente unicast Poste 2 → Windows, nem outros pares da VMnet8 |
| ens37 atual | tráfego destinado ao gateway nesse segmento; trânsito somente se realmente roteado | INPUT local; FORWARD apenas se encaminhado | sessão histórica Poste 2 → gateway não prova percurso MQTT |
| Windows broker | conexões que chegam ao listener; logs de autenticação/tópicos conforme configuração | firewall local e ACL MQTT, com escopos diferentes | não observa outros destinos; ACL não equivale a descarte IP; TLS oculta payload no PCAP |
| espelho de switch/vSwitch | somente portas/direções efetivamente espelhadas | nenhum bloqueio pelo sensor passivo | perda no espelho e segmentos excluídos; promiscuidade sozinha não cria espelho |
| AP/intermediário ESP32 | trecho Wi-Fi ou túnel realmente terminado ali | depende de roteamento/firewall do equipamento | VPN externa pode ocultar MQTT; proxy/NAT pode agregar dispositivos |

Broker → consumidor é outra conexão TCP. Interrompê-la não prova conter a publicação do Poste 2. Tráfego local não usa FORWARD. Caminhos IPv6, bridge e túneis precisam análise própria; não declarar cobertura com filtro IPv4/TCP atual.

## Alternativas mínimas

| Alternativa | Impacto e compatibilidade | Decisão |
|---|---|---|
| manter caminho e observar no broker | menor mudança de rede; controle local Windows/ACL exige aplicador homologado; coletor Linux não captura NIC Windows diretamente | boa opção imediata de evidência de aplicação, insuficiente para demonstrar defesa no gateway; importação PCAP Windows não homologada |
| espelhar para sensor Linux | preserva caminho dos produtores, depende de suporte VMware/AP e prova de entrega ao espelho | resolve observação, não contenção; insuficiente sozinha |
| encaminhar campo → HarpiServer → broker existente | reutiliza duas NICs e caminho FORWARD previsto pela arquitetura; exige ida/retorno e impedir desvio | **recomendada como candidata**, condicionada ao inventário e a uma janela futura autorizada |

Desenho recomendado: Poste 2 no segmento de campo → NIC interna do HarpiServer → NIC de saída → broker Windows existente. Preferir roteamento sem SNAT, preservando identidade IP, com rota específica de retorno no Windows. Os valores observados acima são candidatos a conferir, não comandos aprovados. Se retorno específico for inviável, avaliar SNAT separadamente: simplifica retorno mas agrega origem no broker, exige correlação pré-NAT e perde seletividade no bloqueio pelo broker. Não instalar bridge, mover broker ou criar proxy nesta proposta.

Poste 2: rota específica ao destino MQTT pelo gateway pode bastar, mas uma NIC direta VMnet8 manteria desvio potencial; sua restrição precisa ser projetada após inventário, preservando administração. Não mudar gateway padrão por conveniência. ESP32: conectar a AP cujo uplink de campo seja roteado pelo HarpiServer; ESP32 usa gateway do Wi-Fi, não ens37 diretamente. Se remoto, intermediário deve entregar rota ao segmento protegido pelo HarpiServer; proxy em host externo contornando-o não satisfaz a proposta. Um AP na LAN doméstica/VMnet8 não garante travessia. Se isso não for viável, ESP32 fica fora do escopo de contenção no gateway e requer controle no broker, explicitamente separado.

Broker: manter listener/credenciais/tópicos, prever somente retorno específico após revisão. Consumidor no HarpiServer continua conexão local pela saída; não misturar seus pacotes com publisher. Administração: preservar acesso atual por canal identificado, loopback da API/DB e sessão de console fora do caminho experimental. Não bloquear IP de proxy compartilhado, sub-rede administrativa ou fluxo de retorno sem avaliar alcance. P10 não autoriza habilitar executor automaticamente.

## Perfil, fontes e aceite

`examples/lab-gateway-routed.profile.candidate.json` usa exatamente o contrato atual, com placeholders que impedem uso prematuro. Gerar um perfil por produtor/par/interface e caminho, não somar capturas das duas NICs em uma sessão. Selecionar NIC interna antes de eventual NAT; origem é o IP efetivamente visto ali. Não usar o IP do consumidor como origem do publisher. O filtro existente é TCP bidirecional do par, não restrito à porta 1883: documentar outros TCP do par e não declarar MQTT por porta presumida.

Fontes obrigatórias: PCAP do sensor correto, log do broker Windows, consumidor MQTT e API para o cenário fim a fim. `gateway_capture` é nome de contrato, não prova de localização. Cada fonte exige host/chave pública autenticados, fingerprint DER, UTC, intervalo completo, boot/geração, cursores/offsets e prova de retenção/rotação. Exportador Windows permanece pendente; sem continuidade comprovada, UNKNOWN/INCOMPLETE. Não retirar fonte para obter PASS. ESP32/proxy exige ainda registro sanitizado de identidade MQTT e tradução do caminho, preservando vínculo de mensagem sem confundir IP agregado com dispositivo.

Após autorização futura, correlacionar mensagem legítima do produtor com observação na NIC interna, conexão vista no broker, consumidor e API no mesmo intervalo. Registrar rota de ida/retorno e ausência de caminho alternativo. Só então declarar observação daquele fluxo. Capacidade de aplicação exige confirmar hook, par, interfaces e alcance; eficácia de contenção precisa ensaio separado autorizado, não realizado aqui. Integridade/assinatura e zero kernel drops não comprovam ausência de perdas fim a fim.

## Implantação e recuperação propostas

1. Receber inventário faltante; arquiteto fecha tabela de origem/destino/NIC/próximo salto/retorno e acesso administrativo, inclusive IPv6. Sem isso não produzir comandos mutantes com IPs supostos.
2. Obter snapshots/configurações e acesso por console; preparar plano exato de mudança e inversas, com rota/interface/regra identificadas, valor anterior e dono. Reservar janela e critérios de aborto: perda administrativa, consumidor indisponível, retorno assimétrico ou caminho diferente do perfil.
3. Em autorização separada, aplicar somente mudanças aprovadas de conectividade, uma por vez; verificar rotas e conexões existentes com os comandos do pedido. Forwarding habilitado sozinho não cria caminho nem defesa. Não executar nesta rodada.
4. Candidata P08 em diretório novo e imutável, conforme procedimento de 31/10, sem sincronização destrutiva. Comparar hashes instalados e manifesto. O wrapper usa **`/opt/harpisense/staging/p08-captura/integracao/integrar_p08.py`**: preservar bytes, permissões e dependências dessa VM. Não copiar integrador antigo dos pacotes, não instalar diretório inteiro e não usar instalador histórico de dois arquivos para a candidata completa. Divergência inesperada bloqueia substituição.
5. Perfil revisado e hashes/chaves fechados antes da coleta. O comando de orquestração já existe no procedimento de 31/10; continua reservado à rodada autorizada, em saídas novas, sem persistência/checkpoint. Gates de inferência e IPS permanecem falsos.
6. Recuperação futura: interromper somente processo experimental identificado, restaurar apenas arquivos efetivamente alterados usando backup da mesma aplicação; reverter mudanças de rede em ordem inversa pelo console e pelos identificadores registrados. Não dar flush em nftables, não apagar rotas em massa, não substituir configurações globais. Conservar PCAP/logs/recibos. Confirmar hashes do integrador legado e retorno de MQTT/administração. Não há mudança desta rodada a recuperar nas VMs.

Comandos de preservação/verificação, no HarpiServer, somente leitura (caminhos conferidos pelo operador):

```sh
stat /opt/harpisense/staging/p08-captura/integracao/integrar_p08.py
sha256sum /opt/harpisense/staging/p08-captura/integracao/integrar_p08.py
ip -br -4 addr
ip -4 rule show
ip -4 route show table all
sysctl net.ipv4.ip_forward
ss -nt
systemctl show harpisense-mqtt -p ActiveState -p MainPID -p NRestarts
```

Comandos de recuperação de código, **modelo para aplicação futura**, somente após confirmar os caminhos absolutos e hash do backup da mesma aplicação; nunca apontar CODE_DEST para integrador legado, logs ou configuração de rede:

```sh
# CODE_BACKUP, CODE_DEST e EXPECTED_BACKUP_SHA256 são definidos no recibo revisado.
sha256sum "$CODE_BACKUP"
printf '%s  %s\n' "$EXPECTED_BACKUP_SHA256" "$CODE_BACKUP" | sha256sum -c - &&
  cp --preserve=mode,timestamps -- "$CODE_BACKUP" "$CODE_DEST"
sha256sum "$CODE_DEST"
```

As inversas de rede concretas dependem da tabela ainda faltante; não há autorização implícita para executar este modelo. Validação desta entrega: JSON e revisão de diff/contrato, sem novos testes operacionais. Pedido ao arquiteto preparado, mas não transmitido: `maestri list` não encontrou agentes conectados neste terminal.
