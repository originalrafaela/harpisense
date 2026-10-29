> Entrega atual de frontend/backend e autonomia: [relatório, matriz e execução local](../docs/ENTREGA_FRONTEND_BACKEND_AUTONOMIA.md).
> A composição local nova fica em `backend/delivery`; a documentação abaixo descreve a base anterior.

# HarpiSense V2 — frontend

Interface de consulta em português com login e 14 telas operacionais, demonstração explícita e integração progressiva. React 18, TypeScript e Vite seguem a stack do frontend legado preservado no P11; nenhum backend foi criado. Apenas React/React DOM entram no bundle. Playwright é dependência de desenvolvimento.

Esta worktree usa a branch **integration/harpia-ui**, derivada de `integration/frontend-p11` (`280bab4`). A entrega original do frontend e sua worktree foram preservadas. Preparação HarpIA, resultados e pendências em [Integração visual HarpIA](docs/HARPIA_INTEGRACAO_VISUAL.md). Geração permanece desabilitada; consulta somente projeções registradas, com identificação de revisão, origem e atualidade. A preparação anterior de acesso SSH está em [Integração P11](docs/INTEGRACAO_P11_REAL.md). A VM não foi acessada nesta rodada.

## Executar

Requer Node 24 (testes usam remoção nativa de tipos) e npm. Dentro de `frontend/` da worktree:

```powershell
npm.cmd ci
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm.cmd run dev
```

Abra `http://127.0.0.1:5174`. Para operação P11, abra manualmente o túnel SSH conforme o documento de integração. Sem túnel, o login deve falhar; a interface não substitui a API por exemplos. A entrada **Explorar demonstração visual** não exige API e mantém o aviso “Prévia visual — dados de demonstração, sem ações reais.” Não é o modo operacional SIMULATION. Consulte [instruções, telas e pendências da prévia](docs/PREVIA_VISUAL.md).

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npx.cmd playwright install chromium
npx.cmd playwright test
npm.cmd run preview
```

Não há lint configurado. O build também executa a checagem de tipos. `dist/` é o artefato de empacotamento posterior, ignorado no Git. Nenhum Docker, publicação ou alteração de VM faz parte desta entrega.

## Conexão e autenticação

Por padrão, `VITE_API_URL=/p11-api` usa o transporte local de leitura para `HARPI_API_TUNNEL_TARGET=http://127.0.0.1:18000`, que deve apontar para um túnel SSH autorizado. O proxy só aceita GET health/telemetry do P11; não publica API nem altera CORS da VM. `VITE_P11_RESOURCES=telemetry` mantém módulos não confirmados identificados como não integrados, sem inferir que não existem. O valor `all` é usado nas fixtures da suíte visual de regressão; não amplia a guarda do proxy local.

Também é aceita uma origem/base HTTP(S) absoluta já autorizada e compatível, com `VITE_API_PROFILE=p11` ou `legacy`. O transporte `/p11-api` atende apenas P11. Alternativamente, abra **Conexão da API** no login. URL e perfil locais prevalecem sobre o ambiente. Configurações só mudam a interface; aplicar encerra a sessão. Não inclua senha, token ou credenciais na URL ou em variáveis Vite.

`p11` usa GET `/api/v1/p11/health` protegido para validar HTTP Basic, antes de consultar telemetria; não cria endpoint de login. `legacy` continua usando GET `/api/v1/telemetry`, pois seu health é público. Não há tentativa automática de outro perfil. Usuário e senha começam vazios. A senha e o cabeçalho Basic permanecem somente em memória e são descartados ao sair; navegação cancela consultas sem encerrar a autenticação. Nenhuma mutação operacional é enviada. Não existe aprovação otimista ou repetição de comandos.

Para **admin/admin no laboratório isolado**, o responsável pelo backend deverá configurar o mecanismo efetivamente implantado. Variáveis encontradas:

| Implementação inspecionada | Usuário | Senha |
|---|---|---|
| P11 local `backend11/service.py` | `HARPISENSE_ADMIN_USER` | `HARPISENSE_ADMIN_PASSWORD` |
| Base Git `backend/app/core/config.py` | `HARPI_ADMIN_USERNAME` | `HARPI_ADMIN_PASSWORD` |

Configurar ambos como `admin` somente no laboratório isolado. Nenhuma credencial de VM foi alterada ou validada nesta entrega. Confirmar os nomes em `/opt/harpisense/staging/p11-postgresql/app.py` antes de ajustar o serviço: esse código atual não foi disponibilizado como arquivo-fonte inspecionável. Trocar a senha antes de disponibilizar fora do laboratório; usar HTTPS ou túnel equivalente.

O relatório de 18/10 informa API no loopback do Ubuntu (`127.0.0.1:8000`). `localhost` no Windows não alcança esse serviço. O Arquiteto deve definir proxy/túnel autorizado e HTTPS, preferencialmente com mesma origem do frontend; se usar origens diferentes, permitir apenas a origem exata e o cabeçalho Authorization. Não foi alterado bind, porta, CORS, firewall ou encaminhamento. Um proxy deve preservar respostas 401/403 e não registrar Authorization.

## Estrutura

| Local | Responsabilidade |
|---|---|
| `src/main.tsx` | sessão, navegação, carregamento e coordenação das consultas |
| `src/api.ts` | cliente HTTP, timeout, cancelamento, autenticação e adaptadores |
| `src/telemetry.tsx` | identidade e payload da projeção P11/PostgreSQL sem inferir campos ausentes |
| `src/resources.ts` | escopo explícito dos recursos confirmados para a conexão |
| `vite.config.ts`, `scripts/p11-proxy.mjs` | transporte restrito até o túnel local, sem lógica de backend |
| `scripts/open-p11-tunnel.ps1` | aplicação manual do túnel SSH, sem alterar VM |
| `src/components.tsx` | painéis, tabelas, filtros locais e detalhes |
| `src/pages.tsx` | conteúdo específico de cada tela |
| `src/demo.ts` | exemplos isolados; nunca usados como fallback de rede |
| `src/dashboard.tsx` | HarpIA na página inicial e controles independentes de autonomia, modo e execução |
| `src/catalog.json` | exportação gerada do catálogo oficial P03 |
| `docs/harpisense_catalog.source.py` | cópia intacta da fonte oficial consultada |
| `scripts/catalog.mjs` | gera catálogo; falha se a estrutura esperada mudar |
| `public/assets/` | assets copiados da proposta visual local |
| `tests/` | testes isolados de contrato/HTTP e testes Chromium |

Para atualizar o catálogo, substituir a cópia da fonte por uma nova entrega aprovada e executar `npm.cmd run catalog`. Não editar as linhas geradas nem manter um catálogo alternativo. O SHA-256 da fonte acompanha o JSON.

## Limites e entrega

Consulte [matriz e pendências](docs/INTEGRACAO.md), [testes](docs/VERIFICACAO.md), [ajuste do dashboard](docs/AJUSTE_DASHBOARD.md) e [entrega ao Arquiteto](docs/ENTREGA.md). Interface preparada e testada com respostas isoladas não significa integração com a VM. Listas são páginas de até 50 registros, com paginação P11; filtros se aplicam à página atual. O perfil legacy tem limite e não anuncia paginação por offset que o servidor não implementa.
