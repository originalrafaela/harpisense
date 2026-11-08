# Emissor e autenticação local — entrega backend

Contrato normativo: `INITIAL_AUTH_CONTRACT_V1.md`, publicado em `fadebd9`.
Worktree `issuer-local-auth`, branch `feat/issuer-local-auth`, base `2345808`, contrato incorporado como `65cc219`.
Commit mínimo de autenticação: `cb6545be4ab0e585f8ff4315e80f7061821eb7e6`.
O commit complementar inclui emissor, testes, migração 005 repetível e fechamento da composição antiga.

## Composição e migrações

O backend existente combina FastAPI, SQLAlchemy/Alembic para o domínio e psycopg para as projeções/autenticação administrativas. As tabelas de autenticação já tinham migrações SQL explícitas 001–004, fora da cadeia Alembic do domínio. A entrega mantém essa autoridade: nenhuma migração no startup, nenhuma revisão concorrente sobre as tabelas de domínio.

Banco **local**: aplicar `backend/admin_auth/005_initial_auth_v2.sql` depois de 001–004. É transacional, usa o advisory lock existente e pode ser reaplicada. Acrescenta vínculo UUID à conta, segredo de enrollment pendente cifrado e tabelas `hs_admin_recovery_set_v2` / `hs_admin_recovery_v2`. Administrador único continua garantido por `PRIMARY KEY CHECK(id=1)`.

Banco **do emissor**, separado: aplicar `backend/license_issuer/001_issuer.sql` explicitamente, uma vez, com identidade de migração. Contém registro compartilhado Windows/Ubuntu, desafios e throttle. `key_hash UNIQUE` continua registrado depois da ativação. Não instalar esse schema no PostgreSQL local.

`install_candidate_admin_auth(..., protection_key=<Fernet bytes>, initial_access=<Edge adapter>)` preserva o nome usado pelo runtime. `initial_access=None` impede bootstrap e operações privilegiadas iniciais; nenhum header HTTP substitui o callback. Bootstrap chama `require(request)` e usa somente os UUIDs retornados. Retry chama o próprio `retry(request)` do adaptador: ele autoriza transporte/cookie mesmo antes da ativação, permitindo recuperar a conexão. Exigir receipt antes desse retry impediria a ativação inicial. Status delega ao adaptador, sem produzir segredo. Confirmação MFA chama `invalidate()` após commit; a checagem de conta pronta do Edge também fecha o acesso após restart/resposta perdida.

O Gerenciador mantém `backend/native_server/runtime.py`: **não foi alterado neste branch**. `docs/integration-patches/initial-auth-runtime.patch` é referência separada, verificável contra a base, para encaminhar `initial_access` e `protection_key`; não aplicar sobre a composição que o Gerenciador já fez. `protection_key` chega de `load_totp_key`, sem leitura plaintext no runtime integrado.

`MFAAdminAuth.administrator_state()` é callback sem argumentos para Edge: `absent`, `mfa_pending`, `ready` ou `migration_required`. A fábrica pode receber uma closure que consulta `app.state.admin_auth` após a composição.

`delivery.app.build_candidate_app` agora exige `protection_key`, instala `MFAAdminAuth` e aceita `initial_access`; sem chave recusa startup com `MFA_COMPOSITION_REQUIRED`. `build_app` continua sendo componente de composição técnica; o pacote deve servir o runtime que instala a autenticação humana antes de abrir o listener. Ferramentas antigas de provisionamento não substituem o handoff nativo. `issue_local_grant`, `/local-recovery` e `/mfa/recover` não abrem cadastro nem redefinem MFA.

## Estados e transações

