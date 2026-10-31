# Gerenciador de configurações — etapa 1

Módulo interno do backend: esquema administrativo `config.*` 1.0.0,
validação e persistência no PostgreSQL existente. Não inicia outra API e não
executa comandos, chamadas de rede, resoluções de segredos ou aplicadores.

## Base e coordenação

Branch `feat/config-manager-stage1`, base `a098343`, worktree
`harpisense-worktrees/config-manager-stage1`. A candidata de autenticação está
em `harpisense-worktrees/frontend-backend-autonomia`, branch
`feat/frontend-backend-autonomia`, com alterações locais em `admin_auth`,
`admin_auth_ops`, seus testes e documentação. Nenhum desses arquivos, bootstrap,
frontend ou router foi alterado nesta entrega.

A confirmação direta com o arquiteto continua pendente: o Maestri identifica
este terminal como `HarpiSense Arquiteto`, e `maestri ask` para esse nome retorna
`No connection`. A conexão técnica foi verificada com `maestri debug`.
Foi solicitada ao operador a identificação correta do terminal. A base acima
foi determinada pela inspeção do Git e da documentação de autenticação, sem
atribuir ao arquiteto uma confirmação que não ocorreu. Integração/ativação
permanecem pendentes desse alinhamento.

## Referências e reutilização

Precedência: entregas aprovadas de `referencias/versão_v2`; componentes sem
atualização continuam presentes em `referencias/Versões corretas`.

- Consolidado `HarpiSense_Mudancas_Consolidadas_Frontend_Backend.pdf`, 27/10.
- Especificação histórica `HarpiSense_Gerenciador_Configuracao_Especificacao_v1.pdf`.
- Proposta de revisão de 27/10: DOCX, matriz XLSX e exemplos sanitizados.
  Usada como orientação, preservando seu estado de proposta.
- P03: reutiliza `harpisense_contracts.canonical.canonical_json`, `fingerprint`
  e `harpisense_contracts.validation.timestamp` de `backend/domain`.
  Sua origem V2 já consta de `backend/domain/ORIGINS.json`.
- P08: schema `harpisense.if.window.v1`, janela atual de 10 segundos.
  O esquema administrativo restringe essa combinação; não redefine features.
- P11: migração de projeções e contratos administrativos consultados; nenhum
  endpoint/projeção ou head Alembic existente foi substituído.
- Legados consultados: Inventário de Alvos v1, nftables v1 e Gerenciador de
  Execução v1. Permanecem disponíveis, sem copiar seus motores para este módulo.

Não há catálogo concorrente de ações, Risk/Policy ou autonomia. Identidades,
modelos, redes, ACLs e referências aceitas vêm de um `Capabilities` confiável
fornecido pelo backend/instalador, com fingerprint persistido na validação.
Manifesto vazio recusa referências operacionais. Não usar valores enviados pelo
navegador como manifesto confiável.

## Parâmetros desta etapa

Todos os parâmetros são opcionais no documento, mas o objeto não pode ser
vazio. Cada proposta contém um **snapshot completo**, não um merge/patch:
omitir campo anteriormente presente propõe removê-lo e exige verificação do
componente afetado. Não há padrões presumidos do laboratório.

| Grupo | Campos suportados | Validação |
| --- | --- | --- |
| Apresentação | `display_name`, `timezone` | Texto limitado; fuso IANA existente |
| Redes | `network_cidrs`, `sensor_bindings` | CIDRs estritos, sem sobreposição; redes autorizadas e sensores/pontos cadastrados |
| Captura | `capture_filter_profile`, `capture_window_seconds`, `feature_schema_version` | Perfil aprovado; janela 10 s compatível com schema atual |
| MQTT | `mqtt_broker_host`, `mqtt_broker_port`, `mqtt_tls_mode`, `mqtt_ca_ref`, `mqtt_identity_secret_ref`, `mqtt_topics`, `mqtt_client_id` | Grupo completo; host permitido, porta 1–65535, TLS obrigatório, CA e identidade registradas, tópicos exatos da ACL |
| Pipeline | `rf_model_ref`, `if_model_ref`, `protocol_adapter_ref` | Referências aprovadas/instaladas, modelo compatível com schema |
| Segredos de operações futuras | `external_credential_ref`, `vpn_auth_ref` | Somente referências cadastradas `secret://namespace/id` |

Os dois últimos campos de segredo **não habilitam** backup ou VPN. Cadastro de
rede não significa tráfego observado, cobertura completa ou sensor conectado.
Validação de referências não significa conectividade, integridade do artefato
ou autorização de execução. Essas provas pertencem aos aplicadores/verificadores.

Campos fora da lista são recusados, incluindo senhas, tokens, comandos, bind,
DSN/bootstrap, política de autenticação e controles M1/M2/M3/IDS/execução. Os
demais parâmetros da matriz são evolução futura, com autoridade e limites a
alinhar antes de implementá-los. `api_public_base_url` também está fora desta etapa.

Os JSON Schemas exportados em `schemas/` são gerados das definições em
`schema.py`; o teste garante igualdade. `TypedDict` documenta os tipos Python.

## Persistência e fluxo

`provision_registry` registra uma identidade de instalação já fornecida pelo
instalador. Estado inicial: revisão desejada 0 e efetiva desconhecida (`null`).
Não descobre nem substitui o bootstrap.

1. `propose`: valida estrutura/semântica, reserva revisão monotônica e grava
   snapshot imutável, operação `DRAFT` e evento `PROPOSED` numa transação.
2. `validate`: verifica manifesto e compatibilidade e persiste `VALIDATED` ou
   `REJECTED`. Rejeição de referência fica auditada sem alterar a versão efetiva.
