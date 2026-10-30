# Integração de conta administrativa — 30/10/2026

Branch `feat/frontend-backend-autonomia`, candidata original `460c8a3`.
Não houve merge na main. A referência mais recente é `referencias/versão_v2`,
incluindo P11/P13 e o consolidado de 27/10. Os módulos anteriores de
`referencias/Versões corretas` continuam preservados e foram consultados para
autenticação e interface legadas; ausência em V2 não foi tratada como ausência
de implementação. Nenhum pacote legado foi implantado sobre o P11 ativo.

## Sequência e aceite de telemetria

Antes da integração, o operador enviou o registro
`poste2-d3c4e04b4fb6b30220b1d4f5d618641cf5a8e4cc1b90adb011759bd7b953aba4`,
luminosity 352, led_state ON, registrado em
`2026-10-30T01:25:35.426975-03:00`, como resultado do ensaio solicitado com a tela
aberta e sem interação. SQL e API confirmaram o mesmo ID/payload. A evidência
visual é texto fornecido pelo operador, não captura direta deste agente.
Esse retorno foi aceito no contexto do ensaio; não é evidência de sensor físico.

O ensaio anterior com 351 falhou na interface por indisponibilidade do transporte:
frontend e túnel não tinham listeners. Logs do proxy mostraram tentativas a cada
dez segundos. Após restabelecimento: frontend 200 e health sem credenciais 401
tanto no túnel quanto no proxy. Não se atribuiu a falha à autenticação nem se
declarou polling válido apenas por encontrar registros no banco.

Linha de base antes da autenticação: 15 telemetry, 7 window, total 22 projeções.
Nenhuma publicação MQTT foi feita pelo agente a partir do gateway. P08/P09,
modelos, defesas, firewall, redes e configurações MQTT foram preservados.

## Composição real e compatibilidade

O serviço `harpisense-p11` usa `/opt/harpisense/staging/p11-postgresql/app.py`,
`PostgresStore`, fábrica P11 de `integration-v2` e complemento
`harpia_deterministic`. O consumidor MQTT grava diretamente no Store/banco e
não depende de sessão administrativa. Não foi substituído por `backend/delivery`.

Python real 3.14, FastAPI 0.143.3, psycopg 3.3.6 e PostgreSQL 18.6.
A candidata originalmente testada com FastAPI 0.115 passou por requisições ASGI
na própria VM, em pasta temporária, usando os fontes reais e identidade/Store
de teste. Sem HTTPX instalado ou banco operacional na fixture, os três testes
confirmaram rotas administrativas sem sessão/Basic/token inválido recusadas,
Bearer válido, autenticação de sessão, validação privada, origem recusada e
ingestão técnica ainda exigindo Basic e token próprios. Isso é compatibilidade
de runtime, não prova de login de uma conta real na VM.

Hashes dos bytes anteriores à integração:

| Arquivo | SHA-256 |
| --- | --- |
| app.py | `52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2` |
| postgres_store.py | `cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c` |
| mqtt_consumer.py | `188490130d89a3eebe6370bd23e645cd5089ef18f80364624b3f3e0ce0da8f30` |
| fábrica P11 | `8cb67932cc2f7ef22ed357b0c94f7a8cb416cde164db60866dd6df5cf7fb8698` |

O manifesto da release também confere os três arquivos do complemento HarpIA.
Diferença em qualquer arquivo bloqueia ativação e exige comparação explícita.

## Login, sessão e transporte

O frontend envia usuário/senha próprios somente ao POST `/api/v1/admin-auth/login`
e confirma a sessão no GET `/session`. Não guarda senha, Authorization Basic,
token em URL, cookie, armazenamento do navegador, bundle ou variável pública.
O campo senha é limpo ao tentar login, inclusive em erro. Token opaco Bearer
permanece apenas na memória; senha scrypt e hash SHA-256 do token ficam nas
tabelas separadas de autenticação do PostgreSQL. Recarregar exige novo login.

O limite absoluto é oito horas e a inatividade é trinta minutos conforme o
relógio do PostgreSQL; requisições autenticadas atualizam atividade, mas não o
limite absoluto. Há throttle persistido e global. O frontend encerra no prazo
absoluto e ao receber sessão expirada, revogada, inválida ou autorização recusada.
Não tenta Basic, perfil legado ou novo login automaticamente.

