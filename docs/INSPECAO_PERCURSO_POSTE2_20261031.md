# Inspeção do percurso Poste 2 — 31/10/2026

Inspeção somente de leitura, após solicitação do operador. Rede, rotas,
firewall, MQTT, P08/P09, modelos e serviços remotos não foram alterados.
Não houve captura, publicação MQTT, implantação ou migração nesta rodada.
Validação direta do login no navegador continua pendente: operador informou
painel aberto, mas o portal acessível ao agente permanecia no formulário às
04:27:07 UTC. Não foi lida senha nem token.

## Procedimento revisado

Fonte atual: `../p08-evidence-coverage/p08_captura/PROCEDIMENTO_ARQUITETO_2026-10-31.md`,
candidata sobre `c314ca5`, ainda local e não implantada. O roteiro antigo da
worktree `edge-security` não representa a autenticação administrativa vigente;
seus exemplos de consulta administrativa Basic não devem ser executados.

O procedimento atual distingue publisher → broker, broker → consumidor e
observação TCP histórica pela ens37. Não transforma telemetria persistida em
prova de travessia, nem libera coleta ou IPS por retorno zero de um comando.
Perfis MQTT NAT e ESP32 ainda contêm placeholders e não estão prontos para uso.
Testes Linux da candidata e exportação contínua de logs Windows permanecem
pendentes; assinatura sozinha não comprova continuidade.

## Estado observado

| Local | Evidência atual |
| --- | --- |
| HarpiServer / hostname gateway | ens33 UP `192.168.155.144/24`; ens37 UP `10.20.30.1/24`; Tailscale `100.66.89.7/32` |
| Rota padrão do gateway | via `192.168.155.2`, ens33 |
| Rota para broker | `192.168.155.1 dev ens33 src 192.168.155.144` |
| Encaminhamento | `net.ipv4.ip_forward = 0` |
| Consumidor MQTT | serviço `harpisense-mqtt` ativo, conexão `192.168.155.144:44201 → 192.168.155.1:1883` estabelecida |
| API P11 | serviço ativo, listener `127.0.0.1:8000` |
| PostgreSQL | listener `127.0.0.1:5432` |
| Firewall do gateway | unidade `harpisense-firewall` active/exited; isso não prova aplicação de regra a um fluxo específico |
| Windows broker | serviço Mosquitto Running; executável `D:\Programas\Mosquitto\mosquitto.exe run` |
| Listener broker | `192.168.155.1:1883`, PID 21748, interface VMware VMnet8 |
| Conexões broker na leitura | somente consumidor `.144:44201`; ausência de publisher persistente não prova ausência de publicações pontuais |
| Windows | VMnet8 `192.168.155.1`; VMnet1 `192.168.180.1`; Ethernet `192.168.1.5` |
| Poste 2 | endereço/rotas atuais ainda não autenticados; `.142` é referência histórica, não identidade confirmada nesta rodada |

Não houve listener MQTT identificado no HarpiServer. A leitura de arquivos não
acessou `/opt/harpisense/capturas`, protegido por permissões; essa limitação não
foi contornada e não foi interpretada como ausência de capturas.

Trecho confirmado: broker Windows ⇄ consumidor HarpiServer pela ens33.
Hipótese a conferir no Poste 2: publisher na VMnet8 → broker Windows diretamente,
sem passagem pela ens37. A conexão do consumidor não é a conexão do publisher.

## Comparação da candidata com a VM

Manifesto local `CANDIDATE_MANIFEST.json`: todos os hashes listados conferem.
Hashes atuais da VM foram lidos sem alterar os arquivos. Evidências locais em
`frontend/local-evidence/p08-vm-hashes-20261031.json` e
`frontend/local-evidence/p08-comparison-20261031.json`.

| Resultado | Arquivos |
| --- | --- |
| Idêntico | adaptador P09 `p08_artifact_validator.py` |
| Diferentes | P08 `capture_session_v4.py`, `monitorar_tcpdump_v1.py`, `diagnosticar_cobertura.py`, `integrar_p08_v2.py`, `orquestrar_p08_v4_experimental.py`, `validar_sessao.py`; P09 `p08_p09_pipeline.py` |
| Ausentes na VM | `audit_feature_contract.py`, `build_source_manifest.py`, `coverage_evidence.py` |
| Somente na VM nesta comparação | `integracao/integrar_p08.py`, dependência legada explicitamente reutilizada pela candidata |

Essa comparação prova diferença de bytes, não compatibilidade funcional.
Antes de qualquer implantação, revisar diffs, fechar pacote/hash inclusive dos
adaptadores, preservar o integrador legado, repetir testes Linux isolados e
definir staging/backup próprios. O instalador antigo de dois arquivos não instala
a nova candidata inteira. Nenhum arquivo deve ser sobrescrito com base apenas
no nome ou na versão declarada.

## Ajuste mínimo proposto antes de qualquer modificação

1. Para manter a telemetria funcional, nenhuma mudança de rede é indicada agora.
   Confirmar NIC/MAC/IP e rota do Poste 2 no console, destino MQTT e identidade
   sanitizada do publicador. Comandos solicitados: `hostname; id -un;
   ip -br -4 address; ip -4 route; ip -4 route get 192.168.155.1`.
2. Se o caminho NAT direto se confirmar, observar publisher → broker no Poste 2
   ou no Windows/VMnet8 com sensor compatível. Captura apenas de broker →
   consumidor na ens33 não representa o fluxo do publisher. Não assumir que a
   VM vê unicast entre outros dois hosts por compartilhar a mesma sub-rede.
3. Regras de defesa no endpoint podem atuar onde o fluxo termina; defesa de rede
   no broker/host depende da identidade realmente vista e do escopo aprovado.
   No gateway, INPUT protege serviços locais; FORWARD não controla o fluxo
   publisher → broker quando ele não atravessa o gateway. Não ativar IPS nesta
   inspeção nem confundir controle MQTT/aplicação com bloqueio de trânsito.
4. Se o objetivo exigir travessia pela ens37, será necessário um desenho separado
   de ida/retorno, conectividade e ponto de aplicação da defesa. Só propor rotas,
   forwarding ou NAT concretos após inventário do Poste 2 e das NICs VMware;
   apresentar impacto e reversão antes de executar. Não habilitar forwarding ou
   remapear o broker apenas para produzir uma captura.

Próximos dados necessários: login no portal observável e inventário atual do
Poste 2. Sem esses dados, validação do navegador e percurso fim a fim permanecem
pendentes. MFA e recuperação por e-mail continuam indisponíveis.
