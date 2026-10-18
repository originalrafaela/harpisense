# Integração P11/PostgreSQL — preparação e validação real assistida

## Isolamento da entrega

Branch `integration/frontend-p11`, worktree `D:\Projetos\tcc - harpisense\harpisense-worktrees\integration-p11`, base `1d7ed4de110eedc5c68f4acd7d10427783b4c6a5`. Essa base inclui o frontend publicado e a integração anterior `a7cb501`; a main `9d58e69` não é a base adequada. Não houve merge em main ou push. A worktree `frontend-v2` e a branch `frontend/harpisense-v2` permanecem preservadas.

## Código e referências comparados

Fontes locais em `referencias/versão_v2/`, somente leitura:

| Fonte | Formato/semântica | Compatibilidade e limite |
|---|---|---|
| P11 `backend11/service.py` | health protegido por Basic; listas de `{id,revision,source,data,created_at}`; limit/offset | Compatível com o adaptador; login passa a verificar o health protegido antes de telemetria |
| P13 `componentes/p11/backend11/service.py` | Mesma implementação P11 | SHA-256 idêntico ao P11: `8cb67932cc2f7ef22ed357b0c94f7a8cb416cde164db60866dd6df5cf7fb8698`; não representa adaptação PostgreSQL nova |
| P11 `migrations/002_projection_postgresql.sql` | Migração candidata com `hs11_projections`, `entity_id`, `payload` | Não aplicada; não é o armazenamento `projections`/`data` descrito no relatório. Não executar como correção automática |
| Relatório `HarpiSense_V2_Relatorio_Fluxo_Poste2_MQTT_PostgreSQL_API.pdf`, 18/10 | PostgreSQL 18; tabela projections/JSONB; API Ubuntu em 127.0.0.1:8000; projeção de poste2 | Fonte mais recente de evidência externa. Fixture de contrato segue seu envelope, sem afirmar nova coleta |
| Base Git `backend/app/` | API v1 anterior e telemetria com measurements | Perfil legacy continua separado; não substitui o P11 do HarpiServer |

No relatório, o registro tem `data.device_id=poste2`, `data.temperatura=28.4`, `data.tipo=teste_systemd`, `revision=1`, `source=trusted-service`, `created_at=2026-10-18T01:14:12.498058-03:00`. Não contém observed_at, unidade da temperatura, luminosidade ou LED. O frontend preserva esse significado: mostra a temperatura provisória sem atribuir unidade, o ID e o horário da projeção, mantendo observação/luminosidade/LED não informados. created_at não se transforma em horário da medição.

Os arquivos atuais `/opt/harpisense/staging/p11-postgresql/app.py`, `postgres_store.py` e `mqtt_consumer.py` não foram encontrados como fontes locais. Os nomes/caminhos constam do relatório. Não foram recriados. Nenhum pacote antigo adicional é necessário para o adaptador atual; antes de qualquer necessidade nova, solicitar especificamente o componente existente.

## Matriz do primeiro fluxo

| Etapa | Endpoint real esperado | Frontend nesta branch | Evidência desta sessão |
|---|---|---|---|
| Login P11 | GET `/api/v1/p11/health`, Basic | Verifica status e objeto de saúde com api string; 401/403/503/rede tratados; não cria sessão fictícia | Testes isolados, não credencial de VM |
| Saúde | GET `/api/v1/p11/health` | Mapa original; API/store não atestam broker/PostgreSQL/modelos | Contrato e transporte local testados |
| Telemetria Poste 2 | GET `/api/v1/p11/telemetry?limit=50&offset=0` | Envelope preservado; IDs não são renomeados; lista vazia e inválida distintas | Fixture baseada no relatório; VM não consultada |
| Dashboard/histórico | Mesma lista de telemetria | Mostra ID, revisão, origem, timestamp e payload provisório; detalhes permitem conferir correspondência | Chromium com resposta isolada |
| Outros módulos | Endpoints P11 de referência | Telas preservadas, mas default `VITE_P11_RESOURCES=telemetry` impede consultas não confirmadas; indica não integrado | Nenhuma ausência de implementação inferida |
| Mutações/controle/autonomia | Nenhum endpoint fornecido | Desabilitados em operação; prévia visual permanece separada | Nenhum POST/PUT/DELETE é encaminhado |

## Aplicação manual do acesso restrito

Não foi aberto túnel nem alterado bind, firewall, CORS, serviço, banco ou credencial. O operador precisa de SSH já autorizado ao Ubuntu, com alias e fingerprint previamente verificados. O acesso proposto é:

```text
Browser Windows http://127.0.0.1:5174
  → /p11-api/api/v1/p11/{health,telemetry} (mesma origem)
  → proxy local Vite 127.0.0.1:18000
  → túnel SSH cifrado
  → API existente 127.0.0.1:8000 no Ubuntu
```

