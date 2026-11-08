# Revisão operacional do frontend — 07/11/2026

## Prévia para revisão visual

- URL desta worktree para revisão: `http://127.0.0.1:5176/`
- `http://127.0.0.1:5175/` foi preservada e não reiniciada; ela não foi usada como origem do código modificado nesta rodada.
- Worktree: `harpisense-worktrees/frontend-operational-review`
- Branch: `feat/frontend-operational-review`
- Base visual: `a8fef1f5810ad5077658a29fe2aa407ffd21df6d`
- HEAD antes do commit desta revisão: `89d40eedfcbcb0c8200991f310ebaad89248c9da`
- A rota de demonstração mostra o aviso permanente “Prévia visual — dados de demonstração, sem ações reais.”
- O teste visual observou zero requisições de API durante a demonstração. Nenhum dado da prévia comprova funcionamento operacional.
- A porta `5174` continuou respondendo e não foi reiniciada nem substituída.
- Capturas: `docs/evidence/review-dashboard-final-20261107.png` (referência anterior) e `docs/evidence/dashboard-review-current-20261107.png` (esta worktree, apenas demonstração).
- Captura cases V2: `docs/evidence/dashboard-cases-v2-fixture-20261108.png`, com selo visível de fixture controlada; não representa resposta do serviço ao vivo.

## Escopo visível nesta prévia

- Faixa superior com seleção local de M1/M2/M3, estado efetivo, cobertura de casos e parada de emergência independente.
- Recusa HTTP 409 preserva o estado vigente no cliente; a seleção continua utilizável. As operações demonstradas não enviam comandos reais.
- Estado efetivo explicita executor não integrado, disponibilidade, atualização e bloqueios sem inferir contenção a partir do perfil.
- HarpIA vinculada ao incidente selecionado; campos históricos não são inferidos do perfil atual; execução ausente aparece como “Sem registro de execução”.
- Análise XAI sem explicação disponível na demonstração, sem gráfico ou métricas fabricados.
- Incidentes, aprovações, defesas e demais páginas continuam dependentes da API existente ou mostram exemplos identificados na prévia.

## Modal pós-MFA e códigos de recuperação

- O contrato de primeiro acesso está publicado pelo Backend no commit `071d052`, ainda candidato e não instalado. O frontend usa a sessão existente, `username` e `first_access` persistido por conta; não cria outra autenticação.
- Depois de uma sessão completa com `first_access.status=pending`, o dashboard é montado primeiro; o modal central é uma camada sobre ele. A entrada do `InstallationEntry` continua montada por trás, com as ações existentes de iniciar/retomar o gerenciador.
- `recovery_codes` e `password_reset_codes` são mantidos em memória e em seções separadas, apenas a partir da resposta de emissão. O rótulo de redefinição é exclusivo para `password_reset_codes`; recuperação TOTP serve apenas para novo cadastro de autenticador.
- O modal chama `POST /api/v1/admin-auth/first-access/confirm` com apenas a geração mostrada, depois da confirmação do administrador, valida sessão/estado completed e só então some. `GET /api/v1/admin-auth/session` dirige o comportamento nos próximos logins; completed não abre novo modal.
- Após reload pendente, o frontend não tenta ler os originais. `POST /api/v1/admin-auth/first-access/codes` solicita senha atual e TOTP ainda não usado, recebe os dois novos conjuntos e a nova geração; o servidor invalida ambas as listas anteriores atomicamente. Em conflito 409, as listas antigas são limpas e a UI exige nova emissão.
- Escape e clique no fundo não fecham o modal; foco fica retido. Copiar/baixar são decisões explícitas. Nenhum código é enviado em URL ou gravado em localStorage, sessionStorage ou IndexedDB. Logout/expiração desmonta o estado em memória.
- `GET /api/v1/admin-auth/first-access` também está ligado para releitura do estado por conta após conflito. No runtime nativo o caminho continua sendo mediado pelo cliente existente sob `/p11-api`.
- `InstallationEntry` permanece a única entrada do Gerenciador existente; não foi criado wizard paralelo nem conclusão obrigatória do assistente.

## Integração e limites