| Fluxo | Transição / regra |
|---|---|
| Emissão | Credencial exclusiva do distribuidor → chave CSPRNG 32 bytes entregue uma vez; banco recebe apenas SHA256 e UUID. Colisão UNIQUE tenta nova chave. |
| Desafio | 120 s, nonce CSPRNG, vínculo exato da licença/instalação/chave/plataforma, até cinco tentativas. Erros de prova incrementam contador em commit. |
| Ativação | Lock licença → desafio; prova Ed25519 válida; vínculo, receipt e consumo na mesma transação. Outra instalação recebe 409 e a mensagem normativa. |
| Retomada | Mesmo vínculo, novo desafio e prova → mesmo receipt persistido. Desafio consumido sempre recebe 409. Receipt não expira. |
| Cadastro | Callback local verificado → uma conta pendente, sem sessão administrativa. Nova tentativa com mesma conta/senha/vínculo retoma enrollment. |
| Enrollment | Segredo pending cifrado pertence à conta e é reutilizado entre desafios. Só o primeiro TOTP confirmado habilita MFA e emite Bearer; não emite códigos. |
| Sessão | Senha → desafio 300 s → TOTP atual ainda não usado → Bearer. Toda rota administrativa requer sessão com `mfa_verified=true`. |
| Primeiro acesso v2 | `not_issued` geração 0 → POST codes `{}` → `pending`, geração 1, exatamente três códigos. Repetição/duas abas recebe 409 com estado, sem originais. |
| Confirmação | `pending` + geração corrente → `completed`; mesma confirmação é idempotente. Geração antiga recebe `GENERATION_CONFLICT`. |
| Reemissão | Sessão MFA + senha + novo TOTP; revoga conjunto anterior e incrementa geração atomicamente. Resposta perdida exige nova reemissão explícita. |
| Recuperação | Código v2 da conta/instalação + TOTP → Argon2id nova senha, consumo de um código, revisão de credencial e revogação de sessões em uma transação. Outros dois códigos e MFA permanecem. |

Autenticação serializa transições pela linha singleton existente (`hs_admin_throttle`). Savepoint separa mutações de domínio dos contadores/auditoria: erro esperado desfaz consumo, revogação e TOTP, mas registra a tentativa. Falha SQL aborta a transação inteira. Reset simultâneo não consome duas vezes o mesmo código. O passo TOTP fica em `hs_admin_mfa.last_step` e vale para todas as rotas, com janela estrita de 30 s e relógio PostgreSQL.

Contas existentes sem receipt continuam fazendo login por senha e MFA, sem exigir uma nova licença. O estado público é `migration_required`; conta legada sem MFA recebe apenas desafio enroll. Migração 005 atribui UUID estável ao administrador legado; não fabrica receipt nem ativa licença. Senha scrypt válida recebe rehash Argon2id oportunista. Sessões antigas sem MFA são revogadas. Conjuntos antigos 10+10 ficam preservados para trilha e não são aceitos no reset v2; a primeira emissão v2 autorizada revoga-os explicitamente na mesma transação.

## Criptografia e isolamento

Ed25519 verifica os bytes exatos do envelope antes do JSON; recusa purpose incorreto, chave desconhecida, campos extras, duplicados, tipos errados e épocas float. A chave privada do emissor é injetada exclusivamente no processo do emissor; o cliente recebe apenas o anel público. TLS/hostname são verificados pelo `HTTPSIssuer` de Edge. O emissor não aceita `X-Forwarded-Proto` como autorização TLS.

Senhas: `argon2-cffi==25.1.0`, `argon2-cffi-bindings==25.1.0`, `cffi==2.0.0`, `pycparser==2.23`; Argon2id m=65536 KiB, t=3, p=4, salt aleatório individual de 16 bytes. Lista canônica em `backend/admin_auth/requirements-passwords.txt`, incluída pelos requisitos backend e MFA. TOTP: `pyotp==2.9.0`, segredo cifrado com Fernet (`cryptography==50.0.2`), QR com `qrcode==8.2`. O protetor DPAPI CurrentUser / credential systemd e as contas de serviço pertencem a Edge/Gerenciador. PostgreSQL não recebe a chave de proteção.

`api.install_admin_auth` troca recursivamente a dependência Basic administrativa por Bearer. A exceção exata é POST `/api/v1/p11/ingest/{kind}`: continua exigindo Basic técnico e token de serviço no handler original. Controles, configuração, XAI e dossiê usam os hooks administrativos. Consumidor MQTT, ACLs e credenciais técnicas permanecem separados. O token do distribuidor não é um Bearer administrativo local.

