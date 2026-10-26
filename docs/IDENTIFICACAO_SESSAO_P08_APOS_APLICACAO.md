# Instalação confirmada e identificação de sessão P08

Rodada de conferência e identificação somente leitura, posterior à aplicação
executada pelo usuário. Nenhuma coleta, execução de pipeline/modelo, consulta SQL,
associação de lote, alteração de checkpoint ou serviço foi realizada.
Atualizado com a saída privilegiada fornecida pelo usuário, capturada em
2026-10-26T18:01:44.807708Z. Não se afirma nova execução SSH como root.

## Código efetivamente instalado

Os hashes lidos na VM coincidem com a candidata testada do commit `2de050e`,
branch `fix/p08-p09-validated-batch`:

| Arquivo | SHA256 instalado |
|---|---|
| auxiliary_audit_adapter.py | 04b58d66d5d6d9cd513bff4b559c187bca4a2d13ea370e80fcbfc97bb9eb5416 |
| p08_p09_pipeline.py | 4ec9ed8c2fb5b068ebdae4b6cd7643d1aca5a5c0fcc5d9c354e28f5f7f12d8dc |

Diretório: `/opt/harpisense/staging/p09-deteccao-decisao/adaptador_logs_p08_p09`.
Ambos root:root 0644, diretório root:root 0755: adequados para código legível
pelo usuário do processo sem conceder escrita a grupo/outros. Os gates, leitor
de janelas e demais fontes conferidos permanecem com hashes anteriores.

Backup confirmado: `.validated-batch-backup-5jgd2gmh`, root:root 0700. A saída
privilegiada confirma ambos os arquivos originais, root:root 0644:

- auxiliary_audit_adapter.py: a6e2747e9cf857216297db1a9557fa12925e4e1c088b27152a0fcfbea8c827ff.
- p08_p09_pipeline.py: a43d0db34a5c6bca409248d8b464bdacafa3ed93e7eddd34da0fa2de1f4b85cf.

Ambos correspondem à base anterior. O recibo tem applied=True, diretório alvo e
backup corretos e pares before/after iguais à base e à candidata 2de050e.
Conferência do backup/recibo concluída; não foi executada restauração real.

Lotes, manifestos e checkpoint: os cinco hashes continuam iguais aos da base
confirmada. A inspeção sanitizada também comparou metadados/hashes antes e depois,
sem alteração. O Store P11 mantém cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c;
app.py mantém 52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2.
P11 ativo, PID 1787, início 26/10/2026 12:53:53 -03, sem reinício. A paginação SQL
não foi instalada. `INSTALLED_READONLY_RESULTS.json` e `STAGING_STATUS.json`, na
branch de implementação, registram o estado aplicado e os limites da conferência.

## Sessão existente aproveitável para análise offline

A inspeção privilegiada listou 20 relatórios .session.json em
`/opt/harpisense/capturas`. A sessão detalhada é **p08-v4-persistencia-auto02**,
agora comprovadamente existente, não apenas um default do leitor. As outras 19
foram somente inventariadas; não há base para concluir que todas são insuficientes.

Intervalo: 23/10/2026 19:17:27.443326–19:18:28.387151 UTC. Interface ens37,
sensor harpiserver; verificação básica da sessão aprovada. Arquivos presentes:

| Artefato, todos com prefixo p08-v4-persistencia-auto02 | Evidência |
|---|---|
| .session.json | SHA256 74a6a4c4c99cef85fc23c8c5f2625df4879f0999ecbcfe9702f1c9b49d9ff99f; registra caminho, tamanho e hash do PCAP. |
| .pcap | 1.824 bytes, SHA256 87f05fa8954d5ae648861c609b09942dcfb1cbcbefb05d7228bedb70719cf52c; hash calculado confere com a sessão. |
| .p08.json | SHA256 cf285f11dde03104d02a803f28e58ada57ed39ef9ceae2d34ed64cd056df6169; referencia mesmo caminho/tamanho/hash de PCAP, interface e sessão; 20 eventos convertidos e quatro janelas. |
| .coverage.json | SHA256 9ffc11c3600bbef9441c3e2d69eba83559b829d3566e43142ab811c054cf7ca1; diagnóstico da mesma sessão, não certificado de cobertura. |

