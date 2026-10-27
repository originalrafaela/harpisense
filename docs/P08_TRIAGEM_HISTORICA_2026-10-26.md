# Evidências históricas P08 — resultado parcial e decisão de continuidade

> **Atualização:** a triagem root foi concluída em 27/10/2026. As seções que
> descrevem a triagem pendente e decisão provisória abaixo são o registro do
> estado anterior e foram substituídas por
> [`P08_DECISAO_COBERTURA_2026-10-27.md`](P08_DECISAO_COBERTURA_2026-10-27.md).
> Resultado atual: auto02 é candidata ao validador de artefatos, nenhuma das 20
> sessões comprova cobertura completa e uma coleta nova será necessária para
> obter as evidências faltantes. Inferência/IPS continuam bloqueados.

Escopo: sessão p08-v4-persistencia-auto02, 23/10/2026,
19:17:27.443326–19:18:28.387151 UTC, e triagem das demais sessões existentes.
Não se repetiram verificações de instalação ou da integridade do backup aplicado.
Nenhum coletor, pipeline, modelo, SQL, checkpoint ou serviço foi executado ou
alterado. Arquivos históricos foram somente lidos. Arquivos novos desta rodada
limitam-se à documentação local e a um diagnóstico em diretório temporário.

Referências: entregas aprovadas em referencias/versão_v2, em particular P08
componentes/edge/README.md e P09 harpisense_data/windows.py, que preservam o schema
e os componentes v1. Os pacotes de Versões corretas permanecem referência para
componentes sem atualização. Não se presumiu ausência de componentes pela falta
de uma revisão V2 individual.

## Journal do intervalo: evidência já obtida

Consulta journalctl somente leitura no intervalo envolvente
19:17:27–19:18:29 UTC, sem exportar mensagens brutas/payloads. Artefatos:

- P08_HISTORICAL_JOURNAL.json: registros e limites disponíveis por unit.
- P08_HISTORICAL_CAPTURE_EVENTS.json: classificação segura dos quatro registros
  locais encontrados no intervalo, com origem e horário.
- P08_HISTORICAL_SOURCE_LIFECYCLE.json: ciclo de vida das fontes no boot histórico.

Origem: host gateway, boot 91d82a3b9b3f4560b0105de61e49413a. O journal retido
desse boot cobre registros entre 18:58:04.285103 e 19:31:43.788077 UTC. Isso é
extensão de registros disponíveis, não comprovação de que toda mensagem/evento
foi emitida, armazenada ou exportada. O texto original de list-boots exibe -03;
as datas normalizadas nos demais artefatos foram convertidas do epoch para UTC.

| Horário UTC | Origem | Evidência |
|---|---|---|
| 19:17:27.340732 | sudo / session-3.scope | Abertura de sessão PAM. |
| 19:17:27.341145 | sudo / session-3.scope | Registro de comando contém orquestrar_p08_v4_experimental.py e p08-v4-persistencia-auto02. Não se exportou o comando bruto. |
| 19:17:27.513357 | kernel | ens37 entrou em modo promíscuo. |
| 19:18:27.468657 | kernel | ens37 saiu de modo promíscuo. |

Esses rastros corroboram localmente execução e atividade da interface no intervalo
da sessão, sem provar captura integral, identidade do alvo, autenticidade externa
ou ausência de perdas. Não vinculam os lotes de auditoria de 25/10 à sessão de 23/10.

Fontes procuradas:

| Fonte local | Registros no intervalo envolvente | Retenção/ciclo observado |
|---|---:|---|
| harpisense-mqtt.service | 0 | Registros disponíveis de 18/10 a 26/10; no boot da sessão, início 18:58:15 e parada 19:31:40 UTC. |
| harpisense-p11.service | 0 | Registros disponíveis de 18/10 a 26/10; no boot da sessão, início 18:58:15 e parada 19:31:40 UTC. |
| mosquitto.service | 0 | Nenhum registro dessa unit encontrado no journal local consultado. Host/destino real de logs do broker ainda não confirmado. |

