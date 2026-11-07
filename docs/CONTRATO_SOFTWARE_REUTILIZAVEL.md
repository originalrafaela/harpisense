# Contrato de implementação para Frontend, Gerenciador e Arquiteto

Base local: `integration/install-lab-20261105` em `69ca4dd`; implementação isolada
em `feat/reusable-software`. Maestri indisponível (pipe expirado); nenhuma
confirmação de integração dos outros responsáveis foi obtida. Este documento
publica o contrato para revisão, sem declarar implantação operacional.

## Recuperação de senha

Migração explícita `backend/admin_auth/003_password_recovery.sql` após 001/002.
Mesmo banco, conta, auditoria, lock e throttle PostgreSQL; nenhum DDL no startup.
Prefixo `/api/v1/admin-auth`, JSON, `Cache-Control: no-store`.

| POST | Entrada | Resultado |
|---|---|---|
| `/password-recovery/codes` | Bearer administrativo + `current_password`, `code` TOTP novo | `password_recovery_codes` (10 códigos, exibidos uma vez), `expires_in_seconds` |
| `/password-recovery/validate` | `username`, `code` | `reset_token`, `next_step=reset_password`, `expires_at` |
| `/password-recovery/reset` | `reset_token`, `new_password` | `status=credentials_changed`, `login_required=true`, `sessions_revoked=all` |

Códigos com 256 bits aleatórios, somente SHA-256 persistido, validade de 365 dias.
Reemissão exige sessão, senha e TOTP; invalida códigos anteriores e autorizações
de senha. Consumo serializado e condicional, uma única vez. Autorização de cinco
minutos, exclusiva para senha, não aceita em sessão, inscrição MFA ou ingestão.
Conclusão incrementa revisão de credenciais e revoga sessões, challenges e grants.
TOTP e códigos do autenticador não são alterados. O login seguinte exige nova
senha e TOTP. `RECOVERY_INVALID`/401 é comum a conta ausente, nome incorreto,
código usado/expirado e autorização inválida. Throttle global persistente devolve
429/`TRY_LATER` com `Retry-After`. Não registrar bodies, Authorization ou respostas
de emissão no proxy/cliente. Não há GET que recupere segredos originais.

O fluxo `/mfa/recover` continua separado: senha + código do autenticador autoriza
apenas novo cadastro TOTP. Códigos de senha não são fatores MFA.

## Ativos

Migração aditiva explícita `config_manager/003_assets.sql`. Rotas com sessão
existente em `/api/v1/config/assets`. Identidade da instalação vem do servidor.
GET lista ativos; PUT `/{technical_id}` cria com `expected_revision=0` ou altera
com revisão corrente; GET `/audit` lista auditoria por cursor `after`.
Documento: `display_name`, `asset_type`, `profile`, `location`/`group` opcionais,
`bindings` (mapa de papéis connection/sensor/gateway para identificadores).
Perfil e vínculos devem pertencer ao manifesto confiável fornecido pelo instalador.
Sem manifesto compatível a gravação falha; cliente não aprova capacidades.
Identificador técnico é imutável no cadastro; nome pode ser corrigido sem tocar
em `device_id`, tópicos, telemetria ou projeções anteriores. Registro retorna
`registered=true`, `connectivity=unknown`, `capture=unknown`, `defense=unknown`.
Esses estados exigem observação própria; o cadastro não os habilita.
409 para revisão/identificador conflitante; 422 para incompatibilidade.

## Estado operacional e dados

`GET /api/v1/security/settings/mode/default` mantém valor efetivo e revisão.
`effective_profile` é o valor vigente; `blocking_reasons` lista QUEUE_UNVERIFIED,
OPERATIONAL_PENDING e EMERGENCY_STOPPED quando aplicáveis. Propostas do
Gerenciador permanecem separadas. A ausência de adaptador autoritativo de fila
é `QUEUE_UNVERIFIED`; ler projeções não certifica fila vazia. O adaptador deve
participar do mesmo lock/conexão de Controls.decision_transaction, incluindo
anomalias/incidentes ativos, aprovações, execuções e reversões; estados não
reconhecidos impedem aplicação. Histórico encerrado não constitui pendência.
M1/M2/M3, gates, bloqueio REAL e parada de emergência permanecem preservados.

Sessão já fornece `username`. Consultas P11 existentes distinguem asset,
detection (RF/IF), incident, evidence, network_event, decision, approval,
execution e verification, com histórico por entidade. Consultas não autorizam
aprovar ou executar.

`GET /api/v1/interface/incidents/{id}` agrega incidente, detecções RF/IF, evidências,
network_event_refs explícitos, decisões da revisão exata, aprovações, execuções e
verificações relacionadas. Retorna `unresolved` para referências ausentes ou
mutáveis sem revisão fixada, `log_references` para ponteiros de evidência e
`commands.approval_available=false/execution_available=false`. Não há endpoint
para ler arbitrariamente arquivos de log. Resultados conservam seus estados e
contratos originais, sem equiparar uma decisão à execução confirmada.

`GET /api/v1/p11/explain/{id}` mantém o adaptador HarpIA determinístico existente
e persiste a explicação, revisão e fingerprint no mesmo PostgreSQL (migração
explícita `delivery/003_interface.sql`). Repetir a mesma explicação é idempotente.
`GET /api/v1/interface/incidents/{id}/harpia?limit=100&before=ID` retorna `history`
paginado e `latest_three`, em ordem decrescente de emissão. Fonte continua
deterministic_fallback; não há inferência BitNet nova. História prévia não
persistida não é reconstruída nem inventada.

`delivery.operational_queue.AuthorityQueue` recebe callables confiáveis por domínio
(anomaly/incident/approval/execution). Cada um recebe a conexão sob o lock vigente
e devolve `{reliable:true, items:[{id,state}]}` completo. Ausência, falha ou estado
não reconhecido bloqueia aplicação. Não aceita atestado por HTTP. CLOSED encerra
incidente/anomalia; DENIED/EXPIRED/CONSUMED/CANCELLED encerram aprovação;
SIMULATED/UNAVAILABLE/FAILED/EXPIRED/REVERSED encerram execução. Mitigação ainda
vigente e reversão falha permanecem bloqueantes. Fontes reais precisam ser ligadas
pelos proprietários dos produtores; projeções P11 não são autoridades.

## Composição e validação

Registrar separadamente implementação, composição candidata, testes reais e
integração/implantação aprovada. Pendências do Arquiteto: manifesto de perfis e
vínculos, adaptador operacional autoritativo, endpoints de comando aprovados,
composição no instalador e integração dos formulários no Frontend. Não há
autorização implícita para alterar broker, rede, captura ou contenção.

Composição candidata: `delivery.app.build_candidate_app(..., protection_key=...,
asset_catalog=..., operational_sources=...)`. Chave MFA vem do arquivo protegido
existente. Catálogo: `{(asset_type,profile): {(role,id),...}}`, fornecido pelo
instalador. `operational_sources` ausente mantém o bloqueio seguro. Executar
migrações com o proprietário SQL antes de iniciar; runtime recebe SELECT/INSERT/
UPDATE nos cadastros e grants, DELETE nos códigos para reemissão, INSERT/SELECT
nas auditorias/histórico e USAGE nas sequências. Não conceder UPDATE/DELETE às
auditorias ou histórico. OpenAPI exportável por
`python backend/scripts/export_reusable_contracts.py`, sem conexão com o banco.
