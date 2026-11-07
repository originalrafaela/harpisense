# Perfil, estado e atividade — critérios de integração

Base preservada: `a8fef1f5810ad5077658a29fe2aa407ffd21df6d`. Esta entrega deve
ser revisada em worktrees isoladas; não atualizar native-installers nem a prévia 5174.

## Autoridade e consistência

- Seleção frontend é rascunho. Apenas Aplicar solicita mudança ao backend.
- Aplicar deve consultar e validar o estado dentro da mesma transação que altera
  o perfil, serializando também os escritores de atividade. Validar apenas antes
  da transação deixa uma corrida entre aprovação, execução, incidente e troca.
- Ataque, anomalia ou incidente ativo, aprovação ou execução pendente e estado
  operacional desconhecido recusam a troca. A resposta preserva o perfil vigente
  e fornece motivo curto. Histórico encerrado não impede a troca.
- Perfil aplicado, executor, disponibilidade, atualização e bloqueios são eixos
  separados. Perfil M2/M3 não comprova execução ou contenção.
- Parada de emergência permanece disponível independentemente da troca recusada.
- Cada decisão conserva o perfil histórico; alterar o perfil atual não reescreve
  decisões anteriores. Simulação pertence ao ensaio, sem quarto perfil. Avaliar
  um registro não altera sua origem nem produz estado global de ataque.

## Indicador de casos

O indicador independe do perfil. “Sem casos ativos” exige evidência atual e
suficiente. Visibilidade insuficiente resulta em desconhecido/parcial. Perda
de comunicação preserva o ataque conhecido até encerramento explícito; a idade
da observação e a disponibilidade devem permanecer visíveis separadamente.

## Contrato reutilizado de controles

Rotas existentes, autenticadas: `GET/PUT /api/v1/security/settings/mode/default`,
`POST /api/v1/security/emergency-stop`, `GET /api/v1/security/audit`.
Aplicar mantém o corpo existente: `value` canônico com `autonomy_mode: 1|2|3`,
`operation` e `execution_enabled`, mais `expected_revision` e `reason`.
M1/M2/M3 são exclusivamente `autonomy_mode`; o campo legado `operation=SIMULATION`
descreve o executor de ensaio e não cria um quarto perfil. A avaliação de registros
não deve chamar Aplicar nem modificar esse campo.

A resposta mantém os campos legados e acrescenta `effective_state`:
`applied_profile`, `control_revision`, `executor`, `availability`,
`execution_enabled`, `updated_at`, `operational_visibility`, `blockers`,
`change_allowed`, `containment_confirmed`. Nesta composição sem executor real,
contenção permanece falsa; disponibilidade não é inferida de M2/M3.
Recusa HTTP 409 mantém `code/message/pending/current_revision` e acrescenta
`current`, a mesma representação do estado vigente (sem executar nova consulta
da autoridade). A recusa é auditada e não altera a revisão vigente.

O adapter existente `queue.snapshot(tx)` fornece `{reliable: bool, blockers:
[{id, state}], dependency?: str}`. `reliable=true` significa cobertura atual e
completa de atividade e pendências, não apenas lista vazia de projeções. Todos
os escritores autoritativos precisam usar `Controls.decision_transaction` e a
conexão recebida, com o mesmo advisory lock PostgreSQL `72611027`. Sem isso, a
integração deve permanecer não confiável. O adapter e os produtores de atividade
pertencem à entrega Backend Data, não a um serviço novo.

`decision_transaction` fornece `current.historical_profile` com
`applied_profile/autonomy_mode/control_revision/control_updated_at`; o produtor
deve persistir essa cópia na decisão. O simulador existente persiste a cópia no
resultado junto de `trial.simulated=true`, sem alterar incidente/origem global.
Decisões antigas sem snapshot não devem receber retroativamente o perfil atual.

### Casos, frescor e encerramento explícito

GET de controles e `operational_controls` no health incluem `cases`:

```json
{
  "status": "unknown",
  "known_active_count": 0,
  "count_basis": "source_item",
  "coverage": "unknown",
  "sources": [],
  "items": []
}
```

`status` é `active`, `none_active`, `partial` ou `unknown`. Somente `none_active`
autoriza o texto “Sem casos ativos”. `active` tem precedência sobre perda de
cobertura; `coverage` continua mostrando `complete/partial/unknown` separadamente.
Zero itens conhecidos com cobertura desconhecida não comprova ausência. Quando
o adapter inteiro está indisponível, `known_active_count=null` explicita a ausência.
As fontes de casos são `incident` e `anomaly`; um ataque deve ter vínculo real
com o item do produtor, nunca um seletor global. Aprovação/execução/verificação
bloqueiam a troca, mas não inflam a contagem de casos.

Cada fonte informa `source/source_revision/observed_at/fresh/valid/complete`.
Cada item ativo informa `source/record_id/source_revision/state/fresh`; somente
se o produtor fornecer revisão real do item haverá `record_revision`. Não
inventar essa revisão a partir da revisão do snapshot. `known_active_count`
conta itens por fonte; não é contagem deduplicada de incidentes entre fontes.
Deduplicação exige vínculo explícito de IDs que ainda pertence ao produtor.

A validade atual usa o prazo existente de 30 segundos. Itens ativos de relatório
vencido continuam em `items` e `blockers`. Um produtor não pode substituir ativo
por snapshot vazio: `report` recusa `ACTIVE_ITEM_REQUIRES_CLOSURE`. Deve publicar
o mesmo ID com estado encerrado e revisão de snapshot maior; depois esse histórico
pode ser omitido. `UNKNOWN`, fonte ausente, inválida ou vencida torna a autoridade
não confiável e Aplicar recusa. Nenhuma rota browser publica esses snapshots.

