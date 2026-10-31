# Encaminhamentos consolidados — 31/10/2026

Escopo: revisão e repasse manual. Nenhuma nova implementação, implantação,
migração, coleta, inferência, alteração de rota/firewall ou reparo de worktree.
Raiz local: `D:\Projetos\tcc - harpisense`.

## Ordem de continuidade e referências

1. Concluir aceite do navegador na sessão observável: login, telemetria,
   atualização automática, logout e retorno ao login por expiração. O operador
   confirmou abertura do painel; o portal Maestri continuava no formulário nesta
   inspeção, sem requisições autenticadas observadas. O recibo HTTP da VM não
   substitui esses testes de interface. MFA e recuperação por e-mail pendentes.
2. Receber NICs/rotas atuais do Poste 2 e fechar percurso publisher → broker.
3. Apresentar a proposta concreta de observação/contenção. Só depois deliberar
   sobre a próxima alteração mínima. Nenhuma alteração de rede está liberada.

Prioridade documental: entregas aprovadas de `referencias/versão_v2` (nome real
no disco; corresponde à pasta Versao_v2 citada pelo operador). Componentes sem
revisão continuam em `referencias/Versões corretas`; não são considerados ausentes.
Status de proposta dentro de um pacote V2 continua sendo proposta: precedência
da pasta não homologa automaticamente todos os seus contratos ou exemplos.

## Texto para repassar ao Edge Security

> Entrega recebida em `feat/p08-evidence-coverage`, commit
> `1cf058e1b1ffbf08a954d56ee082759be2eae49e`; publicação confirmada por
> `git ls-remote origin refs/heads/feat/p08-evidence-coverage` nesta rodada.
> Procedimento: `harpisense-worktrees/p08-evidence-coverage/p08_captura/PROCEDIMENTO_ARQUITETO_2026-10-31.md`.
> Manifesto conferido contra bytes Git do commit, conforme sua normalização LF.
> Registro `LINUX_VALIDATION_RESULTS.json`: 81 testes Linux isolados; esse
> resultado não comprova cobertura, passagem pela ens37, inferência ou bloqueio
> na rede real. Não repetir testes na VM operacional como substituição de aceite.
>
> Comparação remota atualizada salva em
> `docs/continuity/2026-10-31/p08-published-comparison.json` nesta worktree.
> Diferem da VM os seis arquivos de captura/validação P08 anteriormente apontados
> e, no adaptador P09, `p08_p09_pipeline.py`, `log_coverage_integration.py` e seu
> teste. `coverage_evidence.py`, `build_source_manifest.py` e
> `audit_feature_contract.py` não estão no staging P08 da VM. A comparação
> completa inclui os módulos idênticos e os arquivos legados exclusivos da VM.
> Não sobrescrever árvores nem usar o instalador antigo de dois arquivos para
> instalar este pacote. Preservar explicitamente
> `/opt/harpisense/staging/p08-captura/integracao/integrar_p08.py`, que é dependência
> reutilizada pelo wrapper candidato. Nenhum arquivo foi implantado.
>
> Aguardar inventário do Poste 2 e decisão de sensor por trecho. Não promover
> perfis com placeholders, não retirar fontes para passar o gate e não tratar
> `UNKNOWN/INCOMPLETE` como janela sem eventos. A observação do consumidor MQTT
> não representa automaticamente o tráfego do publisher. Manter o fluxo atual.

## Percurso e proposta a fechar após as rotas

Fatos atuais: broker Windows Mosquitto em `192.168.155.1:1883`, VMnet8;
consumidor no HarpiServer `192.168.155.144`, conexão estabelecida pela ens33;
API e PostgreSQL em loopback. ens37=`10.20.30.1/24`; `ip_forward=0`.
O endereço histórico `.142` do Poste 2 não foi autenticado nesta rodada.

Comandos solicitados no console do Poste 2, sem segredos:

```sh
hostname
id -un
ip -br -4 address
ip -4 route
ip -4 route get 192.168.155.1
```

| Caminho confirmado futuramente | Observação e mecanismo | Defesa possível | Ajustes a apresentar |
| --- | --- | --- | --- |
| Poste 2 direto ao broker via VMnet8 | NIC de saída confirmada no próprio Poste 2 com captura local, ou VMnet8 do Windows no endpoint broker, com sensor/PCAP compatível e direção publisher → broker | ACL/identidade/tópico no broker; firewall INPUT do Windows no destino; firewall OUTPUT do Poste 2 na origem, conforme escopo e autorização | Captura: posicionar sensor compatível e definir perfil/filtro/fontes; nenhuma rota necessária. Contenção: política explícita no endpoint escolhido, sem executar nesta inspeção |
| Poste 2 efetivamente roteado pelo HarpiServer | ens37 na entrada e NIC de saída realmente indicada pela rota; correlação dos dois trechos, considerando NAT se existir | INPUT para destinos locais; FORWARD somente para trânsito comprovado | Captura: sensor nas interfaces comprovadas. Contenção: política e caminho de retorno; forwarding/NAT/rotas somente se necessários ao desenho e aprovados previamente |
| Poste 2 → serviço local em 10.20.30.1 | ens37 observa esse fluxo específico | INPUT no gateway | Não equivale ao fluxo MQTT para o broker Windows; não usar essa coleta para alegar proteção do publisher → broker |

