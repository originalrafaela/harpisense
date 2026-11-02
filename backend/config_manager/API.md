# API e assistente de primeira configuração

Atualização de integração: existe agora aplicador **opcional e limitado à
apresentação**, conforme [PRESENTATION.md](PRESENTATION.md). Quando instalado
explicitamente pelo bootstrap, acrescenta GET presentation e POST
proposals/{uuid}/apply com reautenticação, além de metadados de escopo em
current/catalog. Sem essa opção, permanecem válidas as limitações da entrega
original abaixo. Operational continua false em ambos os casos; os demais
grupos continuam sem aplicadores. Descrições antigas de ausência de rotas de
aplicação referem-se à composição original sem essa opção.

Continuação de `feat/config-manager-stage1`, commit
`edd0cb7e1d92e14a2518790db61a7b0c0ffef8dd`. Branch desta entrega:
`feat/config-manager-api`, worktree `harpisense-worktrees/config-manager-api`.

## Coordenação pendente

Em 01/11/2026, `maestri list` identificou este terminal como
`Gerenciador de configurações`, sem agentes conectados. Não houve destinatário
descoberto nem confirmação do arquiteto. Não foi enviado pedido a nome presumido.
Encaminhamento manual ao arquiteto: confirmar o commit acima como base; revisar
o instalador abaixo, manifesto Capabilities e identidade da instalação; integrar
após autenticação administrativa existente. A entrega não ativa rotas no bootstrap.

## Integração

Reutilizar a conexão PostgreSQL de runtime, sem outro banco ou credenciais.
Bootstrap (DSN, usuário SQL, bind e credenciais iniciais) continua sendo responsabilidade
do instalador externo, antes da API e do login. O assistente administra apenas o
ambiente já instalado; não oferece configuração do banco que o sustenta.

Executar explicitamente, com proprietário de migração, nesta ordem:

```python
from config_manager.store import migrate, ConfigStore
from config_manager.setup import migrate_setup
from config_manager.api import install_config_api

migrate(existing_connect)
migrate_setup(existing_connect)
# No bootstrap aprovado pelo arquiteto, após install_admin_auth(...):
store = ConfigStore(existing_connect, trusted_capabilities)
store.provision_registry(installer_installation_id)
install_config_api(app, store, installation_id=installer_installation_id)
```

Não executar migração no startup. `002_setup.sql` é aditiva; o executor usa
lock e checksum próprios sem alterar a migração 001. Permissões adicionais ao
papel de runtime existente: USAGE hs_config; SELECT/INSERT/UPDATE em
setup_progress; SELECT/INSERT em setup_request e setup_audit; USAGE na sequência
setup_audit_id_seq. Sem DDL, DELETE ou TRUNCATE. Recibos e auditoria de progresso
são imutáveis para UPDATE/DELETE. Instalador pode conceder SELECT em setup_schema
somente se precisar consultar sua versão; runtime não executa migrações.

Todas as rotas usam `app.state.require_admin_session`, instalado pelo módulo
`admin_auth`. Bearer de sessão administrativa, mesma validação de origem, expiração
e revogação; Basic/contas técnicas não autorizam estas rotas. O ator persistido
`admin-account-1` corresponde ao singleton id=1 de hs_admin_account; não usa o
username mutável. Uma futura autenticação com múltiplas contas exige adaptar esse
mapeamento a uma identidade estável fornecida pela sessão.

Não há operação sensível de aplicação/alteração de credenciais neste router.
Reautenticação de credenciais continua nas rotas existentes. Aplicação futura
deve reutilizar a reautenticação aprovada antes de chamar begin_application.
Nenhuma rota permite recibos, confirmação, comandos ou aplicação pelo navegador.

## Contrato para frontend

Prefixo `/api/v1/config`; respostas JSON com `Cache-Control: no-store`.
Sem campos de senha/token/DSN; referências opacas seguem o esquema da etapa 1.
Não registrar bodies ou Authorization em middleware/proxy. Campos de texto livre
como display_name servem apenas para rótulos; nunca inserir segredos nesses campos.

| Método/caminho | Contrato |
| --- | --- |
| GET /current | revisão desejada/efetiva, documentos proposto/efetivo, status e state |
| POST /proposals | config.proposal v1 completo, mesmo schema exportado da etapa 1 |
| GET /proposals/{uuid} | snapshot, operação e resultado/status persistido, somente instalação local |
| POST /proposals/{uuid}/validate | `{ "expected_revision": 1 }`; valida esquema e Capabilities |
| GET /history?after=0&limit=100 | auditoria de propostas/aplicação; paginação por id, máximo 500 |
| GET /setup | versão/documento/updated_at/state/pending; vazio = versão 0, documento null |
| PUT /setup | snapshot parcial do assistente, expected_version e idempotency_key |
| GET /catalog | perfis de firmware/implantação e limitações de aplicação |