Respostas de auth e emissor têm `Cache-Control: no-store`; validação Pydantic é sanitizada. Não registrar corpos, headers, tokens, QR, senha, licença ou códigos. Auditoria local grava evento/resultado/account_id. Emissor CLI desativa access log, proxy headers e saída bruta de erros de configuração. Nos bancos há apenas hashes/verificadores, metadados e TOTP cifrado; nunca originais recuperáveis dos três códigos.

## Executar emissor

Ambiente próprio do emissor, Python 3.11, dependências em `backend/license_issuer/requirements.txt`. `PYTHONPATH=backend`. Arquivos privados de configuração ficam fora do checkout, com ACL do serviço no Windows ou modo 0600 no Ubuntu. Migração com identidade DDL; serviço com conta de banco distinta e privilégios das tabelas do emissor. Não distribuir a chave privada ou os arquivos de credenciais em pacotes locais.

```text
python -m license_issuer migrate --dsn-file <arquivo-privado-dsn>
python -m license_issuer serve --dsn-file <arquivo-privado-dsn> --signing-key-file <ed25519-pkcs8-pem> --distributor-token-file <arquivo-token256bits> --tls-cert <certificado> --tls-key <chave-tls> --host <listener-do-emissor> --port 8443
```

Somente o distribuidor chama POST `/api/v1/licenses/issue` com Bearer técnico exclusivo e `{}`. Os endpoints challenges/activate seguem exatamente o contrato. `create_issuer_app` também permite composição com chave e credencial injetadas; não expor sem TLS. Rotação do anel público requer atualização assinada do pacote; nenhum endpoint aceita chave pública de emissor enviada pelo navegador.

## Evidência reproduzível

Testes não usam SQLite/Docker nem banco de produção. O runner usa binários PostgreSQL nativos, cluster `.pg-auth-test` privado da worktree, listener loopback com porta livre, database `auth_initial_fixture`, schema aleatório por teste e shutdown no finally. A autenticação trust é exclusiva desse cluster descartável. Recusa anexar a um cluster que já está rodando.

```powershell
uv venv .venv311 --python 3.11
uv pip install --python .venv311/Scripts/python.exe -r backend/requirements.txt -r backend/admin_auth/requirements-mfa.txt
.venv311/Scripts/python.exe backend/initial_auth_tests/run_native_postgres.py --pg-bin D:/Programas/PostgreSQL/bin
.venv311/Scripts/python.exe backend/initial_auth_tests/run_native_postgres.py --pg-bin D:/Programas/PostgreSQL/bin --edge-backend ../local-activation/backend
```

Em outro SO ajustar somente Python e `--pg-bin`. Também é possível executar pytest diretamente com `INITIAL_AUTH_TEST_DSN` apontando exclusivamente para `auth_initial_fixture`. Ausência de DSN falha explicitamente, sem transformar ausência de banco em testes aprovados. `--test <pytest-node>` executa validação específica.

Executado em Windows em 08/11/2026: PostgreSQL 18.4 nativo, Python 3.11, psycopg 3.2.1. **17 passaram em 18,32 s**: 15 de backend e dois com código real de Edge `5d87e6f3b9bce1b7e79c970653764e1199dc75d9`, TLS local com CA explícita e DPAPI nativa. As disputas observam duas conexões simultaneamente esperando por locks no servidor. Cobertura: colisão/emissão concorrente, Windows vs Ubuntu no mesmo registro, licença dupla, TTL, prova inválida, replay, resposta perdida, cadastro interrompido, duas abas, perda/reload dos códigos, reset concorrente, replay MFA, Basic administrativo recusado, logs/erros sanitizados e login legado sem receipt.

Validação complementar dirigida: quatro testes aprovados de rollback tardio, falha CSPRNG, persistência de tentativas e migração repetível com conta legada pronta; após corrigir a posição do guard de startup, o teste específico da composição antiga passou em 1,08 s. Não foi repetida a rodada E2E do runtime/IPC do Gerenciador. Avisos observados são de depreciação Starlette/AnyIO e WebSockets. Não é aceite de máquina limpa Ubuntu, systemd nem instalador sem checkout; esses resultados pertencem à frente nativa.
