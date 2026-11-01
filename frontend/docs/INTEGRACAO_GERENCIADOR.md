# Integração do assistente com o gerenciador

Esta candidata usa a sessão administrativa já implementada. O cliente central envia `Authorization: Bearer` somente em memória, aplica timeout/cancelamento e `Cache-Control: no-store`; senha e token não são salvos no navegador. Não há login técnico próprio do assistente.

Entrega frontend: branch `feat/frontend-config-manager`, worktree `D:\Projetos\tcc - harpisense\harpisense-worktrees\frontend-config-manager`, derivada do commit de integração confirmado `4adf234aa75ac3bb129f02bdddabe73b62956549` (`feat/frontend-backend-autonomia`). Para integrar, o Arquiteto revisa e cherry-picka o commit frontend desta branch na sua candidata; nenhum merge com main é necessário. O bootstrap do backend precisa continuar instalando o gerenciador depois da sessão administrativa existente, usando a mesma conexão/configuração de instalação/capabilities documentadas no contrato; migrations são responsabilidade do instalador e não do navegador.

## Rotas confirmadas

Prefixo `/api/v1/config`. Todas as rotas usam a mesma sessão administrativa e instalação fixa fornecida pelo instalador.

O transporte de desenvolvimento `/p11-api` também foi atualizado com allowlist estrita destes oito pares método/caminho, preservando Bearer, no-store, loopback e rejeição de Basic. A única query adicional permitida ao gerenciador é `after` + `limit` em `/history`; os recursos fora do contrato continuam bloqueados no proxy.

| Tela/ação | Endpoint | Uso e estado |
|---|---|---|
| Abrir Configurações | `GET /setup` | Retoma `version`, `document`, `state`, `pending` e `updated_at`; `version=0` + `document=null` identifica primeiro acesso no estado persistido. |
| Carregar resumo | `GET /current` | Compara revisão desejada/proposta com revisão efetiva e `operational`. |
| Carregar perfis | `GET /catalog` | Perfil ESP32/WROOM-32 é exibido conforme catálogo, `available=false` significa preparatório e não aplicado. Nenhum outro firmware é criado. |
| Carregar auditoria | `GET /history?after=0&limit=100` | Mostra eventos retornados; não os trata como prova de aplicação. |
| Avançar/retomar | `PUT /setup` | Snapshot parcial com `expected_version` e nova `idempotency_key`; repetição após falha de transporte mantém a mesma chave/body em memória. Conflito conserva o formulário e pede nova leitura. |
| Criar proposta | `POST /proposals` | Envelope `config.proposal` v1 com `expected_revision` da configuração, id UUID, idempotência e documento `config.document` v1. |
| Consultar operação | `GET /proposals/{operation_id}` | Atualiza o estado da proposta criada. |
| Validar proposta | `POST /proposals/{operation_id}/validate` | Envia `expected_revision` da própria proposta. Erros 422 são associados aos campos sem ecoar valores. |
| Atualizar resumo | `GET /current` + `GET /history` | Refaz leitura depois de salvar/criar/validar. |

O rascunho do assistente suporta as etapas autorizadas pelo schema de progresso: `installation`, `deployment`, `devices`, `mqtt`, `capture`, `backup`, `review`. A tela não envia conta de administrador, DSN PostgreSQL, senha, token, comando, segredo MQTT/AWS ou operação de bootstrap. Referências `secret://…` são referências opacas, não valores secretos. Os parâmetros de captura usam identificadores informados pelo operador e são verificados pelas capabilities do servidor.

Propostas são snapshots imutáveis: editar uma proposta validada salva um novo rascunho e cria outra operação por `POST /proposals` com a revisão corrente; não sobrescreve UUID ou revisão anterior. `deployment_profile`, `devices` e `backup` pertencem ao progresso parcial e não são acrescentados ao documento `config.document`, cujo schema oficial aceita somente `parameters`.

## Estado e limites

- Rascunho persistido não é proposta de configuração nem significa que os campos estão completos.
- Proposta salva e proposta validada são estados distintos.
- `/current` é a fonte para revisões desejada e efetiva. Configuração efetiva ausente aparece explicitamente como ausente.
- O backend da base confirma `operational=false` e catálogo `applicators=[]`; o botão de aplicação permanece indisponível. Não existe `/apply` nesta integração.
- Selecionar ESP32-WROOM-32 prepara somente o inventário do Poste 1. `selection_flashes_board=false`; não grava placa. Poste 2 é Ubuntu com telemetria simulada e não aparece como perfil de firmware.
- A identidade da instalação, usuário administrativo, credenciais de runtime, migrations e capabilities são do instalador. O assistente não pode autorizar nem configurar aplicação operacional.
- Primeiro acesso depende do `GET /setup` persistido. As outras páginas e a telemetria continuam navegáveis em instalações existentes.

## Execução

Na worktree candidata, em `frontend/`:

```powershell
npm.cmd ci
npm.cmd run dev
```

Configurar a URL acessível pelo navegador pela tela de acesso. Para a API candidata local, usar o endereço/proxy de loopback aprovado pelo responsável do ambiente; não usar `localhost` supondo que alcance o Ubuntu remoto. A composição local não está exposta automaticamente ao navegador e esta entrega não altera CORS, túnel, serviços ou firewall.

Testes frontend:

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npx.cmd playwright test tests/config-manager.spec.ts
```

Resultado nesta candidata: `typecheck`, build e 38 testes unitários aprovados; Playwright 43 aprovados e 1 skip opcional da composição local P11. Os testes de retomada, validação inválida, conflito, expiração e API indisponível do navegador usam respostas HTTP isoladas e não são integração real do browser com o backend.

A suíte candidata `python -m unittest discover -s backend/config_manager_tests -v` executou contra o container isolado `harpisense-config-api-db`, banco `config_fixture`, usando o `TestClient` FastAPI com PostgreSQL real descartável: 29 testes aprovados, sem skips. Cobriu as rotas autenticadas, persistência, retomada após recriar Store, proposta, validação, conflito, idempotência, auditoria, sessão e P11 preservado. A DSN foi obtida localmente do container, sem imprimir credenciais. Nenhum banco operacional foi usado. Isso valida a composição backend candidata, mas não substitui uma execução do frontend em navegador apontando para um servidor HTTP candidato.

## Próximas pendências

1. Iniciar a candidata HTTP local com bootstrap aprovado e conectar o browser à URL/proxy permitido; a suíte atual testou a API pelo `TestClient`, não por Vite/browser.
2. Confirmar no ambiente em que o frontend será aberto o proxy/URL permitido, HTTPS ou loopback e CORS de origem restrita.
3. Confirmar com o Arquiteto as `Capabilities` reais da instalação para referências MQTT, sensor, rede, modelos e credenciais externas antes de esperar uma validação aprovada.
4. Nenhuma aplicação de configuração pode ser habilitada até existir contrato e aplicador/verificador aprovado; não faz parte deste frontend.
