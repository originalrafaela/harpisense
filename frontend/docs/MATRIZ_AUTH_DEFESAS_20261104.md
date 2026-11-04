# Matriz frontend: autenticação, incidentes e defesas

Base desta entrega: `feat/frontend-auth-defense-v2` em `9d35906cc46a35a1d5e80c27243e75aef69d7b58`. A base já contém a integração do gerenciador feita em `40908b3`; ela foi preservada.

## Cobertura

| Tela/fluxo | Endpoint e contrato | Estado |
|---|---|---|
| Login administrativo | `POST /api/v1/admin-auth/login`; resposta Bearer validada por `GET /api/v1/admin-auth/session` | Integrado no cliente existente; token apenas em memória. |
| Sessão e saída | `GET /api/v1/admin-auth/session`, `POST /api/v1/admin-auth/logout` | Integrado e preservado. A resposta de sessão informa `mfa_available=false` e `email_recovery_available=false`. |
| Primeiro provisionamento | Nenhuma rota HTTP; provisionamento local do operador | Indisponível na interface, sem criar conta ou declarar primeiro acesso. |
| MFA e recuperação | Nenhuma rota de setup/verificação TOTP, códigos ou recuperação | Indisponível na interface. O status explica a ausência; abrir o fluxo não envia chamadas. |
| Incidentes | `GET /api/v1/p11/incident?limit=&offset=` e `GET /api/v1/p11/incident/{id}/history` | Lista, seleção, payload e revisões conectados ao P11. Erro, histórico vazio e demo ficam distintos. |
| Evidências e decisões associadas | `GET /api/v1/p11/evidence`, `GET /api/v1/p11/decision` | Exibidos apenas quando os vínculos (`evidence_refs`, `incident_id`) estão presentes nos registros. |
| Fila de aprovações | `GET /api/v1/p11/decision`, `GET /api/v1/p11/approval` | Somente leitura. Estado da fila vem do `decision.status` canônico; aprovações são registros associados por `decision_id`. |
| Acompanhamento de defesas | `GET /api/v1/p11/decision`, `/approval`, `/execution`, `/verification` | Proposta, aprovação, execução e verificação exibidas separadamente a partir de projeções. |
| Aprovar, rejeitar, alternativa, executar e reverter | Sem operações confirmadas de aprovação/execução no backend | Botões indisponíveis com o motivo. Não há envio de comando nem confirmação operacional. |

Os históricos P11 preservam ordem de revisão, origem e payload; não inferem horário quando ele não é fornecido. A allowlist do proxy local permite apenas `GET` para tipos P11 e IDs validados no caminho de histórico; não aceita query nessa rota.

## Demonstração e validação

Os dados de navegador usam respostas isoladas de Playwright e são testes de interface/contrato, não integração com uma VM. A prévia demonstrativa permanece separada e não envia requisições operacionais.

Pendências do backend: primeiro provisionamento por HTTP, setup/verificação MFA, recuperação por e-mail/códigos, e contratos de escrita para aprovar/rejeitar/substituir defesa e solicitar execução/reversão. A consulta P11 do Poste 2 documentada em 29/10 é simulada; não representa telemetria física nova.

## Retomada pelo Arquiteto

Revisar a branch `feat/frontend-auth-defense-v2`, derivada de `9d35906`, e integrar o commit frontend desta candidata conforme o fluxo do repositório. Arquivos de backend não fazem parte desta entrega.

## Verificações desta candidata

- TypeScript: npm.cmd run typecheck aprovado.
- Testes unitários/contrato: npm.cmd test — 41 aprovados.
- Build: npm.cmd run build aprovado.
- Playwright isolado: 48 aprovados, 1 ignorado; fixtures interceptam as chamadas, sem sessão conectada à VM.
- Consulta da telemetria aceita Poste 2: não realizada nesta sessão por ausência de sessão administrativa operacional; nenhum login foi tentado.
