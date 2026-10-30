# Conta administrativa e sessão — candidata aditiva, 29/10/2026

> Registro histórico da candidata `460c8a3`. A integração e as verificações de
> 30/10 estão em [Integração de conta administrativa](INTEGRACAO_CONTA_ADMINISTRATIVA_20261030.md).
> O estado de implantação atual deve ser consultado nesse relatório.

## Base, responsabilidade e limites desta rodada

Base confirmada pelo arquiteto: branch `feat/frontend-backend-autonomia`, worktree
`D:/Projetos/tcc - harpisense/harpisense-worktrees/frontend-backend-autonomia`,
HEAD inicial `901053edad08e5f86933a369bfa82878f18b0423`.
Alterações desta entrega restritas a `backend/admin_auth/`,
`backend/admin_auth_tests/` e este documento. Mudanças concorrentes no frontend e
`docs/continuity/` pertencem ao arquiteto e foram preservadas.

O arquiteto confirmou por inspeção SSH a composição da VM gateway:

- `/opt/harpisense/staging/p11-postgresql/app.py`, SHA-256
  `52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2`;
- `create_app` de `/opt/harpisense/integration-v2/HarpiSense_Pacote13_Integracao_Testes_v2/componentes/p11/backend11/service.py`;
- `PostgresStore` em `postgres_store.py`, SHA-256
  `cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c`;
- bootstrap lê `HARPISENSE_DATABASE_URL` e instala `install_deterministic_harpia(app,store)`;
- consumidor existente grava diretamente no mesmo banco, tópico
  `harpisense/poste2/telemetry`, `device_id=poste2`.

Essas observações são informações recebidas do arquiteto; esta implementação não
acessou a VM. Nenhum bootstrap, PostgresStore, `backend/delivery`, frontend,
`genai`, P08/P09, telemetria, modelo, executor, rede ou firewall foi alterado.
Não houve implantação, migração remota, habilitação REAL/BitNet operacional,
commit ou push. A instrução posterior reserva revisão e commit ao arquiteto.
O módulo é opt-in; sua presença no disco não altera a autenticação existente.
**Não substituir o P11 ativo por `backend/delivery`.**

Referências locais lidas: P11 V2 `backend11/service.py`, documentação e contrato
do frontend da base candidata e referências anteriores
`Versões corretas/HarpiSense_Backend_Operacional_v1` (Basic por ambiente).
O último é legado preservado, não um serviço ausente ou substituto a instalar.
Os contratos de domínio permanecem na fonte canônica já incorporada.

## Mecanismo e política

Sessão opaca Bearer: token aleatório de 256 bits entregue somente no login;
PostgreSQL guarda SHA-256 do token. O navegador deverá guardar o token apenas
em memória, nunca em URL, localStorage, sessionStorage ou logs. Recarregar a
página exige novo login; não há refresh token. Cada login cria token novo.

Essa escolha corresponde ao transporte atual: `frontend/src/api.ts` usa
Authorization e `credentials:'omit'`; `frontend/scripts/p11-proxy.mjs` remove
Set-Cookie. O proxy atualmente não libera as novas rotas de autenticação.
**O frontend atual ainda não consome esta API**; sua adaptação pertence ao
arquiteto. Não há compatibilidade implícita que transforme Basic em sessão.

Não são emitidos cookies, portanto HttpOnly/SameSite/Secure não se aplicam a
esta candidata. A credencial Bearer exige cabeçalho explícito e não é enviada
automaticamente pelo navegador, evitando o vetor usual de CSRF por cookies.
Requisições com Origin recebem checagem contra lista exata, incluindo login.
Não se cria CORS; publicar preferencialmente na mesma origem via proxy HTTPS.
Se CORS for necessário, liberar somente origens e cabeçalhos explícitos,
sem wildcard e sem credenciais de cookies. Nunca mover o token para cookie sem
revisar CSRF, HttpOnly, SameSite e Secure. XSS ainda pode usar tokens em memória;
a aplicação deve manter CSP e proteção de conteúdo no ponto de publicação.

