# Inspeção inicial

- Branch histórica integration/primeira-entrega em `harpisense-worktrees/integracao`: worktree com alterações locais em docs/lab/mqtt/tests e arquivos Docker não rastreados; preservada. Registro worktree antigo apontava caminho externo prunable, embora a cópia local tenha gitdir. Não utilizar como integração moderna implicitamente.
- Nova integração real desta tarefa: `harpisense-worktrees/initial-auth-integration`, branch `integration/initial-auth-20261108`, base `2345808` de feat/backend-incident-shap-integration. Esta possui CasesV2, first_access e composição nativa recentes.
- Quatro frentes inspecionadas: backend-incident-shap-integration (2345808, JSON live-backend não rastreado preservado); frontend-operational-review (d2d53b5, limpa); native-installers (9cd930c, limpa); local-activation (9cd930c, limpa no snapshot). Novos trabalhos de outros agentes não serão sobrescritos.
- Base comum das fontes backend/frontend/instalador: a8fef1f5810ad5077658a29fe2aa407ffd21df6d.
- Auth: backend/admin_auth/{service,mfa,candidate,first_access,http_contract,passwords}.py e 001_admin_auth.sql,002_admin_mfa.sql,003_password_reset.sql,004_first_access.sql. Existente usa scrypt, dois conjuntos10, rotas de recadastro MFA por código/grant: incompatibilidades a migrar explicitamente.
- Interface: frontend/src/account-mfa.tsx (Grant local), api.ts, password-recovery.tsx, main.tsx; frontend-operational-review inclui primeiro acesso/modal dentro de account-mfa.tsx e testes próprios.
- Instaladores: packaging/native/{entry,provision,windows_setup,ubuntu_install,build_windows,build_ubuntu}.py, requirements.txt/runtime-windows.lock; integração backend/native_server/runtime.py; proteção e handoff precisam adaptação.
- Contratos anteriores: docs/FIRST_ACCESS_AUTH_CONTRACT_20261107.md (backend), docs/ADMIN_MFA_*, docs/CONTRATO_FRONTEND_GERENCIADOR_20261101.md; contrato desta tarefa em INITIAL_AUTH_CONTRACT_V1.md tem precedência para o novo fluxo, não altera contratos MQTT.
- Nenhum segredo lido/exposto, nenhum banco ou serviço de produção alterado.
