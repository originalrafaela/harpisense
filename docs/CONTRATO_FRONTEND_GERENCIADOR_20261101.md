# Contrato confirmado — composição candidata local

Base 4421cdb; entregas edd0cb7 e 2269bc0 incorporadas por cherry-pick.
API existente: backend/config_manager/API.md e schemas exportados continuam
autoridade dos DTOs. Precedência de referências: Versao_v2 (diretório real
referencias/versão_v2); Versões corretas para componentes ainda não atualizados.
Nenhum pacote foi considerado ausente pela falta de versão V2.

## Diferenças resolvidas

A proposta anterior com /installations/{installation} e /operations/{id}
fica substituída pelas rotas abaixo. A instalação é fixa e fornecida pelo
instalador, nunca escolhida pelo navegador. Consulta histórica por revisão
continua interna; a API consulta proposta por UUID e auditoria por cursor.
API entregue acrescenta progresso persistente e catálogo preparatório existentes;
nenhuma API/autenticação/catálogo/banco concorrente foi criado.

Prefixo efetivo na candidata: /api/v1/config. Autorização: Bearer da mesma
sessão obtida em POST /api/v1/admin-auth/login. Não usar Basic técnico.
Mesmo controle de origem, revogação e expiração. Cache-Control: no-store.

| Método e sufixo | Uso no assistente |
| --- | --- |
| GET /current | revisão desejada/efetiva, documentos e status/state |
| POST /proposals | config.proposal completo conforme REQUEST_SCHEMA |
| GET /proposals/{operation_id} | operação/snapshot/status da instalação local |
| POST /proposals/{operation_id}/validate | objeto expected_revision inteiro |
| GET /history?after=0&limit=100 | cursor ID; máximo 500 |
| GET /setup | retomar documento/version/state/pending; updated_at após salvar |
| PUT /setup | expected_version, idempotency_key, document completo do progresso |
| GET /catalog | firmware_profiles, deployment_profiles, applicators vazio |

Sem rota de aplicação. POST /api/v1/config/apply retorna 404. Nenhum recibo
ou atestado enviado pelo browser é aceito como verificação operacional.

Fluxo frontend: login → GET setup/current/catalog → editar snapshot parcial →
PUT setup → POST proposals na revisão final → POST validate → GET current.
Reabrir sessão/aplicação → GET setup e current para retomar. O frontend visual
ainda não foi conectado nesta rodada; o fluxo acima foi testado por HTTP local.

PUT /setup retorna version/document/state/operational/pending; GET /setup
acrescenta updated_at quando existe progresso. Não comparar objetos inteiros
como se o recibo de PUT tivesse timestamp. Em registro vazio, GET retorna
version=0 e document=null, sem updated_at. O teste composto confirma versão e
documento conservados após recriar aplicação e conexão.

expected_version é versão do progresso; expected_revision é revisão da
configuração. Não intercambiar. Retry idêntico usa a mesma chave e body;
edição usa nova chave e versão/revisão atual. Documentos são snapshots, não
PATCH. Em 409, buscar estado atual antes de reapresentar conflito ao operador.
401 pede novo login; 403 origem recusada; 404 proposta ausente/fora do escopo;
413 body acima de 64 KiB; 422 erros sanitizados com error.code e error.fields.

Ator persistido é admin-account-1, identidade estável do singleton existente.
Capabilities e installation_id vêm do instalador confiável. MFA/recuperação
de e-mail continuam indisponíveis; esta API não declara aplicação sensível
autorizada nem acrescenta autenticação alternativa.

## Composição, provas e limites

delivery.app.build_candidate_app(installation_id=..., capabilities=...,
allowed_origins=...) compõe build_app existente, depois install_admin_auth,
depois install_config_api. DATABASE_URL é o mesmo para todos. A factory não
executa DDL, migração, provisionamento de conta ou registro de instalação.
Chamadores anteriores de build_app permanecem compatíveis. O instalador deve
preparar schemas/identidade explicitamente antes de servir a candidata.
O instalador também repassa technical_credentials ao AdminAuth existente para
preservar sua recusa de credenciais técnicas como senha administrativa; referências
em variáveis aprovadas continuam sendo lidas pelo mesmo módulo. Não registrar
esses valores. Basic mais token de serviço na ingestão técnica P11 foi preservado
e testado; Basic técnico sozinho não acessa o gerenciador.

