# Validação da candidata — 2026-11-04

Base `9d35906cc46a35a1d5e80c27243e75aef69d7b58`, branch
`feat/admin-bootstrap-mfa`, worktree `harpisense-worktrees/admin-bootstrap-mfa`.
Nenhuma alteração na worktree `frontend-backend-autonomia`, na VM, no bootstrap
compartilhado ou em RF/IF/Risk/Policy. Contrato ainda candidato, sujeito à integração
coordenada do arquiteto.

## Resultados

* PostgreSQL **18.6** descartável, banco `auth_fixture`, porta host somente loopback
  `55446`. Sem DSN operacional ou fallback. Migração 001 na fixture, depois 002.
* **25 testes aprovados**, sem skips, em Linux/Python 3.12 com código montado somente
  para leitura: `test_mfa.py` (22 casos PostgreSQL/HTTP) e `test_mfa_local.py` (3 casos
  de permissões e CLI Linux). Execução final: 38,940 segundos, exit 0.
* **22 casos legados de autenticação aprovados**, em schema separado `legacy_auth`
  no mesmo cluster descartável. A execução principal de `test_admin_auth.py`
  passou 21 e pulou o caso que exige URL sem query. Esse caso foi executado depois,
  sem query, com `PGOPTIONS=-c search_path=legacy_auth`, e passou. Não foi necessário
  modificar a suíte anterior nem desabilitar restrições.
* Verificação de whitespace com `git diff --check`: sem erros.

Cobertura: grant ausente/incorreto/expirado/substituído/consumido, bootstrap
concorrente, unicidade administrativa, retomada de cadastro pendente, QR/chave sob
autorização, confirmação válida/inválida/expirada, limitação global e por desafio,
login em duas etapas, replay TOTP inclusive concorrente, recuperação de uso único
inclusive concorrente, recadastro limitado, invalidação de grants pendentes,
logout, troca de credencial e revogação, rollback quando auditoria falha,
chave de cifragem incorreta, não divulgação de segredos, origem e validação HTTP,
continuidade e adesão atômica da conta existente, preservação de ingestão técnica,
arquivo Linux 0600/diretório 0700 e recusa de symlinks/sobrescrita.

Os testes de replay usam controle explícito do `last_step` **somente na fixture**
para representar um passo ainda não utilizado sem aguardar 30 segundos. A produção
usa exclusivamente relógio PostgreSQL e passo atual estrito; os testes também
verificam que um passo já consumido é rejeitado e códigos antigos não são aceitos.

## Limites da evidência

Testes são de módulo e composição HTTP local com PostgreSQL real isolado. Não
atestam implantação, frontend conectado, transporte/ACLs do instalador definitivo,
custódia de backups, relógio NTP da VM ou operação de motores/executor. O arquiteto
deve verificar esses pontos ao integrar. Nenhuma URL de serviço ativo é entregue.
O helper de arquivo é deliberadamente Linux; não declara proteção equivalente por
ACL do Windows. As credenciais de fixture nos exemplos são somente descartáveis.

Reprodução e recuperação:
[instruções de integração](ADMIN_MFA_INTEGRACAO_RECUPERACAO.md).
Contrato frontend:
[contrato HTTP candidato](ADMIN_MFA_CONTRATO_CANDIDATO.md).
