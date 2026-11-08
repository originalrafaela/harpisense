# Primeiro acesso e recuperação por finalidade

Branch `feat/backend-incident-shap-integration`; base `a8fef1f` com integração de
fichas/SHAP independente. Não alterar native-installers nem a prévia 5174.
Implementação publicada no commit `071d052`.

## O que já existia

O módulo `admin_auth.candidate.MFAAdminAuth` já é selecionado por
`native_server.runtime.build_native_app` na base `a8fef1f`.
Os dez `recovery_codes` de confirmação do TOTP são exclusivamente
`authenticator_recovery`: exigem a senha na etapa anterior e abrem somente
recadastro de autenticador, nunca sessão administrativa. Permanecem preservados.
Há um segundo conjunto `password_reset_codes`, aceito exclusivamente em
`POST /api/v1/admin-auth/password-reset/confirm`. Esse fluxo redefine a senha,
revoga sessões e preserva o segredo TOTP; não concede sessão.

## Rotas e resposta para Codex / Configurações

As rotas abaixo usam a sessão administrativa já existente. No runtime nativo,
acrescentar `/p11-api` antes de `/api/v1/...`. Não existe um segundo login.

- `GET /api/v1/admin-auth/session`: `username` persistido da conta e `first_access`.
- `GET /api/v1/admin-auth/first-access`: `{username, first_access}`, sem códigos.
- `POST /api/v1/admin-auth/first-access/codes`: corpo
  `{current_password, code}` (TOTP atual ainda não utilizado). Retorna
  `{username, recovery_codes, password_reset_codes, first_access}` apenas nesta
  emissão; revoga e substitui AMBAS as listas na mesma transação. A rota existente
  `/password-reset/codes` preserva seu propósito restrito: retorna apenas
  `{username, password_reset_codes, first_access}` e substitui somente senha.
- `POST /api/v1/admin-auth/first-access/confirm`: corpo
  `{password_reset_generation: N}`. Retorna `{username, first_access}`;
  repetir a confirmação da geração atual é idempotente.
- `POST /api/v1/admin-auth/mfa/enrollment/confirm`: mantém sessão/campos existentes
  e emite duas listas distintas, `recovery_codes` e `password_reset_codes`,
  com `first_access` pendente e a geração da emissão.
- `POST /api/v1/admin-auth/password-reset/confirm`: mantém o contrato existente
  `{username, code, new_password}` →
  `{status:"password_reset", login_required:true, mfa_preserved:true,
  sessions_revoked:"all"}`. Não retorna `access_token`.

`first_access` tem somente:

```json
{
  "status": "pending",
  "password_reset_generation": 1,
  "password_reset_purpose": "password_reset",
  "codes_issued": true,
  "issued_at": "<timestamp ISO8601 com offset do PostgreSQL>",
  "completed_at": null
}
```

`status` é `pending|completed`. Conta migrada sem emissão nesta versão começa
com geração 0, `codes_issued:false` e horários nulos; exige reemissão, nunca
recuperação de originais. A geração é identificador de conjunto, não um segredo.
Confirmação de geração antiga retorna 409 `FIRST_ACCESS_GENERATION_CONFLICT`.
Conta/usuário não são aceitos no corpo de confirmação: vêm exclusivamente da
sessão. Todas as respostas privadas usam `Cache-Control:no-store` e `Pragma:no-cache`.

## Comportamento da interface

Usar `username` da sessão, sem inventar nome de pessoa. Mostrar onboarding quando
`first_access.status === "pending"`. Mostrar listas apenas da resposta de emissão,
em memória: copiar ou baixar localmente é decisão do administrador. Não colocar
códigos em query string, URL, telemetria, logs, auditoria ou armazenamento do
navegador. O backend não possui rota para reler originais.

Depois de reload pendente, permitir reemitir mediante senha+TOTP. A rota de
primeiro acesso revoga atomicamente ambas as listas anteriores e incrementa a
geração, reabrindo pending. Não há leitura de originais. O
frontend confirma somente a geração que acabou de exibir, depois de o usuário
declarar que guardou. Após completed, o próximo login devolve completed e não
reemite códigos nem requer modal. Reemissão explícita posterior abre nova geração.

Rotular `password_reset_codes` como **Códigos para redefinir sua senha**.
Rotular `recovery_codes` como **Códigos de recuperação do autenticador**.
Cada código satisfaz apenas sua finalidade. Senha nova continua exigindo TOTP.

## Banco e pacote nativo

Migração aditiva `backend/admin_auth/004_first_access.sql` depois de 002/003,
ligada a `packaging/native/provision.py`. Guarda apenas hashes e finalidade,
geração, emissão, uso/revogação; originais são gerados em memória e enviados uma
vez. A reemissão preserva hashes revogados, em vez de apagar o histórico.
`hs_admin_first_access` tem chave estrangeira por conta; o produto continua com
seu contrato existente de uma conta administrativa por instalação.

Reutiliza a transação/lock de autenticação e PostgreSQL existentes. Auditoria
registra somente evento/resultado/conta, sem código, segredo ou senha.
Nenhuma nova biblioteca, serviço, Docker, WSL ou componente de sistema.
Os builders Windows/Ubuntu já coletam `admin_auth` e os SQLs. Será necessário
um pacote novo para aceite instalado; nenhum instalador foi gerado nesta rodada.

## Limites do aceite

Testes nativos de HTTP/PostgreSQL estão em
`backend/admin_auth_tests/test_first_access_native.py`, sem imprimir originais.
Onze testes aprovados. E2E real browser5176 → proxy → API18082 → PostgreSQL
reportado pelo Codex também passou, sem traces/screenshot/vídeo das telas de auth.
Consulta direta ao mesmo banco encontrou completed, geração 2 e as duas listas
com dez verificadores da geração 1 revogados e dez da geração 2 ativos.
Processos API A/B independentes foram reiniciados contra esse MESMO banco, sem
recriar cluster: estado, geração, segredo MFA e setup permaneceram iguais.
Ver `docs/evidence/backend-integration-20261107/process-restart.json` para a
metodologia e seus limites. PID real do servidor, identidade de boot e fechamento
da porta entre processos foram verificados. O runner original 18082 não foi
interrompido; o teste usa porta livre indicada na evidência e foi encerrado,
preservando também a API V2 de 18083. Não houve novo login browser nesse
teste de restart, nem consumo de código do administrador do E2E; reset/replay/MFA
foram verificados separadamente nos onze testes nativos.
TOTP via biblioteca testa protocolo, QR gerado e replay; não comprova ensaio no
aplicativo Microsoft Authenticator. Esse ensaio precisa ocorrer no dispositivo
do administrador sem enviar QR, segredo ou códigos ao chat.
Não declarar aceite Windows/Ubuntu limpos, reboot, serviço instalado ou autostart
com base nos testes de desenvolvimento. SHAP e revisão visual não dependem
deste aceite de conta.
