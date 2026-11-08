# Inventário segurança: captura, preparação, Policy e executor

Somente levantamento e fixtures isoladas. Sem captura real, contenção, alterações de VM/rede/serviço ou duplicação de ActionReview (`e5ce471`). Os hashes observados estão em `inventory-observed.json`; hash de fonte não é hash de binário instalado nem atesta licença de redistribuição.

| Função | Entrada interna existente | Dependências e status Windows | Dependências e status Ubuntu 24.04 x64 | Lacuna produto |
|---|---|---|---|---|
| Captura ao vivo | `edge.capture.scapy_gateway.run_capture`; CLI `python -m edge.capture.scapy_gateway` apenas desenvolvimento | Scapy declarado `>=2.5,<3`, driver Npcap; versão/binário/hash/licença de redistribuição e instalação pelo produto não definidos | Scapy, acesso a captura de pacotes e filtro BPF; libpcap/modo de socket a fixar e validar. Não presumir acesso sob usuário `harpisense` | Não coletado por builders atuais; sem serviço, seleção de interfaces na UI, readiness/drop counters/rotação/flush periódico testados |
| PCAP → eventos/janelas | `edge.capture.offline_pcap`, `packet_to_observation`, `WindowAggregator` | Scapy para leitura PCAP; parser/agregador em Python | Mesmo código; leitura de arquivo não equivale a captura privilegiada | Só CLI/export JSONL. Falta importação suportada no produto, metadados/ID/sessão e leitura UI/PG |
| Parser MQTT | `edge.capture.events.parse_mqtt_from_tcp_payload` | Sem descriptografar TLS; só bytes MQTT visíveis | Mesmo limite | Não transformar tráfego TLS em tópico/autenticação inferidos. Broker TLS local 8883 difere do filtro 1883 padrão |
| Ingestão de eventos | `edge.capture.backend_client.BackendClient.post_network_event` | Biblioteca padrão urllib/Basic com credencial técnica separada; somente 202 confirma entrega | Mesmo contrato | Endpoint legado `/api/v1/ingest/network-events` precisa ser integrado explicitamente à API nativa, sem usar sessão humana nem supor compatibilidade com P11 ingest |
| Preparação RF/IF | Eventos brutos/janelas separados, travessia conforme interfaces realmente observadas | Modelos/transforms/features/locks do Backend, sem classificação inventada pela captura | Mesmo contrato | Confirmar adaptação de schema/versionamento ao produtor canônico; NAT pode mudar chave de fluxo e impedir vínculo |
| Risk/Policy | `harpisense_engines.decide/preflight` | Python/contratos/catálogo compartilhados; independente de Docker | Mesmo código | Gatilhos/evidência/target/scope/freshness/executor não vêm da LLM nem de formulário sem autoridade |
| Aprovação específica | `delivery.action_review.ActionReview.approve` | psycopg/PostgreSQL já incluídos na base; sem biblioteca/serviço novos | Mesmo código, migração 006 no provision desta branch | Hook interno testado; falta resolver exato e autenticado/rotas/projeções/UI. Não reenviar como implementação duplicada |
| Execução simulada | `ActionReview.simulate`, `delivery.simulation` | Sem driver/firewall; nenhum adaptador REAL registrado | Mesmo limite | Simulated e mitigation_confirmed=false; não comprova aplicação ou verificação no SO |
| Execução/verificação REAL | Nenhum adaptador integrado no runtime nativo; referências externas apenas inspecionadas como texto/AST | Primitiva real Windows, privilégios, isolamento/escopo, TTL/reversão e verificador ainda não definidos no pacote | Adaptador Linux e integração com regras/broker/autorização, escopo, TTL/reversão/verificador ainda não definidos no pacote | `containment=not_available`, executor não configurado. Não inventar sucesso; não instalar regras no host para produzir evidência |

## Limites observados diretamente no código

- `run_capture` mantém observações em memória e só chama `flush_events` depois de `sniff` retornar. Com duração padrão ilimitada, prontidão do serviço não comprova eventos persistidos periodicamente; revisar antes de registrar autostart de captura.
- `backend_client` recusa `network_window`; janela offline não deve ser enviada como `network_event`. Entrega HTTP/PG/consulta UI devem ser demonstradas separadamente.
- `aggregation.traversal_verified` exige observação nas interfaces esperadas; configuração de duas interfaces não prova travessia. Uma amostra em arquivo não prova gateway, sensor ou rede operacional.
- MQTT CONNECT/PUBLISH visíveis não comprovam sucesso de autenticação, autorização ou falhas no broker. Autenticação desconhecida permanece unknown/null, não zero.
- O serviço nativo atual opera sem evidência de captura/executor: status não verificado/indisponível deve ser explícito. Instalação nova sem incidente, com consumidores saudáveis e cobertura declarada, pode ser saudável sem defesa liberada.

## Dependências externas verificadas e pendentes de fixação

A [documentação oficial de instalação Scapy](https://scapy.readthedocs.io/en/stable/installation.html) informa Npcap no Windows e suporte nativo Linux sem libpcap; isso não determina automaticamente o caminho de filtro BPF deste produto. A [documentação oficial de uso Scapy](https://scapy.readthedocs.io/en/stable/usage.html) distingue sockets nativos e libpcap. Por isso Ubuntu precisa de escolha explícita/teste do backend de captura, filtro e permissões mínimas no serviço; não marcar libpcap universalmente obrigatório nem presumir que Scapy sozinho resolva Windows.

Antes do empacotamento, Configurações deve fixar Scapy e transitivas com hashes por SO, driver/binários assinados e licenças/notices; registrar redistribuição Npcap como **não verificada** até obter artefato/política aplicável. Não foi baixado ou instalado driver nesta revisão. Nenhum requisito ao usuário final pode ser convertido em instalação manual de Npcap/tcpdump/Python ou concessão manual de privilégios.

Não substituir a arquitetura atual por iptables/nftables/Windows Firewall por inferência. Referências `defense_executor.py` e `execution_manager.py` fora do pacote são material de comparação, não adaptadores homologados. Inventário de imports/hash dessas referências não significa execução ou inclusão nativa.

## Artefatos e modelos

O coletor calcula hashes dos dois instaladores existentes, quando presentes; ambos permanecem **não verificados como offline completos**. Não foram gerados artefatos novos. `genai/artifacts.lock.json` declara runtime BitNet revisão `0b341e582afbf9e1011f24744b554c96a3477eb5`, submódulo llama.cpp `390c307752ab78fd8189f359d6954c9ba1be74af`, patch local e pesos `ggml-model-i2_s.gguf`, 1.187.801.280 bytes, SHA-256 `4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162`, licença MIT declarada pelo lock. São valores **esperados**, não verificação da presença dos pesos ou binários Windows/Ubuntu no payload.

RF/IF, preparação, referências e locks científicos permanecem sob ownership Backend; nenhuma versão foi inventada. Geração BitNet real não pode ser substituída por texto determinístico e não altera Policy, auditoria ou origem dos registros.

## Máquina e rede

`inventory-observed.json` registra somente campos permitidos dos VMX e resultado de `vmrun list` filtrado para os alvos. NAT no VMX não é evidência offline. Sem login guest, snapshot limpo/rede offline/ausência de checkout/Docker/serviços pós-reboot continuam não verificados. Os VMX de candidata 3/reteste histórico estão marcados protegidos, não são candidatos à reinstalação nesta revisão.

Nenhuma rota/interface/firewall do host foi alterada. Nenhuma VM foi ligada/desligada/reiniciada. Kali e demais máquinas de laboratório não foram operadas.