Em um terminal PowerShell local, após configurar/verificar o alias SSH pelos meios habituais:

```powershell
cd frontend
.\scripts\open-p11-tunnel.ps1 -SshAlias ALIAS_SSH_JA_CONFIGURADO
```

Equivalente: `ssh -N -T -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes -L 127.0.0.1:18000:127.0.0.1:8000 ALIAS_SSH_JA_CONFIGURADO`. O script não configura SSH nem aceita fingerprints automaticamente, não inclui senha em argumentos e recusa uma porta local ocupada. Credenciais/chaves são tratadas pelo SSH no terminal; não devem ser fornecidas pelo chat. Ctrl+C encerra o túnel. Se usar outra porta local, ajustar HARPI_API_TUNNEL_TARGET na configuração local.

Em outro terminal, dentro de frontend desta worktree:

```powershell
npm.cmd ci
# Criar somente se ainda não existir; preservar qualquer configuração existente.
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm.cmd run dev
```

Abrir `http://127.0.0.1:5174`. No login, a URL deve ser `/p11-api` e perfil P11; preferências previamente salvas no navegador têm precedência e podem ser corrigidas em “Conexão da API”. Usar as credenciais efetivamente configuradas no backend, sem presumir admin/admin. Senha apenas em memória; logout remove credenciais e cancela consultas.

O Vite de integração usa uma porta distinta do frontend original (5174), bind exclusivo de loopback, CORS desabilitado e alvo de proxy restrito a HTTP/127.0.0.1. A guarda aceita somente GET dos dois endpoints, limit/offset e mesma origem; não encaminha mutações, outros recursos nem cookies de resposta. Authorization é encaminhado em memória, sem logs. HARPI_API_TUNNEL_TARGET é configuração do processo Vite, não variável VITE nem segredo no bundle.

`npm.cmd run build` gera dist; `npm.cmd run preview` usa `http://127.0.0.1:4174` com a mesma configuração local de proxy. Um servidor estático de dist sozinho não contém esse transporte. Esta é uma solução restrita de laboratório, sem publicação de site ou configuração de produção. Não usar --host 0.0.0.0 ou liberar a API da VM para aplicar este procedimento.

Para confirmação manual no túnel sem imprimir cabeçalho/senha:

```powershell
$adminUser = Read-Host 'Usuário administrativo existente'
curl.exe --silent --show-error --user $adminUser http://127.0.0.1:18000/api/v1/p11/health
curl.exe --silent --show-error --user $adminUser 'http://127.0.0.1:18000/api/v1/p11/telemetry?limit=50&offset=0'
```

O curl solicita a senha no terminal. Não usar -v/trace nem colocar senha na URL/linha de comando. Uma consulta sem autenticação deve ser 401; uma credencial incorreta deve ser rejeitada. Se health for público na adaptação atual, parar a homologação do login e comparar app.py antes de mudar o fluxo: não trocar silenciosamente de mecanismo.

## Critério de aceite real e bloqueio

**Situação inicial, superada parcialmente pela validação assistida abaixo.** Na preparação não havia SSH/túnel confirmado nem fontes atuais da VM; os testes dessa fase eram isolados. Consultar o registro de 18/10 abaixo para as evidências reais e os limites restantes.

Para aceitar, publicar uma nova telemetria do Poste 2 pelo mecanismo já implantado (fora do frontend), registrar ID e evidência de persistência PostgreSQL/journal, consultar P11 autenticado e conferir no dashboard **o mesmo ID, source, revisão, created_at e payload**. Guardar horário e evidências sanitizadas em `frontend/local-evidence/` (ignorado), sem Authorization/senhas. Relatório antigo e fixtures não substituem essa execução.

Pendências identificadas na preparação (estado histórico):

1. Alias SSH confirmado ou túnel manual já estabelecido; autenticação digitada pelo operador, sem transmitir segredos.
2. Código sanitizado atual de app.py, postgres_store.py e mqtt_consumer.py, ou ao menos OpenAPI e saídas autenticadas de health/telemetry para confirmar a adaptação.
3. Nova publicação do Poste 2 + confirmação de persistência + registro correspondente visível no navegador. Sem isso, o aceite real permanece pendente.

## Validação real assistida — 18/10/2026

Comandos executados pelo operador em seus terminais, com resultados fornecidos na conversa; este agente não executou SSH nem recebeu senhas. HarpiServer: usuário SSH `harpiserver`, Tailscale `100.66.89.7`, hostname `gateway`, interface LAN `192.168.155.144`. Poste 2: `harpisense@192.168.155.142`, hostname `poste2`.

### Transporte, serviços e autenticação