O ciclo administrativo de primeiro acesso/MFA foi validado por navegador → proxy P11 → API candidata `071d052`, usando o runner nativo Windows de desenvolvimento e o estado de conta persistido pelo serviço. Isso comprova a integração HTTP candidata de autenticação e a retomada de `first_access` após reload/logout/login; não é aceite do software instalado. O Codex não consultou PostgreSQL diretamente nem verificou o estado após reiniciar o runner. As demais consultas P11, XAI, controles de operação e configuração não foram validadas contra esse runner: seus testes de navegador nesta rodada usam fixtures. Aprovação, execução e reversão continuam indisponíveis sem operação autorizada confirmada.

O contrato operacional de casos V2 está em `docs/CASES_V2_CONTRACT_20261107.md`; o Backend confirmou o runner em `feat/backend-incident-shap-integration`, commit `6637781b067a6ad931f05106914e37ea98363d1c`. A interface lê `cases` do `GET /api/v1/security/settings/mode/default` e de `GET /api/v1/p11/health` (`operational_controls.cases`). Usa `distinct_incident_id`, mantém as contagens de classes separadas e sobrepostas, preserva casos conhecidos em fonte stale e só mostra “Sem casos ativos” quando V2 retorna `none_active`, cobertura completa, `observation_sufficient=true` e `total_active_count=0`. Frescor vem dos campos e motivos das fontes no backend; não há TTL local para casos. O snapshot V1 do runner anterior é rotulado como contrato V2 ausente/estado desconhecido. Os links de ficha usam o `links[].path` e a revisão fornecidos; não são derivados dos IDs de fatos fonte.

As oito fixtures sanitizadas publicadas pelo Backend foram copiadas para `tests/fixtures/cases-v2/` para testes locais identificados, incluindo recusa de mudança de perfil com o snapshot corrente. Elas são fixtures HTTP controladas, não tráfego operacional. O runner V2 agora ativo é `http://127.0.0.1:18083`, commit Backend `6637781b067a6ad931f05106914e37ea98363d1c`; o runner antigo `18082` foi preservado em V1. A prévia 5176 usa `HARPI_API_TUNNEL_TARGET=http://127.0.0.1:18083`; o GET da sessão sem autenticação via proxy/origem 5176 respondeu 401 esperado, e a conexão do proxy ao destino 18083 foi observada, sem credenciais. A sessão autenticada necessária para consultar Cases V2 não estava disponível; não fiz login por tentativa nem usei grants/tokens. Portanto os testes V2 navegador → API autenticada → PostgreSQL continuam pendentes. A equipe Backend informa 14 testes PG/HTTP aprovados e evidências de restart/upgrade do processo com o mesmo banco preservando first_access/MFA/setup; isso não valida um novo login no navegador após restart, draft de configuração salvo, reboot de sistema instalado ou app Microsoft Authenticator. O contrato operante consulta PostgreSQL, mas as fontes de casos não têm cobertura certificada: não declarar ausência de casos/ataques nem inventar “Sem casos ativos”. O executor real continua explicitamente não integrado/disponível; M2/M3 não comprovam contenção. M1/M2/M3, IDS/SIMULATION/REAL, `execution_enabled`, executor e parada de emergência permanecem separados.

Ainda dependem de integração backend/produtores: cobertura autoritativa completa dos casos sob o lock contratual; vínculos reais para deduplicação entre anomalias/incidentes; persistência do perfil histórico em cada decisão; e executor real. A integração MQTT observacional é separada e não comprova publicação de telemetria nem ausência de casos.

## Verificações desta revisão

