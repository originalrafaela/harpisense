# Triagem histórica P08 e decisão de nova coleta — 27/10/2026

## Resultado e decisão

Foi recebida a execução privilegiada somente leitura de
`triage_p08_history_readonly.py`, capturada em `2026-10-27T00:46:41.620105Z`.
Ela inventariou 20 relatórios, aprofundou `p08-v4-persistencia-auto02`,
`p08-v4-orquestrado-validacao01` e `p08-v3-tcp-validacao03` e não registrou
erro de leitura para esses artefatos. A triagem não executou o validador real.

**Decisão:** nenhuma sessão existente atende aos requisitos de uma sessão P08
completa e cobertura demonstrável. É necessária uma coleta nova para obter essas
evidências em conjunto desde o início. A sessão `p08-v4-persistencia-auto02` é a
melhor candidata para submissão ao validador real de estrutura/artefatos, como
diagnóstico offline; não deve ser tratada como aprovada para cobertura. O
preflight de metadados passou para os três candidatos aprofundados, mas não
substitui a execução do validador nem satisfaz o gate de cobertura.

Essa decisão não depende de nomes ou hashes como prova de cobertura. Em todos os
20 relatórios, `collection_complete` e `ready_for_inference` são `false`. Nos
relatórios que têm diagnóstico, a qualidade é `INCOMPLETE`,
`logs_complete=false` e `collection_complete=false`. Nenhuma sessão declara
`required_sources` ou registros de cobertura por fonte. Assim, mesmo os melhores
PCAPs/janelas não demonstram que as fontes obrigatórias foram observadas durante
todo o intervalo.

## Triagem dos 20 relatórios

Todos os 20 têm arquivo `.session.json` e `session_basic_checks_passed=true` no
relatório. A coluna “faltam artefatos” lista os artefatos esperados que a triagem
não encontrou. A contagem de janelas é metadado, não prova de continuidade.

| Sessão | Faltam artefatos | Janelas | Elegibilidade e razão objetiva |
|---|---|---:|---|
| `p08-orquestrador-teste01` | coverage | 0 | Não apta à cobertura: diagnóstico ausente, sem janelas ou fontes declaradas. |
| `p08-orquestrador-teste02` | coverage | 1 | Não apta: diagnóstico ausente, só uma janela e sem fontes declaradas. |
| `p08-v2-heartbeat-teste01` | p08, coverage | 0 | Não apta: sem integração/diagnóstico/janelas; continuidade não comprovada. |
| `p08-v2-heartbeat-trafego01` | p08, coverage | 0 | Não apta: sem integração/diagnóstico/janelas; continuidade não comprovada. |
| `p08-v2-teste01` | nenhum dos quatro | 0 | Não apta: diagnóstico marca INCOMPLETE; sem janelas/fontes declaradas. |
| `p08-v2-trafego-real01` | nenhum dos quatro | 1 | Não apta: diagnóstico INCOMPLETE e somente uma janela. |
| `p08-v3-heartbeat-teste01` | nenhum dos quatro | 0 | Não apta: INCOMPLETE, sem janelas e continuidade não comprovada. |
| `p08-v3-heartbeat-trafego01` | nenhum dos quatro | 1 | Não apta: INCOMPLETE, uma janela e continuidade não comprovada. |
| `p08-v3-integrado-teste01` | nenhum dos quatro | 0 | Não apta: INCOMPLETE; 2/11 heartbeats sem tcpdump; sem janelas. |
| `p08-v3-monitor-direto-teste01` | p08, coverage | 0 | Não apta: integração/diagnóstico/janelas ausentes; 2 heartbeats sem tcpdump. |
| `p08-v3-tcp-controlado01` | nenhum dos quatro | 0 | Não apta: INCOMPLETE; 1/20 heartbeats sem tcpdump; sem janelas. |
| `p08-v3-tcp-validacao03` | nenhum dos quatro | 0 | Não apta à cobertura; candidata ao validador de artefatos. Detalhada abaixo. |
| `p08-v4-captura-validacao01` | p08, coverage | 0 | Não apta: integração/diagnóstico/janelas ausentes; 2 heartbeats sem tcpdump. |
| `p08-v4-orquestrado-validacao01` | nenhum dos quatro | 3 | Não apta à cobertura; candidata ao validador de artefatos. Detalhada abaixo. |
| `p08-v4-persistencia-auto01` | coverage | 0 | Não apta: diagnóstico ausente, sem janelas e 1 heartbeat sem tcpdump. |
| `p08-v4-persistencia-auto02` | nenhum dos quatro | 4 | Melhor candidata para submissão ao validador de artefatos; cobertura incompleta. Detalhada abaixo. |
| `p08-v4-tcp-validacao03` | p08, coverage | 0 | Não apta: integração/diagnóstico/janelas ausentes; continuidade não comprovada. |
| `p08_controlador_teste01` | p08, coverage | 0 | Não apta: integração/diagnóstico/janelas ausentes. |
| `p08_controlador_teste02` | p08, coverage | 0 | Não apta: integração/diagnóstico/janelas ausentes. |
| `p08_integridade_adulterada_teste01` | PCAP, p08, coverage | 0 | Não apta: PCAP e artefatos derivados ausentes; o flag básico isolado não reverte isso. |