- Senha: scrypt N=131072, r=8, p=1, salt aleatório de 16 bytes, saída de 32 bytes,
  formato versionado; custo aproximado de memória de 128 MiB por hash.
- Senha nova: 15–128 caracteres, até 512 bytes UTF-8; sem truncamento ou remoção
  silenciosa de espaços. Usuário case-sensitive, 3–64 caracteres ASCII
  `[A-Za-z0-9_.@-]`. Não há conta/senha padrão.
- Sessão: limite absoluto de 8 h e inatividade de 30 min; relógio do PostgreSQL.
  Consulta autenticada atualiza a atividade sem estender o limite absoluto.
- Logout revoga a sessão apresentada. Alterar usuário ou senha exige a senha
  atual e revoga **todas** as sessões, inclusive a que solicitou a alteração,
  na mesma transação que incrementa a revisão da credencial.
- Throttle global do único administrador, compartilhado por login e
  reautenticação: primeiras cinco falhas são processadas; após a quinta há
  espera de 2 s, dobrando até 60 s. Tentativas durante a espera recebem 429 e
  não prolongam o prazo. Login/reautenticação válidos zeram o contador.
  Usuários inventados não criam buckets extras; reiniciar o processo não zera
  o estado. Sessões já válidas continuam consultando o sistema durante a espera.
  Não há bloqueio permanente nem recuperação fictícia. Um atacante contínuo
  ainda pode disputar as janelas do administrador; limitar tráfego no proxy é
  uma proteção complementar da implantação, não foi configurada nesta rodada.
- Lock transacional exclusivo de autenticação; sem interferência no advisory
  lock de projeções ou na coordenação P08/P09/autonomia. Lock timeout 5 s,
  statement timeout 10 s e conexão 5 s; falha é 503, sem fallback.
- JSON de autenticação limitado a 4096 bytes e campos extras recusados.
  Erros de validação são redigidos, pois o retorno padrão do Pydantic pode
  incluir o valor rejeitado de uma senha.

