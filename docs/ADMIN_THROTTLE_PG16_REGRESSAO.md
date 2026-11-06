# Correção de throttle PostgreSQL 16 — 2026-11-06

Base: `589ed25`; branch `fix/admin-throttle-pg16`.

`AdminAuth.throttle` subtraía `clock_timestamp()` de `blocked_until`, cujo
sentinela inicial e de reset é `-infinity`. PostgreSQL 16 rejeita a operação
com SQLSTATE 22008. A transação traduz o erro em `503 AUTH_UNAVAILABLE` antes
de consumir o grant ou criar a conta. Renovar o grant não passa pelo throttle.

A correção em `backend/admin_auth/service.py` protege a subtração por CASE:
`-infinity` e prazos finitos expirados permitem continuar; prazos finitos futuros
mantêm 429/TRY_LATER e Retry-After; `+infinity` falha fechado com 503.
Não muda migração, sentinela, contagem de falhas, lock, grants ou contrato HTTP.

## Verificação executada

Sete testes direcionados em cada versão: PostgreSQL 16.15 (`postgres:16-alpine`)
e PostgreSQL 18.6 (`postgres:18.6`), todos aprovados. A expressão antiga foi
executada separadamente na fixture 16 e falhou com
`cannot subtract infinite timestamps`.

Cobertura: sentinela inicial/reset; prazo expirado; cooldown futuro com 429 e
Retry-After; +infinity fechado; falhas sucessivas criando cooldown; bootstrap
consumindo grant e retornando somente enroll, com zero sessões; bootstrap
bloqueado preservando grant e zero contas.

Somente processos descartáveis Docker, rede `none`, sem portas publicadas;
código montado somente para leitura. Nenhuma conexão com banco operacional,
alteração em VM ou packaging/native. Não repete a suíte completa MFA. Este
resultado não substitui novo ensaio do instalador: candidata2 permanece como
evidência de falha, sem patch aplicado nela.

## Reprodução (PowerShell, raiz desta worktree)

Preparar a imagem de dependências se ainda não existir:

```powershell
docker build -t harpisense-admin-mfa-tests -f backend/admin_auth_tests/Dockerfile.mfa .
```

Iniciar somente a fixture, sem acesso externo. Trust é exclusivo do namespace
de rede isolado, nunca configuração de produto:

```powershell
docker run -d --rm --name harpisense-throttle-pg16-regression --network none -e POSTGRES_DB=admin_throttle_fixture -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine
docker exec harpisense-throttle-pg16-regression pg_isready -U postgres -d admin_throttle_fixture
```

Após `accepting connections`, executar (o teste exige esse nome de banco e
reseta apenas suas tabelas de autenticação; não usar DSN operacional):

```powershell
docker run --rm --network container:harpisense-throttle-pg16-regression -e ADMIN_THROTTLE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/admin_throttle_fixture -v "${PWD}:/work:ro" -w /work harpisense-admin-mfa-tests:latest python backend/admin_auth_tests/test_throttle_postgres.py
docker stop harpisense-throttle-pg16-regression
```

Para repetir a comparação com PG18 usar outro nome de container e `postgres:18.6`.
Os testes executados usaram `harpisense-admin-mfa-http:latest`, que estende a
imagem acima; o teste importa apenas dependências disponíveis na imagem base.