Os dois relatórios `p08-orquestrador-*` e os três heartbeat/tcp descritos sem
diagnóstico não foram promovidos por passarem no teste básico. Esse teste é
distinto de consistência cruzada e cobertura. Pontuações da triagem serviram
somente para escolher quais candidatos aprofundar.

## Candidatos aprofundados

Nos três, o tamanho/hash/caminho do PCAP, a identidade de sessão na integração,
os vínculos das janelas e IDs únicos passaram as verificações do diagnóstico;
`artifact_gate_metadata_preflight=true`. Isso permite submetê-los ao validador
real de artefatos para obter resultado formal, sem afirmar que ele já foi
executado ou aprovado.

| Sessão | Dados recuperados | Lacunas impeditivas |
|---|---|---|
| `p08-v4-persistencia-auto02` | 20 registros PCAP entre 19:17:31.458187 e 19:18:08.551906Z; quatro janelas de 10s, cinco registros em cada; integração e sessão concordam; estatística do tcpdump: 20 capturados/recebidos, 0 descartados no kernel. | `INCOMPLETE`, `logs_complete=false`, sem fontes/contagens de cobertura. Janelas não cobrem os buckets vazios de borda/final e não há `target_ref` nas janelas. |
| `p08-v4-orquestrado-validacao01` | 10 registros PCAP de 03:23:16.754278 a 03:23:33.810070Z; três janelas com 2, 6 e 2 registros; vínculos cruzados coerentes. | `INCOMPLETE`; quatro buckets sem registros agregados, sem fontes/cobertura declaradas. Apenas três janelas de dados. |
| `p08-v3-tcp-validacao03` | 10 registros PCAP de 02:49:10.296685 a 02:49:23.314538Z; duas janelas com 7 e 3 registros; vínculos cruzados coerentes. | `INCOMPLETE`; cinco buckets sem registros agregados, sem fontes/cobertura declaradas. Apenas duas janelas de dados. |

### Observação de heartbeat e buckets de auto02

A observação ausente é o índice 0: `tcpdump_detected=false` e nenhum PID visível
a `19:17:27.453693Z`, cerca de 1 ms após o início do subprocesso (`19:17:27.444377Z`).
A observação seguinte, aproximadamente 1,011 s depois, encontrou o processo
ativo. A proximidade do `Popen` torna inicialização/visibilidade tardia uma
explicação compatível; não prova falha do monitor nem prova que a captura já
estivesse ativa na observação ausente. O registro do kernel mostra a interface
em modo promíscuo desde 19:17:27.513357Z, mas isso tampouco certifica captura
integral.

Os três buckets com `pacotes_agregados=null` são explicados pelos timestamps
recuperados do PCAP:

| Bucket UTC | Relação com a sessão e os pacotes | O que se pode concluir |
|---|---|---|
| 19:17:20–19:17:30 | Parcial; começa antes da sessão, que iniciou 19:17:27.443326. Primeiro registro PCAP só em 19:17:31.458187. | Nenhum registro PCAP nesse bucket. Não prova ausência de tráfego na rede. |
| 19:18:10–19:18:20 | Completo; último registro PCAP em 19:18:08.551906. | Nenhum registro PCAP nesse bucket. Não prova ausência de tráfego nem completude das fontes. |
| 19:18:20–19:18:30 | Parcial; a sessão terminou 19:18:28.387151. | Nenhum registro PCAP nesse bucket. Não prova ausência de tráfego. |

Portanto, para auto02: a observação negativa é real no relatório e compatível
com uma corrida de inicialização; não há evidência suficiente para atribuí-la a
falha de monitoramento. Os três buckets sem pacotes no PCAP não são evidência de
ausência de tráfego/eventos. A falta de prova de cobertura contínua e por fonte
é uma lacuna de evidência, apesar dos 20 registros e da estatística de zero
descartes do kernel. O código de captura encerrou com status de `timeout` 124;
isso, isoladamente, não demonstra integridade de toda a sessão.

## Recuperável e irrecuperável