As quatro janelas são únicas, de 10 segundos, com collection_session_id explícito
igual à sessão, sensor harpiserver e interface ens37. Intervalos UTC:
19:17:30–40, 19:17:40–50, 19:17:50–19:18:00 e 19:18:00–10. Todas estão dentro
do intervalo da sessão. Declaram schema harpisense.if.window.v1 e perfil
tcp-observacao. Isso identifica a cadeia local sessão → PCAP → integração →
janelas; não é validação numérica completa das features nem compatibilidade RF/IF.
Os window_links fornecidos não trazem target_ref; não foi comprovado contexto de
alvo autenticado para correlação. Integridade local não atesta autoria independente.

Portanto, **a sessão é aproveitável para integridade, rastreabilidade e análise
offline**. Não está apta a comprovar captura/logs completos: quality=INCOMPLETE,
collection_complete=False, logs_complete=False e ready_for_inference=False.
Há 60 observações de heartbeat, 59 com tcpdump ativo e uma sem detecção;
continuous_capture_proven=False. Essa observação não prova perda de pacote,
mas não permite certificar continuidade. O diagnóstico tem sete intervalos,
quatro com eventos e três sem dados agregados. Ausência de agregado não prova
ausência de tráfego nem equivale a zero numa feature.

## Vínculos a demonstrar, sem criá-los nesta rodada

Conforme o código atual do P08 e as referências aprovadas V2, os três primeiros
vínculos abaixo estão demonstrados por consistência dos artefatos fornecidos;
os vínculos com evidências/logs, alvo e cobertura permanecem pendentes:

| Relação | Evidência necessária |
|---|---|
| Sessão → PCAP | .session.json com caminho, tamanho e SHA256 correspondentes ao PCAP existente; intervalo UTC, interface e resultado das verificações básicas. |
| Sessão/PCAP → integração | `<session>.p08.json` com session explícita, pcap.path/sha256/size_bytes e interface correspondentes. O nome de arquivo isoladamente não comprova a relação. |
| Integração → janelas | aggregation.windows; IDs únicos, collection_session_id, sensor_id, interface, perfil, feature_schema_version, duração e início/fim; integridade/proveniência do relatório. |
| Evidência → sessão/janela/alvo | ID estável da evidência, inventário/vínculo confiável para collection_session_id, sensor_id, target_ref e scope_ref quando exigido pelo contrato; intervalo temporal coerente. Um endereço IP não substitui identidade MQTT/dispositivo. |
| Lote → evidências/fonte | Hash e manifesto local consistente, evento, cursor e boot; identidade/procedência da fonte e contexto confirmado separadamente. Hash não autentica autoria. |
| Fontes → cobertura | Fontes obrigatórias explícitas e intervalos comprovados por fonte/contexto, retenção, rotações/reinícios/lacunas e relógios. O diagnóstico de captura não substitui coverage_records autenticados. |

Os dois lotes antigos **continuam sem associação**. A leitura permitida mostrou:

- acabf4…: um evento raw validation_failure com observed_at
  `2026-10-25T18:46:20.171871+00:00`, sensor_id=null, cursor/boot presentes, sem
  collection_session_id, window_id ou target_ref explícitos no evento.
- d94cc2…: lista vazia, sem eventos para estabelecer vínculo.
- Os manifestos têm UNKNOWN, continuity_verified=False e autorizações False;
  não declaram os vínculos de sessão/janela/alvo. Cursores delimitam uma leitura,
  mas não provam cobertura ou pertinência a uma sessão.

O evento é de **25/10**, enquanto a sessão detalhada ocorreu em **23/10**: está
fora tanto da sessão quanto das quatro janelas. Não é candidato temporal para
esse conjunto. O lote vazio tampouco prova cobertura de intervalo algum.
Mesmo coincidência de horário não autenticaria o vínculo. Não preencher contexto
por proximidade temporal ou pelo nome dos lotes; nenhuma associação foi criada.

## Artefatos e fontes ainda necessários para validar cobertura

PCAP, session, integração/janelas e diagnóstico coverage da sessão selecionada
**já existem**. O que não está comprovado/fornecido é:

- Logs históricos das fontes obrigatórias cobrindo o intervalo dessa sessão em
  23/10, com identificação da origem, hashes, cursores/boot quando aplicáveis e
  informação de retenção/rotação/lacunas/relógio.
- coverage_records verificáveis por fonte, contexto e intervalo. O diagnóstico
  .coverage.json presente não os substitui; seus intervalos não atestam completude.
- Vínculo confiável entre evidence_id, collection_session_id, sensor_id,
  target_ref e scope_ref onde exigido. Os lotes fornecidos não entregam esse vínculo.