O consumidor teve uma mensagem anterior à sessão às 19:14:45 UTC. Não se
exportou seu payload nem se inferiu que seja evidência da sessão. As units atuais
declaram StandardOutput=journal; isso não prova que configuração/instrumentação
fossem idênticas em 23/10. Nenhum arquivo de log foi encontrado no diretório
legível /opt/harpisense/logs (busca até profundidade 2), nem arquivos nomeados
mosquitto/mqtt/harpi em /var/log até profundidade 2. /var/log/private e chrony
tiveram restrição de acesso. Não se declara inexistência de logs em outros hosts,
contêineres, arquivos rotacionados ou locais não pesquisados.

Zero entradas retornadas significa somente ausência de registros retidos/legíveis
nessa consulta. Não equivale a zero autenticações, publicações, falhas, pedidos
HTTP ou eventos de telemetria. Início/parada de serviço delimitam atividade de
processo observada pelo systemd, sem certificar completude dos seus eventos.

## Heartbeat e três intervalos: classificação ainda limitada

O monitor vigente consulta /proc, procura tcpdump no grupo do processo e exclui
estados Z/X/x. Erros OSError/ValueError/IndexError são ignorados. O controlador
observa o processo após subprocess.Popen e usa relógio monotônico para intervalos,
além de timestamps UTC no relatório. Assim, uma observação sem tcpdump pode ser
compatível com inicialização, ausência real do processo ou uma falha de leitura;
o resumo 59/60, isoladamente, não distingue essas hipóteses. O código atual não
é evidência suficiente para afirmar qual versão exata produziu cada relatório.

| Questão | Conclusão permitida agora |
|---|---|
| Falha do monitor | Não demonstrada: falta ler timestamp/posição da observação ausente, processo e vizinhos. |
| Ausência de coleta | Não demonstrada pela observação; kernel registra modo promíscuo no período, mas isso não prova captura contínua. |
| Ausência de eventos | Não demonstrada pelos três intervalos sem agregado nem pelo silêncio das units no journal. |
| Falta de evidência para concluir completude | Confirmada: continuous_capture_proven=False, INCOMPLETE e logs_complete=False; faltam detalhamento da observação, contagem por timestamp do PCAP e cobertura por fonte. |

O diagnóstico de cobertura constrói buckets de 10 s alinhados a UTC, arredondando
o início para baixo e o fim para cima. Buckets parciais de borda podem existir.
Uma janela ausente produz pacotes_agregados=None, não zero. O script não deve
ser interpretado como comprovação de interrupção da captura nem ausência de
tráfego. Atribuir os três intervalos a início/fim ou a silêncio real requer os
intervalos detalhados e os timestamps dos registros PCAP, ainda protegidos.

## Triagem: critérios definidos, aplicação aos outros 19 ainda bloqueada

A inspeção privilegiada anterior listou 20 nomes/hashes de relatórios, mas apenas
auto02 foi detalhada. Os metadados completos dos outros 19 continuam root-only
em /opt/harpisense/capturas (0700). A nova tentativa de leitura comum retornou
PermissionError. Não se classificam sessões por nome, rótulo de teste ou versão
aparente, nem se apresenta essa lista anterior como triagem concluída.

Foi preparado triage_p08_history_readonly.py. Ele:

1. Lê somente metadados dos 20 relatórios e artefatos correspondentes.
2. Ordena por presença dos quatro artefatos (1 ponto cada), checks básicos True
   (2 pontos), janelas existentes (2 pontos), usando data final como desempate.
   Score não certifica elegibilidade nem confiança; apenas limita aprofundamento.
3. Aprofunda até três candidatos com checks básicos True e a sessão auto02:
   consistência de referências, posição e vizinhos dos heartbeats sem tcpdump,
   intervalos do diagnóstico e buckets de timestamps do PCAP clássico.