**Recuperado de artefatos históricos:** início/fim e interface da sessão; PCAP e
seus timestamps; resumo de contadores do tcpdump; a posição e os vizinhos do
heartbeat ausente; quatro janelas e seus vínculos; os metadados dos 20 relatórios.
O journal local já recuperado também registra o comando/orquestrador e a entrada
e saída de `ens37` do modo promíscuo. Isso sustenta atividade local, não
autenticidade externa ou cobertura.

**Não reconstruível a partir dos artefatos consultados:** tráfego que não foi
registrado no PCAP; cobertura de fontes obrigatórias sem logs/cursors/limites
retidos e vinculados à sessão; identidade de alvo/contexto que não foi gravada;
continuidade que nunca foi observada ou registrada. Um hash ou a cópia posterior
de logs sem vínculo independente não recupera essas provas. Lotes MQTT de 25/10
permanecem de outra data, sem vínculo com estas sessões e não devem ser
associados por proximidade temporal.

Logs de broker/consumidor/API do intervalo podem ainda existir em hosts ou
arquivos rotacionados não examinados; localizar o host real do broker e verificar
retenção é uma busca concreta e delimitada. Se tais registros existirem, podem
ajudar a explicar o histórico, mas não transformam os relatórios existentes em
coleta completa, conforme os próprios flags e artefatos atuais. Não é necessário
prolongar a busca histórica para decidir a próxima coleta.

## Coleta nova: roteiro mínimo para uma rodada futura

Este roteiro prepara a coleta, não a executa e não habilita inferência ou IPS.

**Máquinas/fontes a deixar disponíveis:**

1. HarpiServer/gateway que captura `ens37` e hospeda o orquestrador P08; confirmar
   previamente interface, rota e relógio sincronizado.
2. Host/contêiner real do broker Mosquitto, onde quer que esteja, com log e cursor
   de início/fim habilitados e retenção suficiente para exportação read-only.
3. Host do consumidor MQTT e API P11/FastAPI, caso sejam fontes requeridas pelo
   esquema/validador. Confirmar quais processos rodam na própria HarpiServer e
   quais são remotos; não inferir topologia pelo nome do serviço.
4. Fonte legítima de telemetria (por exemplo, o ESP32/Poste 02 previsto no
   cenário), ligada e identificada. Usar somente tráfego benigno e perfil
   `tcp-observacao`; sem ataques.

Antes de iniciar, enumerar no contrato/validador a lista fechada de
`required_sources`, os sensores, o `target_ref` autorizado, IDs de janela e os
formatos/logs oficiais. Sincronizar relógios e registrar host, boot ID, interface,
IP/identidade de cada fonte e seu método de retenção. Se alguma fonte obrigatória
ou localização de log não estiver disponível, não começar a rodada de cobertura.

**Duração proposta:** 120 segundos de captura efetiva após confirmar `tcpdump`
ativo, mais preparação antes e encerramento ordenado após a captura. Dois minutos
produzem até 12 janelas completas de 10 segundos, com amostra observável maior
que as sessões históricas de 10–60 segundos; iniciar somente depois do heartbeat
confirmar o processo evita repetir a observação inicial ambígua. Os serviços de
log devem ser acompanhados desde antes do início até depois do fim para obter
cursores de fronteira. Se o cenário de fonte não conseguir produzir eventos
benignos nesse período, dimensionar o tempo com base na cadência esperada antes
de iniciar, não preencher janelas com zeros.

**Artefatos esperados:** novo `.session.json`, PCAP com caminho/tamanho/hash,
integração P08, relatório de cobertura, janelas de 10 s vinculadas à sessão,
manifestos/logs por fonte com cursores/boot IDs/intervalos e identificação de
sensor/alvo, inventário de relógios e resultado do validador. Preservar também
logs do monitor com timestamp e estado do processo em cada heartbeat. Não
sobrescrever as sessões históricas nem os checkpoints MQTT.

**Critérios de aceite antes de qualquer uso de inferência:** validador real de
artefatos passa; lista `required_sources` revisada e todas as fontes disponíveis;
limites temporais/cursors cobrem o intervalo; continuidade e perdas avaliadas por
fonte; sessões/janelas/PCAP/logs têm vínculos verificáveis; contagens obedecem ao
schema oficial RF/IF e `unknown` não vira zero. Qualquer falha mantém cobertura
desconhecida e gates fechados. Inferência e IPS permanecem bloqueados até a
aprovação explícita de todos os gates aplicáveis.

## Escopo e preservação

A saída raiz foi fornecida pelo usuário e é evidência de leitura. Nenhum relatório,
PCAP, journal, lote, manifesto, checkpoint, PostgreSQL ou serviço foi alterado;
nenhum coletor, modelo, inferência ou IPS foi executado. A documentação não
associa lotes antigos a qualquer sessão. Nenhum índice, componente P08/P09 ou P11
foi modificado nesta atualização.
