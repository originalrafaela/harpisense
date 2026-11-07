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
