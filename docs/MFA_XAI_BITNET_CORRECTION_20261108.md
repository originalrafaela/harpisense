# Correção de composição MFA/XAI e ligação BitNet — 08/11/2026

Branch: `integration/initial-auth-20261108`; base da correção `4cd4088`.

## Causas confirmadas

- O serviço real ainda usa autenticação `admin-session-20261030-r1` e composição
  `presentation-20261102-r1`. Não carrega a integração atual. Não é um problema
  de credencial: as rotas novas estavam ausentes do OpenAPI e retornavam 404.
- Além disso, `delivery.build_candidate_app` não instalava XAI/dossiê, embora
  `native_server.build_native_api` os instalasse. A fábrica compartilhada foi
  corrigida para montar ambos após autenticação administrativa.
- P11 só instalava HarpIA determinística. O adaptador BitNet existente não era
  chamado; a interface também só consultava a capacidade determinística.
- Não há recursos para carregar esse modelo no gateway atual: **1.594 MiB de
  RAM total e 973 MiB disponíveis**, contra 3.584 MiB livres exigidos pelo runtime.
  O Windows medido nesta rodada tinha 3.180.924 KiB livres, também insuficientes.
  Não houve desligamento de VM nem redução do limiar de proteção.
- O venv antigo do servidor não contém Argon2, pyotp, qrcode ou cryptography.
  A release separada instalou essas dependências sem alterar o venv ativo.

## Mudanças

`backend/delivery/app.py`: XAI/dossiê na fábrica genérica e adaptador BitNet opt-in
restrito a loopback. `genai/harpia/{p11,client}.py`: geração vinculada à revisão,
texto explicitamente não verificado, fallback completo e prontidão real do modelo.
`frontend/src/api.ts`: aceita a capacidade BitNet explícita e seu fallback;
rotas legadas não ganham permissão implícita de inferência.

`packaging/server/`: pacote identificado por hashes, entrada atual com frontend
compilado, venv separado, backup completo, restauração/ensaio privado, migrações,
drop-in systemd e retorno automático ao serviço original se a partida falhar.
O administrador conserva identidade e senha e migra para cadastro TOTP antes
de receber acesso administrativo. Nenhum cadastro inicial remoto é liberado.
`packaging/native/inspect_gateway_upgrade.py`: inspeção somente de leitura e
saída sanitizada de dependências/permissões, sem imprimir configuração ou contas.

## Testes executados

- **6 testes novos HTTP/composição**: capacidade/prontidão BitNet, resposta vinculada à
  revisão, indisponibilidade com fallback, autenticação e rotas MFA/XAI/dossiê,
  recusa de endereço externo. Runtime gerador **sintético**, não inferência GGUF.
  Conninfo PostgreSQL com `user=` antes de `host=` também é aceito; driver
  incompatível é recusado. Isso permite conectar o cluster de restauração Unix.
- **37 testes HarpIA: 36 aprovados, 1 skip** dependente de referência P11 opcional.
- **77 testes frontend aprovados** e build/typecheck aprovados.
- **20 testes de autenticação aprovados com PostgreSQL 18 nativo descartável**,
  incluindo administrador legado, MFA, concorrência e recuperação. A primeira
  chamada direta de pytest teve 14 erros de configuração por falta da DSN da
  fixture; a repetição pelo runner correto criou o cluster e passou a suíte.
- **1 teste de migração PostgreSQL aprovado**: identidade/senha/revisão legadas
  preservadas, repetição das migrações, runtime sem CREATE no esquema public,
  permissões de tabelas/sequências para os novos controles e cadastro de ativos.

Windows: testes de desenvolvimento com Python/PostgreSQL locais; não é aceite
de instalador em Windows limpo nem reboot do SO.
Ubuntu/HarpiServer: inspeção e preparação de release no servidor existente;
não é instalação limpa nem aceite após reboot.
**Smoke da release em Ubuntu aprovado:** frontend compilado, MFA presente,
XAI protegido e Argon2id criando/verificando senha com as dependências do venv
separado. Sem conexão a banco nesse smoke; não comprova a migração real.

## Situação da implantação

A primeira preparação isolada instalou dependências, mas o dump foi recusado
porque a conta `harpisense_app` não pode ler os valores das sequências de
configuração. O dump incompleto não é aceito como backup nem usado na migração.
O atualizador foi corrigido para exigir backup completo por postgres via sudo,
sem ampliar privilégios da aplicação. `sudo -n` exige autenticação interativa.
Nenhum serviço ativo, banco real, MQTT, VPN ou firewall foi alterado.

**Correção de código testada não significa serviço atualizado.** A aplicação no
servidor permanece dependente da execução administrativa descrita em
[packaging/server/README.md](../packaging/server/README.md). A restauração do dump
real e sua migração só podem ser declaradas aprovadas após essa execução.
O BitNet continua bloqueado por recursos/provisionamento e pela ausência de
nova validação textual; nenhuma inferência real foi executada nesta rodada.
Política de perda do autenticador permanece pendente.

## Auditoria frontend independente recebida

O relatório informado em `harpisense-worktrees/audit-final-385b363/docs/FRONTEND_ACCEPTANCE_AUDIT_20261108.md`
se refere exatamente a `385b363725479767fc7c61523003cfba10ae285e`, anterior a esta
correção. Registra build/typecheck, 76 unitários e duas suítes Playwright de
11 testes aprovados, sem homologação de instalador ou reboot para essa fonte.
Seus resultados não são atribuídos ao commit novo nem aos candidatos antigos.
O parecer de não iniciar C01–C09 é mantido; nenhum ataque foi executado aqui.