- `systemctl is-active postgresql harpisense-mqtt harpisense-p11`: três respostas `active`.
- `pg_isready -h 127.0.0.1 -p 5432`: accepting connections.
- `ss`: API exclusivamente em `127.0.0.1:8000`.
- Health sem autenticação: HTTP 401. Com credencial existente digitada localmente: HTTP 200, `{"api":"available","projection_store":"available","rf":"unknown","if":"unknown","broker":"unknown","executor":"unknown","bitnet":"not_verified"}`.
- Operador abriu túnel SSH Windows com `-L 127.0.0.1:18000:127.0.0.1:8000`, `ExitOnForwardFailure=yes`, `GatewayPorts=no`, `StrictHostKeyChecking=yes`, destino `harpiserver@100.66.89.7`. Vite/frontend/proxy acessados em `http://127.0.0.1:5174`, perfil P11, `/p11-api`.
- Não houve alteração de firewall, bind da API ou credenciais. Nenhum ataque foi executado. Credenciais não foram incluídas neste relatório.

### Cópias atuais e compatibilidade

`app.py` (465 bytes), `postgres_store.py` (4551 bytes) e `mqtt_consumer.py` (1942 bytes) copiados por SCP para `frontend/local-evidence/vm-reference/`, ignorado pelo Git. Originais preservados. Inspeção de possíveis credenciais precedeu a leitura dos trechos: configuração de autenticação MQTT identificada na linha 55 do consumidor e ocultada da saída. Não versionar cópias brutas; varredura textual não é garantia absoluta de ausência de segredos.

`app.py` importa `create_app` do P13 instalado e injeta `PostgresStore`; a URL do banco vem de variável de ambiente. A cópia do store confirma tabela `projections`, campos `kind,id,revision,source,data,created_at`, revisão inicial 1, idempotência e imutabilidade por revisão. A lista retorna última revisão por ID, ordenada por registro, com limit/offset. Envelope compatível com o adaptador existente; health e lista reais confirmam os endpoints usados, sem presumir igualdade de todo o pacote remoto com a referência local.

O consumidor assina `harpisense/poste2/telemetry`, exige objeto JSON com `device_id=poste2`, atribui `source=trusted-service`, `revision=1` e ID `poste2-` + SHA-256 dos bytes do tópico, byte nulo e bytes do payload. Republicação idêntica não gera novo registro. Não foi necessário alterar código após o diagnóstico.

### Registro novo e correspondência

Payload sintético de teste conduzido pelo operador pelo caminho MQTT real; não representa medição física. O comando/publicador exato e sua localização não foram capturados. Não afirmar publicação física originada no Poste 2 apenas pelo campo device_id.

```json
{
  "id": "poste2-7092868eaf328f389005c1e6060e7a62a4d415ec927b0cb10b4e543cd12ca29d",
  "revision": 1,
  "source": "trusted-service",
  "data": {
    "tipo": "teste_conexao_dashboard",
    "origem": "teste_sintetico",
    "device_id": "poste2"
  },
  "created_at": "2026-10-18T15:52:33.594436-03:00"
}
```

Consulta PostgreSQL em transação `BEGIN READ ONLY`, banco `harpisense`, tabela `projections`, filtro `kind='telemetry'` e ID acima: uma linha, com todos os campos coincidentes com o objeto retornado pelo GET autenticado `/api/v1/p11/telemetry?limit=50&offset=0` via túnel. PostgreSQL mostrou `2026-10-18 15:52:33.594436-03`; API mostrou o mesmo instante em ISO 8601. `source=trusted-service` identifica a origem da projeção pelo consumidor; `data.origem=teste_sintetico` descreve o teste e não deve ser confundido com source.

Operador transcreveu do dashboard o mesmo ID, device_id, created_at e tipo `teste_conexao_dashboard`; observação, temperatura e medições ausentes apareceram como não informadas, coerentes com o payload. Conferência explícita de source, revisão e payload completo nos detalhes do dashboard ainda aguardada. Não houve captura de tela real pelo agente. A captura `p11-contract-dashboard-isolated.png` continua sendo exclusivamente de fixture.

O registro anterior de 14:26 não era erro de fuso: o servidor marcava 15:50 e a API ainda retornava a projeção antiga. Ping não publica MQTT. Journal sem entradas nos 15 minutos consultados não comprovava falha de serviço. Após a publicação, o registro de 15:52 foi observado nas três camadas.

### Limite do aceite

Comprovados por evidências do operador: autenticação existente, serviços ativos, transporte local, persistência e leitura API do registro novo, além de identidade/horário/tipo exibidos na tela. Ainda faltam confirmação dos detalhes completos da tela e comprovação do comando de publicação executado no Poste 2 para declarar integralmente todos os critérios solicitados. Modelos, controles e sensores físicos não foram homologados. Testes automatizados isolados não substituem essas confirmações.

Verificação local desta rodada: `npm.cmd test` — 17 testes aprovados; `npm.cmd run build` — tipos e build aprovados; `npx.cmd playwright test tests/p11-flow.spec.ts` — 3 testes Chromium isolados aprovados. Suíte completa Chromium não repetida nesta rodada. Sem merge ou push.