Logout descarta a sessão local imediatamente e solicita revogação na API.
Cancelamento de consultas/navegação não cancela essa requisição de revogação.
Se o servidor não confirmar, a tela informa a limitação em vez de afirmar logout
remoto concluído. Respostas tardias não reabrem sessão ou consultas antigas.

Windows: navegador/proxy no loopback `127.0.0.1:4174`; túnel autorizado em
`127.0.0.1:18000`; API no loopback da VM `127.0.0.1:8000`. O trecho pela LAN é
protegido por SSH. Não se publica HTTP de senha/token na LAN. A release permite
origens exatas `http://127.0.0.1:4174` e `http://127.0.0.1:5174`; não cria CORS,
novo listener de rede, TLS, regra de firewall ou VPN. Publicação externa exige
HTTPS e revisão específica, fora desta implantação local.

O proxy libera explicitamente os endpoints de sessão e os recursos já integrados,
recusa Basic e ingestão técnica pelo navegador, rejeita parâmetros arbitrários,
remove cookies e não injeta segredos. Respostas têm no-store; a página aplica CSP,
no-referrer e nosniff. Há tratamento explícito de transporte indisponível.
O Basic técnico fica apenas na rota exata de ingestão do P11, com token de serviço
adicional. Não há rota administrativa alternativa com autenticação técnica.

Credenciais de MQTT, PostgreSQL e ingestão continuam no host. Provisionamento
recusa reutilização das credenciais técnicas conhecidas, incluindo senha PostgreSQL
e `.mqtt_password`; segredos de serviços externos não presentes no host não podem
ser comparados automaticamente. A conta precisa de senha própria e exclusiva.

MFA e recuperação por e-mail **pendentes**. Exemplos na prévia permanecem
explicitamente visuais e não correspondem a capacidades instaladas.

## Preparação, provisionamento e ativação

Release protegida:
`/opt/harpisense/staging/p11-postgresql/.admin-auth-releases/admin-session-20261030-r1`.
Manifesto `release.json` registra os hashes dos módulos e a base candidata.
Backups protegidos ficam em `.admin-auth-backups/admin-session-20261030-r1`.
Diretórios 0700, arquivos 0600/sem permissões para grupo/outros. Não copiar
`.env`, dumps, senhas ou hashes de conta para o repositório.

`backend/admin_auth_ops/manage.py` verifica hashes, cria backup custom com snapshot
PostgreSQL consistente, prepara migração aditiva, faz provisionamento interativo,
gera bootstrap e fornece verificação segura. Nenhum comando reinicia serviços
automaticamente. O provisionamento não aceita senha por argumento/ambiente nem
stdin sem TTY. Os recibos não contêm senha, DSN ou token.

O backup precisa ser restaurado em PostgreSQL descartável, sem acesso à VM, antes
da migração. Conferem-se SHA-256 do dump e digest ordenado de todas as projeções
com representação UTC, para que fusos diferentes não gerem falsas divergências.
O recibo `restore-verified.json` é exigido antes de aplicar o SQL. A migração é
transacional e aditiva, versão 1; não altera `projections` ou configurações técnicas.

No terminal SSH do operador, como `harpiserver`, após preparação confirmada:

```sh
cd /opt/harpisense/staging/p11-postgresql/.admin-auth-releases/admin-session-20261030-r1
/opt/harpisense/venv/bin/python -m admin_auth_ops.manage provision
```

Define usuário e senha oculta duas vezes. Não enviar a senha ao chat.
Depois do provisionamento, a ativação já autorizada confere novamente os arquivos:

```sh
/opt/harpisense/venv/bin/python -m admin_auth_ops.manage activate
sudo systemctl restart harpisense-p11.service
```

O sudo reinicia **somente a API P11**, para carregar o bootstrap de sessão. Não
reinicia MQTT ou PostgreSQL nem altera firewall/rede. Exige senha sudo local;
não passá-la ao agente. Ativar requer exatamente uma conta já provisionada.

Verificação real após o reinício, no mesmo terminal:

```sh
/opt/harpisense/venv/bin/python -m admin_auth_ops.manage verify
```

