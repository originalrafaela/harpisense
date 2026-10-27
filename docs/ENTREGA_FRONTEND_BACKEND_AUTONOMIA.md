# Primeira entrega frontend/backend — 27/10/2026

Implementação local, sem implantação na VM. Branch `feat/frontend-backend-autonomia`.

## Base e continuidade

Worktree: `harpisense-worktrees/frontend-backend-autonomia`. Base registrada:
`integration/harpia-deterministic`, commit `c2eaed6010d370c3403cb5a188a50893186c5a60`.
Essa base contém as integrações anteriores de frontend/P11 (`280bab4`), HarpIA UI
(`2fbb15c`) e adaptador determinístico (`bd6f6ac`). Não foi usada a main como se todas
as entregas estivessem integradas. Os assets de marca são idênticos aos da branch
`frontend/harpisense-v2` (`f52d837`); preservados nesta entrega.

O Store PostgreSQL foi trazido de `fix/p11-postgres-pagination`,
`70ab0794074569922113b9ce88dfd8b93abfc16e`, arquivo
`backend/p11_postgresql/postgres_store.py`. Adicionado timeout de conexão de 5 s.
Não houve merge integral dessa branch: ela não contém o restante da integração UI.

A inspeção inicial encontrou mudanças locais em `integration-p11` (CSS),
`integracao` (documentação, MQTT, scripts e Docker), `edge-security` e `iot-mqtt`
(progresso). Esses arquivos foram preservados. A main tinha documentos e referências
não rastreados e estava um commit atrás de origin/main. Nenhuma dessas alterações foi
incluída ou sobrescrita. Algumas entradas antigas de worktree eram `prunable`, mas
existiam diretórios locais correspondentes; não foi executado prune.

Especificação lida localmente:
`referencias/versão_v2/HarpiSense_Mudancas_Consolidadas_Frontend_Backend.pdf`.
SHA-256: `59c50ae0fde187a372f99b8148ad8cf92374897c7801d588125b5abb7fdb6253`.
Nenhum acesso ao Drive foi presumido ou realizado.

Referências reutilizadas:

- P03 V2, `base_consolidada_atualizada`: catálogo, contratos, Risk, Policy e preflight.
  Código instalado uma única vez em `backend/domain`; origens e hashes originais em
  `backend/domain/ORIGINS.json`. O snapshot equivalente de P09 V2 não foi duplicado.
- P11 V2: `backend11/service.py`, adaptado em `backend/delivery/projections.py`:
  mesmo envelope, rotas, HTTP Basic e proteção de ingestão por token de serviço;
  removido o Store SQLite de referência e qualquer caminho de geração BitNet.
- “Versões corretas”: Backend Operacional, Controle de Execução, Gerenciador de
  Execução e Defense Executor refatorado foram localizados e inspecionados. Existem,
  mas seus escritores/filas SQLite e APIs isoladas não constituem uma fila integrada
  ao P11 instalado. A URL de settings e o envelope versionado do Backend Operacional
  foram reaproveitados. Não foram montadas as rotas antigas de escrita/aprovação que
  ainda não participam da coordenação de transições.
- O gate de simulação adapta o fluxo IDS/SIMULATION do Controle de Execução, usando
  o validador e preflight canônicos, sem repetir catálogos ou permitir REAL.

## Implementação e estado efetivo

Há páginas próprias de Anomalias, Logs e auditoria, Configurações, Aprovações e
Defesas. A home preserva HarpIA, resumo de saúde e telemetria; histórico detalhado
de telemetria fica na página de telemetria. Controles avançados ficam em Configurações.
Estado ausente, consulta em andamento, falha, indisponibilidade e lista vazia são
distintos. Dados de prévia nunca são fallback de API.

Uma correção acordada foi aplicada à fonte oficial incorporada:
`harpisense_catalog.AUTONOMY[2]['Medium']='MANUAL'`. M1 exige aprovação em todos os
grupos; M2 permite Low elegível automático; M3 permite todos os grupos elegíveis
automáticos. A versão do catálogo foi elevada para `harpisense.catalog.v2.2026-10-27`;
o fingerprint da Policy muda junto. A cópia de catálogo do frontend foi removida;
`npm run catalog` gera a projeção visual diretamente dessa fonte Python.

`Controls` persiste configurações/revisões e auditoria no PostgreSQL. O lock
transacional compartilhado `72611027` serializa troca e operações de produtores
que adotem `decision_transaction`. A transação usa READ COMMITTED explícito.
Recusas também são persistidas. Revisão antiga gera 409. Falha de persistência ou
coordenação gera 503 e nunca confirmação no navegador.

**Limitação operacional explícita:** a composição padrão usa `UnknownQueue`.
Projeções de leitura P11 não atestam fila vazia. Enquanto os produtores reais não
participarem desse lock e de um snapshot autoritativo completo, PUT de controles
é recusado com `QUEUE_UNVERIFIED`, dependência e auditoria. Não existe flag de
ambiente ou endpoint público para declarar artificialmente a fila confiável.
As transições permitidas e com pendências são verificadas com adaptador isolado
injetado nos testes; isso não equivale a integração da fila da VM.