- Eventual evidência independente que esclareça o intervalo sem processo observado
  e a abrangência real das interfaces/fontes, sem alterar retrospectivamente os
  flags conservadores ou fabricar contagens.

Essas são pendências de evidência, não uma afirmação de que os arquivos históricos
foram perdidos ou de que não possam estar disponíveis em outra fonte. O produtor
atual de `<session>.coverage.json` é um diagnóstico conservador.
Heartbeat ativo e zero perdas do kernel, isoladamente, não comprovam captura
integral nem logs completos, conforme o próprio código P08.

Fontes a disponibilizar conforme required_sources: journal do consumidor
`harpisense-mqtt.service` (telemetria/validação/duplicidade), logs Mosquitto de
autenticação/ACL/publicação, e logs da API quando exigidos pelo cenário. Para cada
fonte faltam confirmação do host/serviço, intervalo, retenção/rotação, boot/cursor,
continuidade e sincronização temporal. O host SSH se identifica como `gateway`;
nele foram observados `harpisense-mqtt` e `harpisense-p11` ativos. Isso não prova
onde o broker roda nem que o histórico completo esteja retido.

As referências V2 P08 de correlação exigem sessão/escopo/alvo confiáveis e deixam
os componentes v1 preservados em componentes/. Usam-se pacotes anteriores de
Versões corretas para componentes sem atualização; não se conclui ausência por
não existir revisão individual V2. Nenhum componente foi substituído nesta rodada.

## Se uma coleta nova se mostrar necessária: procedimento proposto, não executado

**Não há justificativa demonstrada para exigir nova coleta agora.** A sessão
selecionada é útil; sua insuficiência é específica para certificar cobertura e
vínculo com os lotes antigos. Os outros 19 relatórios não foram avaliados em
detalhe. O próximo passo mínimo é localizar/verificar os logs históricos e o
inventário de contexto de 23/10, não executar um novo ensaio.

Uma nova sessão só deve ser proposta após verificar se os artefatos e os logs
antigos permitem o vínculo/intervalo exigidos. Se não houver evidência recuperável, manter
os lotes antigos sem vínculo e produzir um conjunto novo, sem reinterpretar os
antigos como evidência da nova sessão.

1. Definir sessão com ID novo e diretório/arquivos exclusivos, janela UTC,
   interface, sensor, percurso, perfil, alvo e fontes obrigatórias confirmados.
   Não usar valores default dos scripts como inventário de rede verificado.
2. Disponibilizar HarpiServer/gateway de captura; host real do broker; consumidor
   de telemetria; produtores legítimos ESP32/Poste 02 conforme o fluxo. O host da
   API é necessário se seus logs forem fonte obrigatória. Windows/VMware e
   intermediário Tailscale precisam estar ligados somente se hospedarem ou
   transportarem esses papéis. Não há necessidade de ataques/Kali para esse fluxo.
3. Registrar relógios e limites de retenção/boot/cursor das fontes no começo/fim,
   com exportação limitada ao intervalo e arquivos novos. Não executar os
   coletores incrementais atuais nem avançar seus checkpoints para esse ensaio.
4. Em rodada autorizada, usar o controlador `capture_session_v4.py` com interface,
   source-ip, duration e output explícitos. Ele recusa sobrescrita; a existência
   de PCAP não promove collection_complete. Não iniciar essa captura nesta rodada.
5. Processar offline com `integrar_p08_v2.py` e diagnosticar com
   `diagnosticar_cobertura.py`, preservando hashes e saídas exclusivas. O
   `orquestrar_p08_v4_experimental.py` vigente também chama
   `persistir_janelas_p08.py`: **não usá-lo para um procedimento sem escrita no
   PostgreSQL**. A persistência é uma ação separada e não foi autorizada aqui.
6. Validar vínculos e cobertura independente por fonte antes de produzir contagens.
   Campos desconhecidos não viram zero. Eventos auxiliares de validação/duplicidade
   não criam features novas no esquema RF/IF.
7. Guardar o conjunto novo com provenance/manifestos sem tocar lotes/checkpoint
   antigos. Permanecer UNKNOWN quando houver lacuna, com inferência e IPS False.

Conferência de backup e identificação de sessão concluídas com a evidência
privilegiada fornecida. Próximo passo mínimo: identificar a disponibilidade dos
logs históricos/fontes obrigatórias e do inventário confiável para o intervalo
da sessão selecionada. Não implementar associação, coletor ou promoção de cobertura.
