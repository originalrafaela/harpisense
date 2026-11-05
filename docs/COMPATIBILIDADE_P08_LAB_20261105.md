# Contrato concreto para a próxima coleta legítima

Continuação de `7fe8294` em `feat/detection-composition`, sem repetir treino ou
inferência sintética. Referências: P08/P09 V2 e componentes preservados de
`Versões corretas`; nenhuma ausência é inferida só pela estrutura da V2.
Este documento complementa a única matriz em `COMPOSICAO_NUCLEO_20261104.md`.

## O que foi conferido tecnicamente

Foram copiados em leitura os três fontes usados pelo integrador instalado na VM.
O integrador permanece com SHA256 `f1537b54...e5f06a5`; o conversor
`6a923456...b9b10152` usa `IPv4.total_length`; o agregador
`5f92f109...8d080be` é byte a byte igual ao P08 V2. Hashes completos e origens estão
em `backend/p08_p09/compatibility_sources/ORIGINS.json`. Não houve alteração remota.

O código instalado produz as mesmas nove features que o P09: isso foi comparado
numericamente nos novos testes de contrato, com o mesmo conjunto de pacotes
offline declarado como fixture. **Não houve sessão/PCAP novo de laboratório**, e
os modelos operacionais continuam sem diretórios/pins apresentados. Portanto,
compatibilidade com um artefato operacional concreto ainda é NOT_VERIFIED.

## Features e pré-processamento para a Edge

| Ordem padrão | Nome | Tipo produzido pelo P08 | Unidade/cálculo efetivo | Fonte necessária |
|---|---|---|---|---|
| 1 | packet_count | int | pacotes TCP selecionados | pacote capturado |
| 2 | bytes_total | int | soma do total_length IPv4, sem Ethernet | IPv4 completo |
| 3 | packets_per_second | float | packet_count / 10 s | contagem + janela |
| 4 | connections_per_second | float | pares (porta origem,destino) distintos com SYN sem ACK / 10 s | cabeçalho TCP; tentativas estimadas, não conexões estabelecidas |
| 5 | syn_count | int | pacotes SYN sem ACK; retransmissão conta como pacote | flags TCP |
| 6 | rst_count | int | pacotes com RST | flags TCP |
| 7 | unique_dst_ports | int | cardinalidade das portas destino | porta TCP destino |
| 8 | avg_packet_size | float | bytes_total / packet_count, bytes IP | mesma população de pacotes |
| 9 | mean_interarrival_ms | float | (último−primeiro timestamp) ×1000/(n−1); 0 só quando n≤1 observado | timestamps dos pacotes, ms |

A ordem **do bundle** é a autoridade; a tabela mostra o default canônico. O P09
exige também todas as nove features base, mesmo quando o modelo seleciona um
subconjunto. A seleção usa nomes na ordem de `metadata.features` e converte para
float32 pelo validador oficial. Contagens devem ser inteiras; rejeitar booleanos,
NaN/infinito, negativos e fórmulas inconsistentes. Não completar ausências.

Agrupamento: sensor + IP origem + IP destino + bucket UTC de 10 s alinhado à época;
intervalos [início,fim). Selecionar uma interface e a direção destino=broker para
evitar dupla contagem de travessias. Preservar início/fim com fuso, sensor, sessão,
capture_interface, schema `harpisense.if.window.v1`, perfil e IDs. O ID Edge usa hash
legado diferente do preparador P09; o auditor verifica o legado e calcula alias v2
sem reescrever o original nem usar observation_id de cobertura como ID de features.

O conversor instalado aceita **PCAP clássico, Ethernet DLT_EN10MB=1, IPv4/TCP,
sem VLAN/fragmentação/truncamento**. Precisão ns é reduzida a microssegundos pelo
conversor existente. `any` pode gerar Linux cooked incompatível; PktMon/PCAPNG não
é entrada suportada. O exportador Scapy de outro pacote usa `len(bytes(packet))`:
não substituir o conversor instalado por essa saída L2 sem reconciliação explícita.
Não descartar registros rejeitados para declarar completude.

O filtro do controlador entregue é TCP entre os dois IPs, com snaplen integral.
Não acrescentar restrição `port 1883` silenciosamente: isso pode alterar população,
packet_count/bytes/portas e a distribuição treinada, especialmente para C01.
O ensaio legítimo proposto usa MQTT1883, mas filtro/perfil devem coincidir com o
pré-processamento de treinamento. Nenhum filtro foi modificado nesta rodada.

O integrador instalado usa `tcp-observacao`, 10 s e flags
collection_complete=False/logs_complete=False. Bundles de `7fe8294` usam
`demo_tcp_ingress` e treinamento artificial; **não renomear o perfil** nem usá-los
como homologação. Para cada RF/IF operacional ainda faltam diretório confiável,
SHA256 fixado, metadata/features/perfil/janela/versões e proveniência do
treino/calibração. Unidades/posição de captura precisam ser confirmadas também no
pré-processamento dos dados de treino; nomes iguais não bastam. RF calibrado,
score operacional IF e risco permanecem resultados distintos.

## Fontes que um PCAP não substitui

O perfil mantém captura, broker, consumidor MQTT e API como fontes obrigatórias.
Não retirar fonte para obter PASS. PostgreSQL e recibo do publicador servem à
correlação da mensagem, sem virar cursor global ou feature de log.