Solicita conta própria com senha oculta. Verifica acesso anônimo e Basic técnico
recusados, login válido/inválido, sessão inválida, health, telemetria, logout,
reuso da sessão revogada e expiração absoluta/inatividade. Expira somente duas
sessões criadas pelo próprio verificador e revoga todas as suas sessões ao final;
não modifica sessões de outros logins. Salva recibo sanitizado no backup protegido.
A atualização periódica e o uso da conta na interface exigem também observação
do navegador real; não são inferidos desse recibo HTTP.

O artefato frontend candidato é compilado em `frontend/local-evidence/auth-candidate-dist`,
fora do `dist` servido, com manifesto de hashes e commit de origem. O script
`frontend/scripts/activate-admin-preview.ps1` exige primeiro HTTP 401 Bearer no
endpoint de sessão e no health do backend, preserva o dist anterior, confere o
processo dono da porta 4174 e reinicia somente o preview desta worktree. Sem essa
confirmação ele não publica o candidato. Nenhuma credencial é injetada no proxy.

## Recuperação

Nunca restaurar o dump sobre o banco operacional para desfazer esta migração,
pois isso perderia telemetria posterior. Preservar as tabelas novas e investigar.
O retorno controlado mantém acesso administrativo fechado e a ingestão técnica:

```sh
cd /opt/harpisense/staging/p11-postgresql/.admin-auth-releases/admin-session-20261030-r1
/opt/harpisense/venv/bin/python -m admin_auth_ops.manage recover
sudo systemctl restart harpisense-p11.service
```

O utilitário recusa recuperação se o bootstrap mudou desde a ativação.
O bootstrap anterior cru fica preservado para análise; não deve ser recolocado
como fallback, pois reativaria o Basic administrativo. O artefato frontend anterior
também é preservado; após ativação ele não autentica pelo Basic recusado no backend.

## Evidências e estado

- Local: 21 testes da candidata em PostgreSQL 18.6 isolado, sem porta externa.
- Local: fluxo do operador passou no banco restaurado descartável, incluindo
  migração, provisionamento, ativação, verificações HTTP via ASGI, expirações e
  recuperação com acesso administrativo fechado; projeções preservadas.
- VM: três testes de compatibilidade ASGI com runtime/fontes reais e fixtures.
- Frontend: testes de cliente/proxy, sessão, polling, logout e prévia; resultados
  finais e estado de ativação são registrados no recibo da rodada.

Resultados finais do frontend nesta preparação: 35 testes Node aprovados,
typecheck/build aprovados e 37 testes Chromium aprovados. Um teste opt-in da
composição local antiga não foi executado; não é evidência contra a VM.

Backup final: SHA-256
`b671c30fb9368ed843bdf11834a93effd8fa7c0001c56920f0c002ff8651ebed`.
Restauração local integral com `pg_restore --exit-on-error` aprovada; total de 22
projeções e digest UTC `1daf4e5b481d6f666b887a531454bc55` idênticos à origem.
O primeiro backup foi preservado em diretório com sufixo `-initial`.
Migração versão 1 aplicada na VM, sem reinício: projeções preservadas.

Preparação não equivale a ativação. Conta real, reinício sudo, publicação do
frontend e validações reais dependentes são registrados separadamente abaixo.

| Etapa | Último estado registrado |
| --- | --- |
| Código e testes locais | Integração concluída; artefato candidato separado do servido |
| Compatibilidade na VM | ASGI e scrypt verificados no runtime real |
| Backup e restauração isolada | Aprovados; recibo conferido antes da migração |
| Migração na VM | Versão 1 aplicada em `2026-10-30T05:43:46.795815+00:00` |
| Projeções após migração | 22, digest UTC preservado |
| Conta própria | Última leitura: zero contas; aguardando provisionamento interativo do operador |
| Bootstrap ativo | Original, hash `52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2` |
| Serviços P11 e MQTT | Ativos na conferência após migração; não reiniciados |
| Ativação de sessão e publicação frontend | Pendentes de conta própria e reinício sudo |
| Login real, logout/revogação e expiração na VM | Pendentes; não confundir com fixtures ASGI ou PostgreSQL local |
| Conta/sessão e polling na interface real | Pendentes após ativação; prévia preservada |