Capturar em ens33 não permite presumir visibilidade do unicast entre outras
máquinas da VMnet8. Uma VM observadora só serve para esse trecho se houver
mecanismo de espelhamento/TAP/visibilidade do switch virtual comprovado; modo
promíscuo sozinho não prova entrega desses pacotes. Captura no endpoint broker
ou publisher dispensa essa suposição. Não instalar sensor Windows nem iniciar
PCAP nesta consolidação. Não declarar nftables do gateway capaz de conter um
tráfego que não o atravessa. Bloqueio de rede e autorização MQTT são mecanismos
distintos e devem ter escopos explícitos.

## Texto para repassar ao Backend

> Etapa 1 recebida em `feat/config-manager-stage1`, commit completo
> `edd0cb7e1d92e14a2518790db61a7b0c0ffef8dd`, pai exato
> `a09834351c768867bb42c109e07c4c5eab723747`. A base é a integração P11/autenticação,
> não a main antiga nem o runtime genérico de delivery. O delta contém somente
> `backend/config_manager` e seus testes; não modifica routers, bootstrap,
> frontend, autenticação ou projeções. A linha de autenticação local avançou
> para `9e4467ea6d57726a9fc65ab88e5f414f9a69c7cb`; preservar seu mínimo de senha 8
> ao integrar, sem reverter arquivos a partir da base a098343.
>
> Push NÃO confirmado: `git ls-remote origin refs/heads/feat/config-manager-stage1`
> não retornou branch nesta rodada, embora o commit exista localmente. Publicar
> a branch quando autorizado e devolver o SHA remoto. Não confundir worktree
> limpa com publicação. O agente não depende de endereçamento do Maestri para
> receber esta decisão de base: este texto é o alinhamento manual do arquiteto.
>
> Compatibilidade estrutural revisada: módulo interno psycopg/P03, schema
> aditivo separado `hs_config`, migração explícita; não substitui tabelas P11
> ou de autenticação. Registro entregue: 21 testes, incluindo PostgreSQL 18.6
> isolado. Não são testes de integração com o backend ativo. A futura integração
> precisa resolver dependências/PYTHONPATH de P03, papel SQL de runtime, migração
> controlada e manifesto confiável das capacidades reais. Não executar isso agora.
> Consulta somente de leitura na VM: Python 3.14.4, psycopg 3.3.6,
> jsonschema 4.26.0, FastAPI 0.143.3 e PostgreSQL 18.6. As dependências principais
> declaradas estão presentes, mas isso não comprova execução do módulo no runtime
> Python 3.14. O schema `hs_config` não existe no banco atual; `projections` e
> `hs_admin_account` existem. Nenhuma migração foi aplicada. Recibo em
> `docs/continuity/2026-10-31/config-runtime-readonly.json`.
>
> Há incompatibilidade de política concreta com importar automaticamente o MQTT
> atual: schema exige `mqtt_tls_mode=required`, CA/identidade cadastradas; o fluxo
> operacional observado usa 1883 sem TLS. Não relaxar o schema nem migrar o broker
> como efeito colateral. Não representar valores desejados como configuração
> efetiva. API autenticada, autorização/MFA, aplicadores e verificadores reais
> ainda não existem. O gerenciador NÃO está operacional nem autorizado a aplicar
> configurações. Persistir um recibo sintético não comprova aplicação real.

## Texto para repassar ao IoT/MQTT