Features opcionais só existem quando exigidas pelo bundle **e** produzidas com
vínculo e cobertura: auth_failures/auth_successes e mqtt_acl_denials (broker),
api_auth_failures (API), telemetry_identifier_conflicts/telemetry_stale_count
(consumidor). O mapeamento entregue não implementa connection_failures,
admin_auth_failures ou mqtt_publish_count. Logs de falha de validação/duplicidade
isolados não equivalem automaticamente a essas contagens. Até as features com
mapeamento ficam bloqueadas pelo gate atual; ausência não é zero.

É necessário comprovar sessão/sensor/alvo, chaves públicas autenticadas, hashes e
assinaturas, boot/geração da fonte, cursores inicial/final e cadeia sem lacunas.
No broker Windows, identificar primeiro destino de log persistente e esquema real
de offsets/rotação; não inventar journal_cursor Linux. No journal, obter fronteiras
globais antes/depois e depois filtrar unidades, sem exigir sequência numérica sem
lacunas em um stream já filtrado. `NRestarts=0` ou uma conexão ESTAB não comprova
cobertura integral. O assinador existente recebe a declaração de continuidade do
operador: sua assinatura não cria a prova faltante.

Cobertura assinada COMPLETE também não certifica erro temporal entre hosts. Exigir
referência/offset/incerteza e estabilidade do Poste2, Windows e HarpiServer antes
das fronteiras; se houver salto ou associação ambígua junto ao bucket, bloquear o
vínculo. Não corrigir timestamps históricos subtraindo uma amostra de offset.

## Menor solução escolhida e dependência atual

**Observação:** Poste2/ens33 → broker192.168.155.1, sem mudança de rota/firewall.
Essa opção foi entregue à Edge, que a incorporou no encaminhamento
`ENCAMINHAMENTO_SENSOR_POSTE2_20261104.md`. O recibo de console ainda é necessário
para confirmar ferramenta, Ethernet, permissões existentes e relógio; SSH foi
recusado, sem troca de chaves ou autenticação. O pedido foi enviado ao usuário.

O nome `gateway_capture` é um identificador legado obrigatório do schema atual;
o plano declara host_id=poste2 e posição=endpoint. Isso **não comprova trânsito pelo
gateway**. O rascunho em `docs/evidence/p08-compatibility-20261105/observation-plan.json`
usa outro schema e chaves null para impedir uso como perfil de captura aprovado.

**Contenção futura:** requer outro desenho com o gateway efetivamente inline e
prova do percurso de ida/retorno sem bypass, preservando administração. Capturar
no publicador ou broker não fornece essa capacidade. Não é necessária mudança de
rede para a observação escolhida; nenhuma rota, forwarding, NAT ou regra foi
preparada para aplicação automática. Se esse desenho for solicitado, comandos
exatos e inversas serão apresentados após inventário e revisão, antes de aplicar.

A nova leitura Edge encontrou Windows W32Time não sincronizado, peer configurado
time.windows.com respondendo (amostras ~+0,397 s, sem limite de erro certificado),
broker sem destino persistente confirmado e journals legíveis com cursores, mas
sem fronteiras da futura janela. Essas são evidências do recibo da Edge, não
leituras repetidas pelo integrador. A menor próxima ação é o recibo do console
Poste2; paralelamente, dono Windows resolve sincronismo e log persistente com
procedimento revisado. Resincronização deve ocorrer antes da coleta; não reverter
relógio depois. Caso o broker precise de mudança, apresentar conf/diff, hash,
backup, impacto de reinício e restauração antes de executar. Sem esses insumos,
sessão vazia ou PCAP isolado não desbloqueiam o fluxo.

Após os pré-requisitos: definir perfil real assinado e início UTC, único publicador,
120 s após readiness, heartbeat1s, fronteiras externas cobrindo o intervalo efetivo
e até três mensagens legítimas novas dentro dele. Não repetir o ID já aceito.
Executar o auditor offline sobre PCAP/sessão/manifests e metadados reais antes de
propor a liberação do próximo estágio. M1/IDS, sem executor/ataques. Recuperação
da observação: interromper só o processo da sessão pelo PID/controle registrado,
reter PCAP/recibos e marcar INCOMPLETE; nenhuma rede a desfazer. O início não foi
marcado enquanto faltam os recibos e a disponibilidade dos donos das fontes.

## Código entregue ao responsável pela captura

`python -m p08_p09.compatibility_audit --help`: audita o plano agora e uma sessão
assinada depois; não executa captura/modelos. Reprodução e comandos completos em
`backend/p08_p09/COMPATIBILITY.md`. Oito testes novos verificam IP versus Ethernet,
SYN repetido, fórmulas P08/P09, ordem/dtype, perfis divergentes, features ausentes,
janelas parciais, VLAN, truncamento e formatos incompatíveis. Não foi repetida a
composição sintética anterior. Resultado atual executável: BLOCKED, com lista das
dependências em `docs/evidence/p08-compatibility-20261105/compatibility.json`.

Propriedade confirmada por `d6a2380`: Edge edita `p08_captura/`; composição edita
`backend/p08_p09/` na própria worktree. Não se alterou a worktree Edge. Maestri
foi usado para entregar os hashes/contrato e colher o encaminhamento; a Edge ainda
relata falha no caminho de resposta ao arquiteto. Este documento e o commit são o
repasse manual utilizável, sem repetição de mensagens ao próprio terminal.