3. `begin_application`: exige proposta atual validada e mesmo manifesto;
   persiste intenção `APPLYING`, componentes exigidos e token monotônico de
   exclusão de workers antigos. Retorna um plano; não executa efeitos externos.
4. `record_verified`: integração interna do verificador registra recibo por
   componente, revisão/hash/token e horário observado após a intenção.
5. `confirm_application`: só avança a revisão efetiva e marca `APPLIED` quando
   todos os componentes têm recibos correspondentes. Recibo parcial não basta.

Transações bloqueiam a linha da instalação com `SELECT ... FOR UPDATE` e
comparam `expected_revision`. Dois escritores sobre a mesma revisão produzem
um vencedor e um `Conflict` com `current_revision`. Escopos de idempotência:
instalação + ator estável + chave + fingerprint da solicitação. Repetição
idêntica retorna a mesma operação; reutilização divergente conflita. Não há
expiração automática das chaves nesta etapa.

`fail_application` mantém a revisão efetiva anterior. Resultado parcial/incerto
fica `RECOVERY_REQUIRED`, retém exclusão da instalação e invalida tokens antigos.
Somente um worker confiável que comprovou ausência de efeitos pode usar
`no_external_effects=True` e liberar a instalação como `FAILED`.
`pending_reconciliation` recupera operações não concluídas após reinício,
sem reaplicar comandos. A reconciliação/rollback externo e watchdog serão
implementados com os aplicadores; não existe desbloqueio automático de estado incerto.

`current` retorna proposta/status e efetiva em um único snapshot SQL;
`revision` consulta snapshots históricos; `history` pagina a auditoria por ID.
Auditoria contém somente identidade estável, revisão, operação, evento, código
e horário UTC do PostgreSQL. Razão é enum, sem comentário livre. Erros de
validação não repetem nomes de campos nem valores submetidos.

## Segredos, autorização e recibos

Não existe campo de valor de segredo nem resolvedor neste módulo. Banco,
histórico e DTOs guardam apenas referências opacas; não há leitura de senhas
para devolver ao frontend. Provisionamento/rotação do segredo ficam em serviço
restrito separado. Não colocar segredos em nomes de exibição/identificadores.

`ConfigStore` é uma biblioteca interna, não uma fronteira de autenticação.
A integração HTTP deve obter `actor` da sessão autenticada, autorizar instalação,
exigir MFA conforme o contrato do arquiteto e mapear `Conflict` para 409.
Nenhuma rota foi exposta, e nenhuma rota técnica de ingestão ganhou privilégios.

`record_verified`, `confirm_application`, `fail_application` e o manifesto
aceitam apenas chamadas de componentes confiáveis do backend. **Nunca expor
recibos/atestados enviados pelo navegador como prova de estado observado.**
Um hash vincula o documento, mas não autentica o autor. Os testes usam um
verificador sintético explicitamente identificado; não comprovam MQTT/P08/VPN
ou serviços reais reconfigurados. `config-registry` também exige read-back pelo
consumidor responsável antes de registrar o recibo.

## Migração explícita e permissões

Instalar `requirements.txt` e disponibilizar `backend` e `backend/domain` no
`PYTHONPATH`. A conexão inicial é fornecida externamente pelo instalador.

```powershell
$env:PYTHONPATH = 'backend;backend/domain'
# HARPISENSE_CONFIG_MIGRATION_DSN fornecido por canal protegido externo.
python -m config_manager migrate
```

Migração aditiva `001_config_manager.sql`, transação única, lock de migração
e checksum. Reexecução idêntica é aceita; checksum divergente é recusado.
Cria apenas schema `hs_config`, tabelas, índices e triggers próprios. Não roda
no import/startup e não muda conexões existentes. Aplicada nesta entrega apenas
ao banco isolado; não aplicada ao HarpiServer.

Executar migração com proprietário separado do usuário de runtime. Conceder
ao runtime somente:

```sql
GRANT USAGE ON SCHEMA hs_config TO config_runtime;
GRANT SELECT, INSERT, UPDATE ON hs_config.installation, hs_config.operation TO config_runtime;
GRANT SELECT, INSERT ON hs_config.revision, hs_config.audit, hs_config.receipt TO config_runtime;
GRANT USAGE ON SEQUENCE hs_config.audit_id_seq TO config_runtime;
```

`config_runtime` é nome ilustrativo; sua criação e credenciais pertencem à
instalação. Sem DELETE/TRUNCATE/DDL. Triggers recusam UPDATE/DELETE nas
revisões, auditoria e recibos. Administrador do banco continua sendo autoridade
privilegiada; isso não substitui backup, assinatura externa ou retenção protegida.

## Validação executada

PostgreSQL **18.6**, container exclusivo `harpisense-config-stage1-db`, banco
`config_fixture`, publicação somente em `127.0.0.1:55441`. Nenhum banco de
autenticação ou operação foi usado. Testes recusam outro nome de banco.

```powershell
$env:PYTHONPATH = 'backend;backend/domain'
# HARPISENSE_CONFIG_TEST_DSN deve apontar para a fixture isolada config_fixture.
python -m unittest discover -s backend/config_manager_tests -v
```

Resultado: **21 testes aprovados**, sendo 5 de esquema e 16 com PostgreSQL
real. Cobrem migração repetível, tabela alheia preservada, concorrência de
conexões, retry simultâneo, histórico, rejeição durável, separação de estados,
todos os recibos por componente, falha parcial, reinício do gerenciador,
fencing, ACL/compatibilidade, segredos ausentes e papel SQL sem permissão para
alterar/apagar/truncar o histórico. Não são testes de implantação operacional.

API/preview autenticado, aplicadores, conectividade, recuperação externa,
restauração de backup e ativação no servidor ficam para as próximas etapas.
