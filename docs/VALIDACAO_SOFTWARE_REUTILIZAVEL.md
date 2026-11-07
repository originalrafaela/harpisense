# Entrega e evidências locais — 06/11/2026 (America/Sao_Paulo)

Base: `integration/install-lab-20261105`, commit `69ca4dd`.
Branch de entrega: `feat/reusable-software` no worktree `harpisense-worktrees/reusable-software`.
Contratos: [documento](CONTRATO_SOFTWARE_REUTILIZAVEL.md) e
[OpenAPI exportado](OPENAPI_SOFTWARE_REUTILIZAVEL.json).

## Resultado observado

| Validação | PostgreSQL 16.15 | PostgreSQL 18.6 |
|---|---:|---:|
| Matriz auth/MFA, recuperação, ativos, controles e interface | 33 passaram | 33 passaram |
| Teste adicional de encerramento e novo processo HTTP | 1 passou | 1 passou |
| Falhas / erros / testes ignorados nessa matriz | 0 / 0 / 0 | 0 / 0 / 0 |

A matriz principal terminou em 07/11/2026 02:51 UTC, ainda 06/11 no fuso local.
Os testes usaram PostgreSQL reais em containers próprios `harpisense-reusable-pg16`
e `harpisense-reusable-pg18`, banco descartável `auth_fixture`, sem rede externa.
Containers de teste compartilharam apenas o namespace de rede do respectivo banco.
Nenhum banco, dispositivo, broker ou executor operacional recebeu migrações ou comandos.

Cobertura observada: geração e hash dos códigos; reemissão; reautenticação por
senha e TOTP; consumo único concorrente do código e grant; expiração; throttle
persistente com sentinelas finitas/infinita negativa/infinita positiva; resposta
comum de erro; separação entre senha e recuperação MFA; nova senha seguida de
TOTP; revogação de sessões/challenges/grants; ausência de segredos na auditoria;
rollback do código e da senha quando a auditoria falha; validação dos schemas
OpenAPI de emissão e grant; rotas HTTP TCP reais e regressões MFA por ASGI.

Ativos: criação, renomeação amigável, compatibilidade, vínculo não aprovado,
conflito entre escritores, revisão, auditoria e preservação de device_id/tópico
nas projeções anteriores. Estado operacional: consultas às quatro autoridades
na mesma conexão sob lock PostgreSQL, histórico CLOSED não bloqueante, anomalia,
incidente, aprovação e execução pendentes bloqueantes, estado desconhecido,
revisão concorrente e parada de emergência. Fontes usadas nesses testes eram
autoridades de fixture SQL explícitas, não integrações operacionais implantadas.

Interface: referências exatas a RF/IF, evidências e eventos de rede, revisões
ambíguas sinalizadas, estados distintos de decisão/aprovação/execução/verificação,
histórico e últimas três explicações persistentes e idempotência de explicação.
O teste adicional encerrou o processo servidor e iniciou outro processo: sessão,
nome do ativo e histórico HarpIA continuaram disponíveis via HTTP TCP.

Regressões adicionais em `delivery_tests/test_delivery.py`: **14 passaram**,
incluindo matriz de 27 combinações cenário/modo, M2 Medium manual, inelegibilidade
M3, gates, concorrência, histórico encerrado e emergência. Quatro testes antigos
desse arquivo foram ignorados por ausência de TEST_DATABASE_URL; não são contados
como PostgreSQL validado. A matriz nova acima cobre o PostgreSQL desta entrega.
`git diff --check` sem erros.

## Operações e integração

| Operação | Implementada | Composta na candidata | Verificada localmente | Runtime operacional / Frontend |
|---|---|---|---|---|
| Emitir, validar e usar código exclusivo de senha | Sim | MFA candidata existente | PG16/18 + TCP | Pendente |
| Recuperar autenticador sem sessão plena | Preservada | Sim | Regressões PG16/18 | Não alterado |
| Cadastro, nomes, vínculos e auditoria de ativos | Sim | Factory opcional com catálogo confiável | PG16/18 + TCP | Pendente |
| Perfil efetivo e motivos de bloqueio | Sim | Controls existente | PG16/18 + regressões | Sem implantação nova |
| Agregar quatro autoridades operacionais | Adaptador pronto | Parâmetro opcional; ausência bloqueia | Fontes SQL de teste | Produtores reais pendentes |
| Incidente, evidências, logs referenciados e resultados distintos | Sim | Factory opcional | PG16/18 + TCP | Pendente |
| Histórico e últimas três explicações HarpIA | Sim, determinístico | Factory opcional | PG16/18 + reinício de processo | Pendente |
| Comandos administrativos de aprovação/execução | Não acrescentados | Não | Não declarados | Exigem contrato do Arquiteto |

## Reprodução

Imagem de teste existente: `harpisense-admin-mfa-http`, que inclui dependências
da autenticação e do Gerenciador. Montar este worktree em `/work`, executar com
cwd `/work` e `ADMIN_MFA_TEST_DATABASE_URL` apontando exclusivamente para
`auth_fixture` descartável. O script recusa outro nome de banco.

```
python backend/scripts/test_reusable_software.py
```

O runner atual inclui os 34 testes (33 da matriz e o reinício adicionado depois).
Emite apenas metadados sanitizados de resultado, sem DSN, códigos ou tokens.
Para exportar os contratos sem banco: `python backend/scripts/export_reusable_contracts.py`.

## Pendências concretas para integração

O CLI Maestri retornou pipe inexistente; `maestri debug` confirmou ambiente
apontando para daemon expirado. Nenhuma comunicação com Arquiteto/Gerenciador
foi declarada como concluída. A base acima foi identificada nos worktrees locais,
sem confirmação nova do Arquiteto. Não foi feito merge em outra branch.

1. Arquiteto confirmar base e composição no instalador, executar migrações
   aditivas com o papel proprietário e conceder permissões mínimas ao runtime.
2. Gerenciador fornecer manifesto de perfis e vínculos aprovados. Cadastro legado
   continua consultável por P11; não há importação automática que invente perfil
   ou renomeie identidade. Frontend deve preservar essa distinção na integração.
3. Proprietários operacionais ligar fontes completas ao AuthorityQueue e garantir
   que todos os produtores compartilhem Controls.decision_transaction. Sem isso,
   mudança permanece bloqueada por QUEUE_UNVERIFIED.
4. Frontend ligar formulários de emissão/recuperação e cadastro aos contratos,
   exibir códigos somente na resposta de emissão e limpar segredos de memória.
5. Aprovação e execução precisam de endpoints autorizados próprios; consulta
   de projeções não concede essa autorização. REAL continua bloqueado.