Referências de segurança: [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
para o perfil scrypt e [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
para identificadores imprevisíveis e revogação. A escolha Bearer decorre da
inspeção do transporte específico deste projeto.

## Inventário Basic e transição controlada

| Consumidor | Estado anterior | Com instalador opt-in |
|---|---|---|
| Dashboard/API P11 GET health, listas, history e explain | Basic `HARPISENSE_ADMIN_USER/PASSWORD` | Somente conta/sessão Bearer; Basic técnico recusado |
| HarpIA determinística | Dependência administrativa herdada do P11 | Mesma explicação, agora protegida por sessão |
| Controles settings, emergency-stop e audit que reutilizam a mesma dependência P11 | Basic | Sessão; sem mudar regras ou execução |
| POST `/api/v1/p11/ingest/{kind}` | Basic + `HARPISENSE_PROJECTION_SERVICE_TOKEN` | Mantém **ambos**, restrito a essa rota técnica; Bearer administrativo não o substitui |
| Consumidor MQTT da VM | Escrita direta via Store/PostgreSQL | Não afetado; sem login administrativo ou sessão |
| Gateway/API legada `backend/app/core/security.py` | `HARPI_GATEWAY_USERNAME/PASSWORD`; admin legado `HARPI_ADMIN_*` | Fora da composição P11; não é montada nem modificada |
| PostgreSQL, MQTT, AWS e demais integrações | Credenciais próprias no host | Continuam no host, nunca retornadas pela API |

O instalador troca apenas consumidores da **mesma função** administrativa
encontrada na health P11, excetuando o POST técnico exato. Funções de autenticação
independentes ou serviços legados montados separadamente precisam ser inventariados
e protegidos explicitamente pelo arquiteto; não manter uma rota administrativa
alternativa com Basic. Novas rotas administrativas usam a dependência devolvida
pelo instalador. Nada deve encaminhar credenciais técnicas em nome do navegador.

O serviço rejeita usuário/senha que reutilizem pares técnicos fornecidos por
`technical_credentials=[(usuario,senha), ...]`, os pares de ambiente conhecidos
`HARPISENSE_ADMIN_*`, `HARPI_ADMIN_*`, `HARPI_GATEWAY_*`, `HARPI_MQTT_*`, e a senha
presente no conninfo PostgreSQL. Não busca segredos em outros hosts nem garante
detecção de reutilização de valores ausentes do ambiente (pgpass, cofre externo,
AWS, etc.). Operador deve criar uma senha própria. Não altera qualquer segredo
técnico. A API não aceita uma credencial técnica como alternativa à sessão.

## Migração e provisionamento — execução futura pelo arquiteto

O mecanismo observado na candidata usa SQL explícito (`001_local.sql`); o Alembic
da API legada não deve ser usado para inventar outra base P11. A nova migração
é `backend/admin_auth/001_admin_auth.sql`, aditiva, transacional e versionada.
O arquiteto deve conferir o mecanismo efetivo da VM antes de integrar e registrar
essa migração nele, mantendo o conteúdo revisável. Nenhum import executa DDL.

Estruturas novas no **mesmo banco P11**: `hs_admin_account` (singleton),
`hs_admin_session`, `hs_admin_throttle`, `hs_admin_audit` e
`hs_admin_schema_version`. Não altera `projections`, modelos, telemetria,
auditoria/controles existentes ou tabelas técnicas. Nova execução do SQL recusa
DuplicateTable e faz rollback, preservando dados; não oculta divergências com
CREATE IF NOT EXISTS. Não executar duas ferramentas de migração em paralelo.

Procedimento proposto, **não executado na VM**:

1. Confirmar hashes de origem informados acima e diferenças remotas; fazer backup
   do banco e bootstrap com restauração verificável em ambiente isolado.
2. Revisar SQL e privilégios: papel de migração executa DDL; papel da API precisa
   apenas SELECT/INSERT/UPDATE nas tabelas de conta/sessão/throttle e INSERT na
   auditoria/uso da sequence. A API não precisa permissão de DROP/CREATE.
3. Aplicar o SQL uma vez no banco existente, com psql `ON_ERROR_STOP=1` e conexão
   obtida do host, sem expor DSN/senha no histórico ou saída. Registrar versão.
4. Com `PYTHONPATH` incluindo `backend` e `HARPISENSE_DATABASE_URL` do host,
   executar em terminal do operador `python -m admin_auth provision`. Solicita
   usuário e duas entradas de senha ocultas via getpass; recusa stdin não
   interativo. Não há endpoint de cadastro/provisionamento nem senha por argumento.
5. Integrar opt-in após os instaladores existentes, antes de servir requisições:

```python
# Exemplo para o bootstrap REAL. Não substituir pelo backend/delivery.
from admin_auth import AdminAuth, install_admin_auth

# store = PostgresStore(conninfo), app = create_app(store), instalação HarpIA etc.
require_admin = install_admin_auth(
    app,
    AdminAuth(conninfo),  # mesmo HARPISENSE_DATABASE_URL já usado pelo Store
    allowed_origins=['https://endereco-real-do-dashboard.example'],
)
# Rotas administrativas adicionais: Depends(require_admin).
```

O exemplo de origem é documental e deve ser substituído pela origem real exata.
HTTP só é aceito como origem de desenvolvimento em localhost/loopback; publicação
externa exige HTTPS ou túnel protegido até proxy HTTPS. O módulo não configura
TLS, proxy, bind ou cabeçalhos de encaminhamento.

Instalar após HarpIA/controles porque estes localizam a dependência P11; não montar
novas rotas dependentes do Basic antigo posteriormente. FastAPI alvo 0.115.0 e
psycopg existente, sem nova dependência runtime. A operação usa a árvore de
dependências do FastAPI; nova versão/composição requer repetir testes HTTP.
Instalação duplicada ou overrides preexistentes são recusados para evitar bypass.

6. Adaptar somente o transporte/comportamento de autenticação do frontend e proxy
   na rodada do arquiteto: liberar as cinco rotas abaixo, trocar Basic por Bearer,
   descartar token ao sair/401/mudar configuração e não injetar credenciais técnicas.
   Corpo e Authorization devem ser redigidos nos logs de proxy/APM. O módulo
   não registra senhas, cabeçalhos ou tokens e usa `Cache-Control: no-store` nas
   respostas de autenticação; conservar essa política também no proxy P11.
7. Verificar conta própria, sessão, Basic técnico restrito, telemetria existente,
   explicação determinística e autonomia preservadas antes da disponibilização.

Recuperação: se a migração falhar, a transação inteira é revertida; se houver
problema no código após migração, interromper publicação administrativa e voltar
ao bootstrap anterior preservado, mantendo as tabelas e os dados novos para análise.
Esse rollback reativa o Basic anterior, portanto só deve ocorrer com o acesso
administrativo isolado. Não há fallback automático para Basic em falha de sessão.
Não há downgrade que remova dados nem reprovisionamento destrutivo. Se perder a
senha, manter acesso administrativo fechado e planejar recuperação local auditada;
nenhum reset por e-mail ou senha universal foi implementado.

## Contrato HTTP para integração do frontend

Prefixo `/api/v1/admin-auth`. JSON UTF-8, sem campos extras.
Sessão protegida por `Authorization: Bearer <access_token>`; token nunca em query.

| Método/rota | Corpo | Sucesso |
|---|---|---|
| POST `/login` | `username`, `password` | 200: `access_token`, `token_type:"Bearer"`, `expires_at` ISO UTC, `idle_timeout_seconds:1800`, `username` |
| GET `/session` | Nenhum | 200: `authenticated:true`, `username`, `expires_at`, `idle_timeout_seconds`, `mfa_available:false`, `email_recovery_available:false` |
| POST `/logout` | Nenhum | 204 vazio; sessão revogada |
| PUT `/password` | `current_password`, `new_password` | 200: `status:"credentials_changed"`, `login_required:true`, `sessions_revoked:"all"` |
| PUT `/username` | `current_password`, `new_username` | Mesmo 200 de alteração de senha |

Não existe renovação automática, cadastro público, endpoint MFA ou recuperação.
Logout com sessão já inválida/expirada retorna 401; frontend deve sempre apagar
o token local e exibir necessidade de login, sem tratar isso como logout remoto
confirmado se houver indisponibilidade.

Erros são `{"error":{"code":"..."}}`, sem senha, identificador de sessão ou
indicação pública de existência da conta. HTTP 401 inclui WWW-Authenticate Bearer.

| HTTP/código | Estado de tela e ação |
|---|---|
| 401 `INVALID_CREDENTIALS` | Login inválido; mensagem genérica para usuário inexistente, senha errada ou conta não provisionada |
| 401 `AUTH_REQUIRED` | Sem Bearer válido; solicitar login |
| 401 `SESSION_INVALID` | Token desconhecido; descartar e solicitar login |
| 401 `SESSION_EXPIRED` | Expiração absoluta/inatividade; descartar e informar expiração |
| 401 `SESSION_REVOKED` | Logout/mudança de credencial invalidou sessão; solicitar login |
| 403 `REAUTHENTICATION_REQUIRED` | Senha atual não confirmou identidade; não aplicar alteração |
| 403 `ORIGIN_DENIED` | Origem não autorizada; corrigir configuração do transporte |
| 429 `TRY_LATER` + Retry-After | Aguardar segundos informados; não repetir automaticamente |
| 422 `INVALID_REQUEST`, `INVALID_USERNAME`, `INVALID_PASSWORD`, `TECHNICAL_CREDENTIAL_REUSE` | Formulário inválido ou reutilização proibida; mostrar orientação sem ecoar senha |
| 413 `REQUEST_TOO_LARGE` | Corpo acima de 4096 bytes |
| 503 `AUTH_UNAVAILABLE` | Persistência/migração indisponível; não declarar mudança/login confirmados e não tentar Basic |
| 404 para cadastro/MFA/recuperação | Recurso ainda não disponível |

O resultado de alterações só é retornado após commit no PostgreSQL. Se a rede
falhar após o commit, o navegador pode não receber confirmação; não repetir
alteração automaticamente, apagar sessão local e consultar/login novamente.

Auditoria separada em `hs_admin_audit`: PROVISION, LOGIN, LOGOUT,
PASSWORD_CHANGE e USERNAME_CHANGE, instante, id estável da conta quando conhecido
e código de resultado, incluindo recusas de credenciais e throttle. Sem IP,
nome submetido, senha/hash de senha, token/hash de token ou payload bruto.
O endpoint existente `/api/v1/security/audit` continua servindo sua auditoria de
controles; este módulo não inventa unificação dessas fontes. Consulta e política
de retenção/exportação da nova auditoria devem ser integradas pelo arquiteto.
Manter tombstones de sessões revogadas/expiradas pelo prazo de diagnóstico;
após expurgo controlado elas passam a SESSION_INVALID. Não há job automático.

MFA futuro: instalar etapa adicional entre verificação da senha e criação de
sessão, com desafio tipado/expirável e armazenamento próprio de fatores/recibos;
nesta entrega login não afirma MFA. Recuperação futura precisa canal verificado,
token de uso único, expiração, auditoria e revogação; não há envio de e-mail,
endpoint fictício, QR demonstrativo ou sucesso simulado.

## Verificação local e evidências

PostgreSQL **18.6 descartável**, banco `auth_fixture`, rede Docker exclusiva,
sem porta publicada, dados em tmpfs. Código montado somente para leitura na
imagem local `harpisense-backend:integration`. Nenhum banco operacional usado.
Testes de autenticação exigem `ADMIN_AUTH_TEST_DATABASE_URL` explicitamente e
recusam reset de fixtures se `current_database()` não for `auth_fixture`.

Com PYTHONPATH=`backend:backend/domain:genai` e PYTHONDONTWRITEBYTECODE=1:

```text
python -m unittest discover -s backend/admin_auth_tests -v
# ADMIN_AUTH_TEST_DATABASE_URL = DSN do auth_fixture descartável

python -m unittest discover -s backend/delivery_tests -v
# TEST_DATABASE_URL = DSN do mesmo auth_fixture descartável
```

Resultados: **21 testes de autenticação aprovados**, **18 regressões existentes
de delivery/P11 aprovadas**. A suíte cobre provisionamento singleton/concorrrente,
ausência de cadastro HTTP, hash/salt e hash corrompido, login, sessões persistidas entre instâncias,
expiração absoluta/inatividade, revogação/logout, alterações com reautenticação,
throttle persistido/global, erros seguros, separação técnica, limites de payload,
migração ausente/reexecução, rollback em falha da auditoria, P11, telemetria persistida, HarpIA determinística e
controles protegidos. As regressões incluem Policy/autonomia, simulação isolada,
recusa REAL, filas desconhecidas, concorrência e PostgreSQL.

Os testes usam como fixture a fábrica P11 local compatível, sem implantá-la ou
substituir a fábrica remota. Compatibilidade com o arquivo real e proxy/frontend
da VM ainda exige teste de integração controlado pelo arquiteto. Não há teste
end-to-end de navegador nesta entrega nem alegação de validação remota.