A parada de emergência autenticada é independente dessa consulta: não chama o
adaptador da fila, desabilita execução e persiste um latch. Não remove regras nem
reverte ações históricas. Retomada após emergência exige incremento próprio.
Alterar M3 preserva `operation` e `execution_enabled`. REAL é recusado na aplicação
e restringido no banco local. Nenhum worker operacional ou adaptador real é iniciado.
O executor de teste produz execução canônica `SIMULATED`, com recibo marcado
`isolated_simulation` e `mitigation_confirmed=false`, protegido por preflight,
revisão e ledger PostgreSQL. Trocar perfil não percorre nem dispara decisões antigas.

## Matriz tela → endpoint → contrato → estado real

Todos os endpoints abaixo exigem o HTTP Basic existente. `P11` significa
`/api/v1/p11`; `security` significa `/api/v1/security`.

| Tela | Endpoint | Contrato | Capacidade nesta entrega |
|---|---|---|---|
| Dashboard / saúde | GET P11/health | Saúde P11 + capacidades HarpIA/controles | Consulta real; PostgreSQL verificado; demais serviços desconhecidos quando não atestados |
| Telemetria | GET P11/telemetry, P11/asset | Envelope P11 id/revision/source/data/created_at | Store PostgreSQL e transporte reais; nenhum coletor novo; origem e horários preservados |
| HarpIA | GET P11/incident, P11/bitnet; GET P11/explain/{id} | Incidente/revisão + contrato determinístico existente | Sem geração operacional; explain só chamado com capacidade determinística explícita; origem exibida |
| Histórico HarpIA | GET P11/bitnet/{id}/history | Revisões P11 | Apenas textos já persistidos; fallback calculado não finge histórico persistido |
| Anomalias | GET P11/detection, P11/incident, P11/evidence | Detection canônica, IF original e referências | Leitura; sem conversão em ataque; revisão administrativa indisponível e declarada |
| Incidentes / IA | GET P11/incident, evidence, decision, detection, xai, risk | Projeções dos contratos P03/P09 | Sem eventos inventados; estado vazio não comprova cobertura de produtores |
| Aprovações | GET P11/approval, P11/decision | Aprovação/decisão projetadas | Consulta; aprovar/rejeitar desabilitados até integrar escritor autoritativo com preflight e lock |
| Defesas | GET P11/decision, execution, verification | Decision/execution canônicos | Leitura; `COMMAND_ACCEPTED` não prova mitigação; executor real não disponível na composição |
| Configurações | GET/PUT security/settings/mode/default | value canônico operation/execution_enabled/autonomy_mode; expected_revision/reason | Persistência real; frontend confirma só resposta válida; fila real desconhecida recusa troca |
| Parada de emergência | POST security/emergency-stop | reason; resposta de controles versionados | Persistida, disponível mesmo sem snapshot confiável de fila; não desfaz contenções |
| Logs e auditoria | GET security/audit?limit&offset | Envelope P11; actor/operation/details/observed_at | Auditoria real de controles e recusas; logs completos dos demais componentes ainda não conectados |
| Tráfego / inventário | GET P11/network_event, P11/asset | Projeções P11 existentes | Leitura, sem captura ou cadastro fictício |
| Laboratório | Catálogo gerado de backend/domain | Catálogo oficial C01–C09 | Consulta estática; não dispara ataques |
| Backup / parâmetros Risk/Policy | Sem API montada nesta entrega | Dependências dos pacotes existentes | Controles indisponíveis; não alegam execução, backup ou configuração aplicada |

## Conferir localmente

Requisitos: Docker Desktop ativo, Node com npm e navegador. A composição cria seu
próprio PostgreSQL 18.6 e volume; não usa os bancos existentes nem a VM.
Não há seeds operacionais. Configure credenciais locais escolhidas por você, sem
reaproveitar ou alterar credenciais de VM. O mecanismo continua HTTP Basic.

No PowerShell, abra a worktree:

```powershell
Set-Location 'D:\Projetos\tcc - harpisense\harpisense-worktrees\frontend-backend-autonomia'
$env:HARPISENSE_LOCAL_DB_PASSWORD = [guid]::NewGuid().ToString('N')
$env:HARPISENSE_ADMIN_USER = Read-Host 'Administrador da instância local'
$localPassword = Read-Host 'Senha da instância local' -AsSecureString
$env:HARPISENSE_ADMIN_PASSWORD = [System.Net.NetworkCredential]::new('', $localPassword).Password
docker compose -f backend/delivery/compose.local.yml up -d --build
Set-Location frontend
npm.cmd ci
$env:HARPI_API_TUNNEL_TARGET = 'http://127.0.0.1:18010'
$env:VITE_P11_RESOURCES = 'all'
npm.cmd run dev
```