29 testes config_manager aprovados sem pulos (7 HTTP, 1 composição, 21 base).
18 testes delivery aprovados sem pulos, inclusive PostgreSQL. Container exclusivo
harpisense-composition-20261101, PostgreSQL 18.6 em loopback 55443, config_fixture.
Python 3.12 no venv local já existente; nenhum banco operacional acessado.
Reprodução: PYTHONPATH=backend;backend/domain;genai; definir
HARPISENSE_CONFIG_TEST_DSN para fixture config_fixture; unittest discover
-s backend/config_manager_tests -v. Para delivery, TEST_DATABASE_URL aponta
à mesma fixture descartável e executar discover -s backend/delivery_tests
-p test_delivery.py -v. Nunca executar essas suítes em banco operacional.

Teste composto: login pela rota real, proposta/validação, persistência/retomada
após nova factory, P11/health, HarpIA determinística, controles, Poste 2 insert/retry,
Poste 1 disabled, logout e recusa da sessão revogada. Sem conexão MQTT real.
Validar proposta deixa effective_revision=null e operational=false; não aplica.
Nenhum parâmetro foi aplicado ao servidor. Consumidores não foram modificados.

Hardware atual: ESP32-WROOM-32, LDR/LED. API mantém perfil preparatório existente
e available=false. Entrega fdfd27e foi lida: ensaio Wokwi preparado, não executado;
build ESP32/Wokwi falhou por CreateProcess, sem novo ELF homologado. Os testes
nativos/payloads reportados pelo IoT não comprovam hardware/TLS/ACL. Não houve
cherry-pick de firmware, gravação ou habilitação. Outros perfis continuam extensão
futura; parâmetros usam schema, Capabilities e referências, sem fixar IP de laboratório.

## Comparação e preparação para implantação posterior

Nenhuma implantação/migração/backup remoto executado. Antes de autorizar:

1. Recuperar SSH administrativo. Ler hashes e versões instalados de bootstrap,
   admin_auth, P11/Record/PostgresStore, HarpIA e callbacks; comparar com candidata.
   Confirmar DSN via canal protegido sem imprimi-lo, papel SQL, identity singleton,
   installation_id e manifesto Capabilities aprovado. Não usar manifesto do browser.
2. Preparar release imutável e manifesto SHA256; preservar app original,
   dependências, unidade e configuração protegida com permissões e hashes.
   Reutilizar rotina de backup/recibo já existente em admin_auth_ops como referência;
   não reutilizar seu activate para gerenciador sem adaptar/comparar bootstrap.
3. Antes de DDL, pg_dump custom do banco existente em destino protegido, hash e
   recibo de contagem/digest de projeções. Restaurar em PostgreSQL isolado e conferir
   projeções, conta/sessões e integridade; ensaiar as migrações nesse restore.
4. Migração explícita pelo proprietário: config_manager.store.migrate(connect),
   depois config_manager.setup.migrate_setup(connect). Conferir checksums/locks.
   Se hs_config já existir, não presumir versão: comparar primeiro. Conceder somente
   privilégios runtime documentados em README/API.md, sem DDL/DELETE/TRUNCATE.
   provision_registry usa identidade externa aprovada; não redefinir conta ou senha.
5. Só depois da comparação e ensaio de restauração preparar autorização de troca.
   Abortar se login/P11/Poste 2/HarpIA divergir ou schema/checksum não corresponder.
   Recuperação de código volta ao bootstrap/dependências do mesmo backup; manter
   tabelas aditivas e registros em vez de apagar auditoria. Se necessário restaurar
   banco, exigir janela sem escrita e plano para não perder telemetria posterior;
   não restaurar snapshot antigo automaticamente. Validar login e consumidor após.

Esses são gates concretos pendentes, não provas já executadas de recuperação da VM.

## Navegador e continuidade

maestri list: nenhum agente/portal conectado. Tentativas SSH em
192.168.155.144 com identidade antiga e 100.66.89.7 com identidade Maestri
retornaram Permission denied (publickey,password). Nenhuma mudança remota.
Túnel/preview não restabelecidos: script aprovado exige handshake Bearer e não
foi contornado. Pedido ao operador para recuperar acesso pelo canal habitual,
sem credenciais no chat. Após túnel disponível: activate-admin-preview.ps1,
criar/conectar portal observável, operador entra no formulário; então observar
polling/logout/expiração. HTTP local da fixture não substitui esse aceite.

Próxima etapa objetiva frontend: conectar assistente visual às oito rotas acima
em ambiente candidato isolado e exibir claramente salvo/validado/sem aplicador.
Próxima etapa operacional: recuperar SSH para comparação e ensaio de backup/restore,
sem instalar gerenciador na VM nesta rodada.