`effective_state.executor_state` informa `not_integrated/available=false`,
`observed_at=null/source=null` e bloqueio `REAL_EXECUTOR_NOT_INTEGRATED` nesta
composição. É uma ausência explícita: nenhum serviço executor real foi inventado,
nem um heartbeat de PostgreSQL/MQTT tratado como prontidão de contenção.

Parada não consulta a autoridade operacional: sua resposta marca a visibilidade
de casos `unknown`, não encerra nenhum item e nunca retorna `none_active` por
inferência. O consumidor deve conservar os fatos ativos já conhecidos até uma
leitura autoritativa com encerramento; GET subsequente continua vendo esses itens.

### Empacotamento e aceite por runtime

Não há dependências novas nesta entrega. `delivery` já integra o congelamento
Windows (`--collect-all delivery`) e a cópia Ubuntu; a migração existente
`002_operational_authority.sql` já é executada por `prepare_database` e incluída
em ambos os pacotes. Não há novo serviço, variável de configuração, cron ou
comando de manutenção para o usuário final. Os produtores reais ainda precisam
ser conectados pelos responsáveis: não criar um serviço de heartbeat que declare
atividade vazia sem observar as fontes. Sem integração o painel mostra cobertura
desconhecida e a troca permanece recusada.

O ensaio `packaging/native/acceptance_controls.py` usa cluster PostgreSQL nativo
descartável, porta própria e o provisionamento compartilhado dos instaladores,
incluindo repetição de configuração. Testa contratos HTTP autenticados, transações,
recusa auditada, concorrência entre conexões, histórico e perda de comunicação.
Não registra serviços nem altera instalação existente. Evidência sanitizada:
[resultado](evidence/control-state/native-postgresql.json) e
[testes](evidence/control-state/tests.txt).

| Alvo de aceite | Evidência desta entrega | Falta para aceite completo |
| --- | --- | --- |
| Prévia 5174 | Preservada em a8fef1f; contrato alinhado com Codex | Integrar commit em prévia isolada e validar telas com casos/frescor reais |
| Windows nativo | PostgreSQL sem Docker, provisionamento/configuração repetida, HTTP e concorrência | Novo EXE, máquina limpa sem Docker, instalação, reboot, serviços automáticos e login admin no painel sem comandos |
| Ubuntu nativo | Código e dependências existentes contemplam o módulo e SQL | Novo .run, execução Ubuntu limpa sem Docker, instalação, reboot, serviços automáticos e login admin no painel sem comandos |

O resultado não homologa executor real, contenção nem os novos instaladores.

## Matriz de aceitação para as entregas coordenadas

| Cenário | Resultado exigido |
| --- | --- |
| Selecionar outro perfil | Execução e perfil aplicado inalterados |
| Atividade surge após leitura da tela | Aplicar recusa e mantém vigente |
| Aplicar concorrente com início de atividade | Serialização sem janela desprotegida |
| Duas aplicações concorrentes | Revisão/ordem explícita, sem perda silenciosa |
| Apenas casos encerrados | Não bloquear por histórico |
| Estado operacional indisponível | Recusa com motivo curto |
| Recusa e parada de emergência | Parada continua independente |
| Comunicação perdida após ataque | Ataque conhecido permanece |
| Sem casos com cobertura insuficiente | Desconhecido/parcial |
| Avaliação de ensaio | Origem, perfil histórico e estado global preservados |

Reutilizar contratos e serviços existentes. A matriz é critério de aceite,
não declaração de testes executados. Backend Data e Codex devem fornecer commits,
comandos, resultados e lacunas antes de integração e publicação.

## Dependências nativas do produto

Inventário conferido no código de `packaging/native` da base preservada:

| Alvo | Componentes instalados/requeridos | Serviços do produto |
| --- | --- | --- |
| Windows 11 x64 | Runtime Python congelado, frontend compilado, PostgreSQL 18.4, Mosquitto 2.1.2 no modo local, WinSW 2.12.0, Microsoft VC++ x64; payload incluído no EXE | HarpiSensePostgres, HarpiSenseApi, HarpiSenseMqtt; HarpiSenseBroker apenas no modo local |
| Ubuntu 24.04 x86_64 | Python 3.12/venv, wheels incluídos, frontend compilado, postgresql-16, ca-certificates, python3-pip; mosquitto no modo local. Instalação requer acesso aos repositórios Ubuntu | harpisense-postgres, harpisense-api, harpisense-mqtt; harpisense-broker apenas no modo local, via systemd |

O usuário final não precisa de Docker, WSL, VS Code, Node ou Vite. No modo
externo, o broker TLS/ACL deve estar disponível e autorizado; o instalador não
administra serviços de terceiros. Instalação exige administrador; uso diário
ocorre pelo navegador e serviços automáticos. A central usa API loopback 18080,
PostgreSQL loopback 15432 e broker local TLS loopback 8883. Sensores em outra
máquina exigem conectividade e configuração TLS/ACL próprias.

Fontes: [instaladores](../packaging/native/README.md),
[Windows](../packaging/native/windows_setup.py),
[Ubuntu](../packaging/native/ubuntu_install.py). Inventário de código não
substitui homologação em alvo limpo nem comprova defesa/contenção operacional.
