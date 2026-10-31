# Frontend candidato local — 31/10/2026

Encerramento solicitado pelo operador em 31/10: login e abertura do painel
confirmados por relato do operador. Sem observação direta da sessão autenticada
no portal nesta rodada. Validação de telemetria, atualização automática, logout
e retorno ao login por expiração no navegador permanece pendente. Evidências
HTTP do verificador da VM são preservadas separadamente abaixo. Nenhuma senha
ou token de sessão foi registrado.

Worktree: `harpisense-worktrees/frontend-backend-autonomia`, branch
`feat/frontend-backend-autonomia`. Artefato candidato do commit
`a09834351c768867bb42c109e07c4c5eab723747`, release `admin-session-20261030-r1`.
Este registro acompanha a mudança posterior da política de senha para mínimo 8.

## Disponibilização observada

- Ativação local às `2026-10-31T04:13:18.0311174Z`, processo preview 4672.
- URL: `http://127.0.0.1:4174/`; Vite configurado somente em loopback.
- Túnel SSH local: `127.0.0.1:18000` para `127.0.0.1:8000` no HarpiServer.
- Manifesto do candidato conferido pelo script de ativação.
- Handshake de sessão e health exigindo 401 Bearer aprovado antes da cópia.
- HTTP da página: 200; pelo proxy, `/api/v1/admin-auth/session` e
  `/api/v1/p11/health`: 401 com `WWW-Authenticate: Bearer`.
- Portal Maestri `HarpiSense V2 Continuidade` aberto no formulário real.
- Artefato servido anterior preservado em
  `frontend/local-evidence/deployment-backups/auth-20261031-011317-71/dist`.
- Candidato original preservado em `frontend/local-evidence/auth-candidate-dist`;
  nenhuma alteração feita na worktree de prévia `frontend-v2`.
- Sem publicação externa, migração ou reinício de serviço remoto nesta rodada.

## Validação da conta

O operador forneceu recibo do verificador da VM de
`2026-10-31T04:10:12.559853+00:00`: login/sessão/health/telemetria 200,
logout 204, acesso anônimo/Basic técnico/login e sessão inválidos/reuso após
logout 401; expiração absoluta e por inatividade 401 `SESSION_EXPIRED`.
Essa evidência HTTP foi fornecida pelo operador; não equivale a observação
de login no navegador.

Retorno do operador: conta administrativa autenticou e abriu o painel no seu
navegador. Conferência direta do portal Maestri às 04:25:05 e 04:25:57 UTC:
formulário de login ainda visível e observador sem requisições autenticadas.
Portanto o login relatado ocorreu em contexto diferente do portal acessível ao
agente; não houve leitura de senha ou token. Solicitada entrada no portal para
prosseguir com observação direta. Telemetria, polling, logout e expiração no
navegador continuam pendentes de observação; nenhum resultado foi presumido.

Na disponibilização, a interface ainda estava no formulário. Login real,
consulta de telemetria, polling, logout e retorno ao login por expiração no
navegador estão **pendentes da entrada interativa do operador**. Não foram
declarados aprovados por inferência dos testes anteriores.

Observador temporário no portal coleta apenas horário, caminho HTTP e status;
não coleta corpos, senhas, cabeçalhos ou tokens. Credenciais técnicas não são
usadas como alternativa administrativa.

MFA e recuperação por e-mail: **pendentes / indisponíveis**.

## Abrir e retomar

No PowerShell, abrir a versão já em execução:

```powershell
Start-Process 'http://127.0.0.1:4174/'
```

Para reativar o candidato, com túnel já aberto, a partir da worktree:

```powershell
Set-Location 'D:\Projetos\tcc - harpisense\harpisense-worktrees\frontend-backend-autonomia'
& .\frontend\scripts\activate-admin-preview.ps1
```

O script preserva o dist anterior e exige handshake Bearer antes de servir.
Senha deve ser digitada somente no formulário pelo operador.