- `npm.cmd run typecheck` — passou após a integração V2.
- `npm.cmd test` — 72 passaram, 0 falharam, 0 ignorados. Inclui parsing das oito fixtures, regras de contagem/zero/cobertura, preservação do ataque conhecido, validação do vínculo ID/revisão, marcador de cobertura e recusa 409 preservando snapshot/perfil vigente.
- `npx.cmd playwright test --config tests/cases-v2-ui.playwright.config.ts` — 2 passaram; dashboard/Incidentes, GET da ficha exata, estados parcial e zero suficiente. Respostas interceptadas por fixtures; captura única do dashboard com selo de fixture; vídeo/trace desligados; nenhuma chamada de navegador ao Backend.
- `npx.cmd playwright test --config tests/recovery-modal.playwright.config.ts` — 14 passaram anteriormente com fixtures HTTP isoladas. Inclui operações do assistente, retomada após navegação/reload, instalação sem ativo presumido, seletor/recusa/emergência e primeiro acesso.
- `npm.cmd run build` — passou; 54 módulos transformados.
- `git diff --check` — passou.
- Revisão headless anterior: 1440×1000 e 390×844; controles sem sobreposição e zero chamadas `/api/v1/` na prévia visual.
- `npm.cmd run build` — passou.
- Não foi feita validação Windows/Ubuntu em instalação limpa, reinicialização, serviço automático ou API/PostgreSQL operacionais.
- Ensaio E2E real em browser `5176` → proxy P11 → runner candidato `18082`: bootstrap `200`, início e confirmação MFA `200`, sessão autenticada `200`, login e verificação MFA `200`, emissão/reemissão dos códigos `200`, confirmação da geração `200`, logout `204` e novo login/consulta de sessão `200`. Após logout/login, `first_access=completed` manteve o dashboard sem reabrir o modal. O fluxo chegou ao serviço nativo candidato com persistência configurada pelo Backend; o Codex não consultou PostgreSQL diretamente nem validou reinício do serviço.
- Durante o ensaio, os dois conjuntos tinham dez itens cada e rótulos distintos. Verificação no navegador confirmou que nenhum código estava na URL ou em localStorage/sessionStorage; saídas do teste contêm somente nomes de rota, status HTTP e contagens de armazenamento. Não foram produzidos screenshots, vídeos, HAR ou traces de telas de autenticação. O TOTP foi calculado localmente a partir da chave mostrada na tela; isso valida o protocolo HTTP/TOTP candidato, não o aplicativo Microsoft Authenticator.
- O grant foi lido localmente, usado apenas no runner isolado e não exposto. Nenhuma senha, token, chave TOTP ou código foi incluído no relatório.
- Captura persistida contém somente o dashboard demonstrativo, nunca o modal nem códigos.
- O runner é desenvolvimento nativo Windows, não software instalado. Não valida instalador offline, reboot, serviço/autostart ou runtime Ubuntu.
- `ConfigManager` agora inicia sem linhas de dispositivos; o administrador adiciona uma linha explicitamente. O schema/backend candidato atual suporta apenas o perfil `esp32-lighting`, firmware `esp32-wroom32-lighting` indisponível e aplicador `presentation`; não há contrato para ativos genéricos por rede/sensor nem aplicação real de MQTT/captura.
- O E2E real não validou o Gerenciador. Retomada de rascunho e fluxo fora/volta/reload foram cobertos apenas por fixtures; a API de configuração precisa persistir o rascunho independentemente do estado `first_access`.
- A revisão visual/operacional de XAI ainda depende de registros autenticados com explicadores RF/IF aprovados e suas saídas SHAP reais. O inventário reportado pelo Backend identifica zero artefatos RF/IF aprovados; não declarar SHAP real nem geração BitNet exercitados. Os IDs sintéticos disponíveis são evidência de ensaio, não tráfego operacional.
- A UI foi conferida com fixtures V2 e o proxy atual foi encaminhado ao runner 18083; sem sessão administrativa disponível, não foi feita consulta autenticada real de casos/fichas nem prova navegador → PostgreSQL. O parser rejeita `__coverage__` como caso e mostra a origem imutável conforme cada fato retornado. `cases-live.json` informa `installed:false`; nenhum aceite de sistema instalado/reboot é alegado.

## Acesso local

Na worktree `harpisense-worktrees/frontend-operational-review\frontend`, com dependências instaladas, execute `$env:HARPI_API_TUNNEL_TARGET='http://127.0.0.1:18083'; npm.cmd run dev -- --host 127.0.0.1 --port 5176`. A demonstração depende de `VITE_DEMO_ENABLED=true` em configuração local ignorada pelo Git. A versão em `5176` é a fonte modificada desta worktree; não é software instalado nem comprovação de aceite offline.