Erros: 401 sessão ausente/inválida/revogada; 403 origem recusada; 404 operação
ausente ou de outra instalação; 409 concorrência/idempotência; 413 body >64 KiB;
422 esquema/valores/referências. `error.code` é estável; `error.fields` contém
`field` e `code`, sem valores submetidos. Para restrições entre campos, destaca-se
o grupo de campos relacionados. Campos desconhecidos são reportados no pai seguro.
Conflitos de assistente usam current_revision como versão atual do progresso.

PUT /setup aceita `document.step` (installation, deployment, devices, mqtt,
capture, backup, review), parameters parcial (mesma lista permitida da etapa 1),
deployment_profile opcional esp32-lighting, devices opcionais com device_id,
firmware_id e firmware_version do catálogo, backup opcional deferred ou
external_reference. external_reference prepara a escolha; a referência de segredo
fica em parameters.external_credential_ref. Não habilita backup.

Salvar progresso aceita grupos incompletos, não muda revisões de configuração e
não valida referências operacionais. O frontend retoma o snapshot, permite avançar
e voltar nas etapas e só envia config.proposal completo na revisão final. Identificação
administrativa é display_name/timezone; a identidade técnica vem do instalador.
Trocar documento usa nova chave e versão atual; repetir pedido idêntico usa a mesma
chave e devolve a resposta original, inclusive após reinício. Não misturar a versão
do progresso com expected_revision da configuração.

GET/PUT setup também retornam state=draft_saved (not_started no registro vazio),
operational=false e pending com pendências preparatórias por seção. Esses avisos
são independentes da validação da proposta; para seu resultado consultar current
ou a proposta. Presença de campo não é prova de completude/validade/conectividade.

Exemplo sanitizado de progresso:

```json
{"expected_version":0,"idempotency_key":"setup-example-001","document":{"step":"devices","deployment_profile":"esp32-lighting","parameters":{"display_name":"Instalação exemplo","timezone":"America/Sao_Paulo"},"devices":[{"device_id":"poste-1","firmware_id":"esp32-wroom32-lighting","firmware_version":"1.0.0"}],"backup":"deferred"}}
```

Proposta sanitizada (UUID/chaves novos para cada edição):

```json
{"schema_version":"1.0.0","record_type":"config.proposal","request_id":"b2c88755-a41a-407c-bd2f-1f3c67572810","idempotency_key":"proposal-example-001","expected_revision":0,"reason_code":"INITIAL_IMPORT","document":{"schema_version":"1.0.0","record_type":"config.document","parameters":{"display_name":"Instalação exemplo","timezone":"America/Sao_Paulo"}}}
```

## Estados e revisão final

`state`: not_started, draft_saved (DRAFT), validated (VALIDATED),
application_pending (APPLYING), applied_verified (APPLIED), failed
(REJECTED/FAILED/RECOVERY_REQUIRED). Status original continua disponível para
distinguir rejeição, falha e necessidade de reconciliação. Progresso salvo é
rascunho, mesmo com step=review; não é configuração validada.

Nenhum aplicador está habilitado nesta rodada: applicability é
not_applicable_no_real_applicators e operational=false. Preservam-se leitura
de resultados reais gravados por integrações confiáveis e todos os controles
de revisão/fencing/recibos anteriores. Validar não aplica nem verifica.

A revisão final deve mostrar: referências não aprovadas, grupos incompletos,
firmware pendente de validação física/contrato, MQTT/rede/captura/backup sem
aplicadores, nenhuma verificação operacional e backup deferred quando escolhido.
O catálogo explicita available=false; selecionar perfil apenas prepara inventário.
Não existe Arduino disponível nem segundo cenário implementado.

## Fontes

Precedência mantida: referencias/versão_v2, complementada por Versões corretas
para componentes não atualizados. README do P05 V2 declara implementação
condicional, contrato pendente e ausência de validação física; não promoveu
esse firmware a operacional. Código existente iot/esp32/poste1 preservado.
Não havia catálogo de perfis de firmware na base; o catálogo de ações em
backend/domain/harpisense_catalog.py é de Risk/Policy e permanece intacto.
Os perfis aqui são metadados preparatórios, sem outro catálogo de parâmetros,
ações ou segredos. Capabilities continua a autoridade de referências aprovadas.

## Testes

PostgreSQL exclusivo `harpisense-config-api-db`, porta loopback 55442, banco
config_fixture. Configurar HARPISENSE_CONFIG_TEST_DSN por canal local e executar
`python -m unittest discover -s backend/config_manager_tests -v` com backend e
backend/domain no PYTHONPATH, dependências de config_manager, admin_auth e
FastAPI 0.115/httpx disponíveis. Nenhum teste deve usar banco operacional.

Validação em 01/11/2026: suíte completa com 27 testes aprovada; após acrescentar
pendências explícitas e rejeição de bootstrap/segredos no progresso, suíte HTTP
com 7 testes reexecutada. Cobertura inclui login/sessões reais, anonimato e sessão
inválida em todas as rotas, origem negada, escopo por instalação, validação com
erros por campo, histórico, idempotência, conflito entre escritores e retomada
com conexão/Store recriados. Os 21 testes anteriores preservam verificação de
recibos, falhas, fencing, concorrência e permissões no PostgreSQL.