4. Não exporta pacotes/endereço/payload, não importa app, não cria arquivo, não
   executa SQL, pipeline ou coleta. PCAP acima de 256 MiB fica explicitamente
   sem aprofundamento automático; erros e formatos não suportados são registrados.

O parser de timestamps foi verificado em contêiner local sem rede, com quatro
combinações de endian/resolução e dois arquivos malformados sintéticos. Isso
valida apenas o diagnóstico, nunca cobertura das sessões reais.

Comando solicitado ao usuário para a leitura privilegiada, ainda sem saída nesta
rodada:

```sh
sudo /usr/bin/python3 -B /tmp/harpisense-p08p09-validated-batch.grdSWc/p08_p09/triage_p08_history_readonly.py
```

Tabela de elegibilidade **parcial**, sem substituir a triagem ainda pendente:

| Sessão | Artefatos presentes | Evidência faltante | Elegibilidade | Justificativa |
|---|---|---|---|---|
| p08-v4-persistencia-auto02 | Session, PCAP, integração, diagnóstico; quatro janelas; rastros sudo/kernel no mesmo boot | Detalhes do heartbeat/PCAP, logs por fonte e contexto/alvo confiável | Reutilizável offline; completude não demonstrada | Integridade/referências locais conferem, mas INCOMPLETE; três intervalos sem agregado e cobertura não atestada. |
| Outras 19 sessões listadas | Relatórios .session.json existentes; demais artefatos ainda não inventariados nesta triagem | Metadados e verificação objetiva de candidatos via leitura root | Pendente, não reprovadas | Acesso comum negado; nome e hash isolados não permitem elegibilidade. |

## Validador real e decisão desta rodada

Não confundir três avaliações distintas:

- validar_sessao.py verifica integridade/estrutura básica e **exige** flags
  conservadores False. Uma sessão pode passar nisso sem ser uma sessão completa.
- p08_artifact_validator.py verifica consistência cruzada de session/coverage/pcap,
  também mantendo inferência desativada; não certifica cobertura de fonte.
- coverage_gate e prepare_verified_log_counts exigem contexto/intervalos; a
  integração vigente não libera contagens sem procedência independente. A presença
  de flags autodeclarados ou ausência de mensagem não substitui esse requisito.

Nenhum desses validadores foi executado nesta rodada. Os candidatos precisam ser
conferidos pelos critérios pertinentes antes de serem declarados aptos; não se
relaxa gate nem se fabrica required_sources vazio para aparentar aprovação.

**Decisão: existe uma pendência histórica específica recuperável.** Os relatórios
e PCAPs existem em armazenamento protegido e o journal do boot/intervalo ainda
está disponível. Falta obter a saída da leitura root já preparada para fechar a
triagem objetiva e a classificação do heartbeat/buckets; também falta localizar
o log histórico do broker e definir as fontes/contexto obrigatórios da sessão.
Não há justificativa demonstrada para exigir nova coleta agora, nem evidência
para afirmar que todas as sessões existentes são insuficientes.

Esta decisão é um ponto de continuidade, **não conclusão da triagem solicitada**:
ela depende da saída privilegiada pendente. Não se declara sessão completa apta
ao fluxo de cobertura. Após obter os metadados, aprofundar somente os melhores
candidatos e verificar recuperação do histórico no host real do broker antes de
decidir se uma nova coleta é necessária.

Se futuramente a evidência faltar de forma irrecuperável, o roteiro condicional
em IDENTIFICACAO_SESSAO_P08_APOS_APLICACAO.md prevê ID/arquivos novos, gateway,
broker, consumidor e produtor legítimo, fontes e intervalos explícitos. A duração
deverá comportar ao menos janelas completas de 10 s, com margens de inicialização
e encerramento definidas por medições; duração maior, isoladamente, não resolve
falta de cobertura. Os critérios de aceite serão rastreabilidade, contexto e
cobertura por fonte verificáveis, nunca heartbeat isolado ou flags promovidos.
Nenhuma coleta foi iniciada, proposta como obrigatória ou autorizada por esta nota.