> Responsável por `iot/esp32/poste1`: agente IoT/MQTT, incluindo firmware,
> serialização, exemplos de configuração sem segredos e testes correspondentes.
> Backend responde pelo adaptador/validação/persistência; mudanças no consumidor
> operacional, ACLs e configuração do broker exigem coordenação e proposta,
> sem sobrepor o trabalho de autenticação ou do gerenciador.
>
> Base exata para a próxima integração isolada: commit local aprovado
> `9e4467ea6d57726a9fc65ab88e5f414f9a69c7cb`, branch
> `feat/frontend-backend-autonomia`. O remoto dessa branch ainda está em a098343
> na consulta atual, portanto resolver a base pelo SHA local; não presumir que
> um clone remoto já contém 9e4467e. Não criar estrutura nesta consolidação.
> A branch IoT existente `iot-mqtt` continua em
> `30132e7787a1f481db576f2386cd2b09d9d31912`, publicada nesse SHA. Os três blobs
> de `iot/esp32/poste1` são idênticos entre essa branch e 9e4467e; reutilizá-los.
>
> Worktree atual existe em
> `D:\Projetos\tcc - harpisense\harpisense-worktrees\iot-mqtt` e o Git consegue
> lê-la. O cadastro aponta ao caminho antigo
> `D:\Projetos\harpisense-worktrees\iot-mqtt\.git`, por isso está prunable.
> Há alteração staged em `docs/progresso/iot-mqtt.md`: preservar índice, arquivos
> não rastreados/ignorados e branches antes de qualquer reparo futuro. Não executar
> prune/remove/reset/recriação. Se for necessário corrigir, primeiro inventariar
> e fazer backup local, depois usar reparo do vínculo, sem recriar o firmware.
>
> Fontes disponíveis na raiz do projeto:
> - `harpisense-worktrees/frontend-backend-autonomia/docs/continuity/2026-10-31/mqtt-consumer-current.sanitized.txt`:
>   cópia de referência, não executável, do consumidor ativo lido nesta rodada;
>   não contém valores de senha/DSN/token. Origem:
>   `/opt/harpisense/staging/p11-postgresql/mqtt_consumer.py`; hash original em
>   `vm-source-hashes.json` no mesmo diretório. Não executar o snapshot: ele
>   contém inicialização operacional, embora seus segredos sejam lidos externamente.
> - `harpisense-worktrees/frontend-backend-autonomia/lab/legitimate-traffic/mqtt_contract.py`
>   e `tests/integration/test_mqtt_contract.py`: contrato/testes históricos do
>   envelope environment; NÃO representam o parser ativo do Poste 2.
> - P05: `referencias/versão_v2/05_Firmware_ESP32/HarpiSense_Etapa05_Firmware_ESP32_v2/05_Firmware_ESP32/CONTRATO_TELEMETRIA_E_COMPATIBILIDADE.md`.
> - P06: `referencias/versão_v2/06_Telemetria_MQTT/HarpiSense_Etapa06_Telemetria_MQTT_v2/06_Telemetria_MQTT/CONTRATO_TELEMETRIA_MQTT_v2.md`.
> - P07: `referencias/versão_v2/07_MQTT_Ingestao/HarpiSense_Pacote07_MQTT_Ingestao_v2/ingest/consumer.py`:
>   referência de pacote; NÃO é o consumidor atualmente em execução na VM.
>
> Decisão de compatibilidade: preservar sem alteração o caminho atual do Poste 2,
> tópico `harpisense/poste2/telemetry`, `device_id=poste2`, QoS de assinatura 1,
> ID de persistência `poste2-` + SHA-256(tópico UTF-8 + byte nulo + payload bruto).
> O parser ativo exige objeto JSON UTF-8 e essa identidade; não valida o envelope
> environment nem os dois envelopes de proposta. Não usar o Poste 2 como identidade
> substituta para aceitar dados do Poste 1.
>
> Poste 1 deve manter identidade própria, credencial MQTT/ACL/client ID próprios
> e roteamento explícito. Para a compatibilidade do firmware existente, preservar
> `device_id=harpisense.poste.poste-1` e tópico
> `harpisense/v1/telemetry/harpisense.poste.poste-1/environment` como linha histórica
> a testar em isolamento; isso NÃO habilita publicação no ambiente atual.
> Antes de habilitar, reconciliar modelo de sensor e envelope aprovado com um
> adaptador de backend adicional e delimitado para o Poste 1; não alargar o parser
> Poste 2 nem renomear silenciosamente seus dados. Se o hardware aprovado exigir
> LDR, documentar o mapeamento/versão explicitamente: não preencher temperatura
> com ADC, nem chamar ADC de lux. Não inventar sensor/pinagem, timestamp NTP ou
> estado físico do LED. Retransmissão deve manter identidade da amostra e payload;
> sem sincronização, não publicar o timestamp fictício de 1970 do firmware antigo.
>
> P05 usa `harpisense.telemetry.proposal.v2` e campos reading_raw/quality etc.;
> P06 usa `harpisense.telemetry.candidate.v2`, measurements/status e tópico por
> sensor. Ambos são propostas e divergem do consumidor ativo e do environment
> histórico. Não escolher pelo nome ou número. Entregar matriz campos/tipos/
> unidades/identidade/tópico/ACL/tempo/deduplicação para decisão de contrato;
> comprovar rejeição de identidade trocada e regressão do Poste 2 antes de
> qualquer habilitação. A configuração de publicação deve continuar fechada até
> compatibilidade e caminho de rede aprovados.

## Próxima alteração mínima

Ainda não executar alteração operacional. Os próximos passos de aceite são
entrada no portal observável e leitura das rotas do Poste 2. Com esses resultados,
fechar uma proposta de sensor no endpoint ou de espelhamento comprovado; se o
caminho for NAT direto, a observação pode dispensar mudança de rota/firewall.
Contenção é proposta separada, com mecanismo, escopo, impacto e reversão. Nenhum
merge do gerenciador, firmware novo ou implantação P08 está iniciado por este texto.