Abra **http://127.0.0.1:5174** e use o administrador definido acima. Conexão da API:
`/p11-api`, perfil P11. A prévia visual é uma entrada separada, identificada.
Confira Dashboard, Anomalias, Incidentes, Configurações e Logs/auditoria. Solicite
M3 com justificativa: a instância padrão deve recusar por fila não integrada, manter
M1/IDS/execução false e registrar `CONTROL_CHANGE_REJECTED`. A parada pode ser
testada na instância local; ela permanece ativa e não possui botão de retomada.

O volume PostgreSQL persiste entre reinícios. Guarde a senha local em gerenciador
seguro ou arquivo `.env.delivery` ignorado, usando `--env-file .env.delivery` nos
comandos compose. Não gere outra senha para um volume já inicializado.
Para encerrar: Ctrl+C no Vite e, na raiz, `docker compose -f backend/delivery/compose.local.yml stop`.
Esse comando preserva os dados. A migração `001_local.sql` é bootstrap local;
reconciliação com o esquema instalado e migração de estado da VM são próximas etapas.

Alternativa sem container de API: instale `backend/delivery/requirements.txt` em
venv própria, aponte `DATABASE_URL` para PostgreSQL isolado com a migração aplicada
e execute `backend/delivery/run-local.ps1 -Python <python-da-venv>`.

## Validação executada e limites

Validação nesta máquina Windows, PostgreSQL 18.6 em Docker isolado e Chromium headless:

- `npm run build`: TypeScript + bundle Vite aprovados.
- `npm test`: 28 testes aprovados, incluindo HTTP Basic, API inválida/indisponível,
  telemetria, HarpIA, contrato de controles e proxy Vite real.
- `npx playwright test`: 26 testes de navegador com fixtures aprovados.
- `local-composition.spec.ts`: 1 fluxo adicional aprovado sem mock HTTP, usando
  Vite → API FastAPI em container → PostgreSQL local: login, saúde, recusa M3 por
  pendência desconhecida, auditoria persistida e anomalias vazias/mobile.
- `backend/delivery_tests`: 18 testes, incluindo 4 com PostgreSQL, aprovados.
  A matriz de 27 combinações está dentro de um dos testes. Cobrem autorização,
  elegibilidade/refusa automática M3, fila desconhecida, pendências, revisão,
  concorrência, rollback, nova instância do repositório e simulação idempotente.
- Regressão `genai/tests/test_deterministic_integration.py`: 5 testes aprovados.
- Imagem Docker construída e composição local iniciada com sucesso.

Os snapshots de fila confiável são fixtures isoladas. Nenhum teste comprova fila
real integrada, execução/eficácia de firewall ou coleta na VM. Não foi realizada
validação nem implantação na VM nesta rodada. Não houve ataque, coletor novo,
alteração P08/P09, credencial de VM, rede/nftables, instalação Qwen ou ativação BitNet.

Para repetir backend, instale requirements-test em uma venv e, da raiz, defina
`PYTHONPATH=backend;backend/domain;genai` no Windows. Execute:

```powershell
python -m unittest discover -s backend/delivery_tests -v
python -m unittest discover -s genai/tests -p test_deterministic_integration.py -v
```

Os quatro testes PostgreSQL exigem `TEST_DATABASE_URL` apontando para banco
**descartável dedicado**: eles limpam tabelas de controles desse banco. Nunca use
DSN de VM/produção. O teste browser sem mocks é opt-in: defina
`HARPISENSE_COMPOSITION_TEST=1`, `HARPISENSE_TEST_ADMIN_USER`,
`HARPISENSE_TEST_ADMIN_PASSWORD` e `HARPI_API_TUNNEL_TARGET` da instância local;
execute apenas `npx playwright test tests/local-composition.spec.ts`.

## Dependências restantes

1. Integrar os escritores reais de Policy, aprovação, fila, worker, resultado e
   reversão à mesma transação/lock e ao snapshot completo de pendências. Só então
   habilitar troca operacional; não usar limite/paginação de projeções como prova.
2. Reconciliar/importar configuração efetiva preexistente e tabelas PostgreSQL da
   VM, com procedimento de migração e revisão de permissões. O bootstrap local
   inicia M1/IDS/false; não sobrescreve nem declara representar controles da VM.
3. Integrar revisão administrativa de anomalias com persistência, autor, evidências,
   vínculos e histórico separados dos resultados originais RF/IF.
4. Adaptar as operações existentes de aprovar/rejeitar/cancelar à fila canônica,
   revalidando ação, fingerprint, incidente/revisão, alvo, política e prazo.
5. Conectar trilhas dos demais componentes e produtores de detecção/incidentes;
   sem isso, listas vazias não indicam monitoramento completo.
6. Conta/sessão/MFA, retomada pós-emergência, backup e gerenciador de configuração
   permanecem entregas próprias. Execução REAL continua bloqueada.
