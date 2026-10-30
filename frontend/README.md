> Conta administrativa e sessão (30/10): [integração, estado e procedimento de implantação](../docs/INTEGRACAO_CONTA_ADMINISTRATIVA_20261030.md). Essa integração substitui o login Basic descrito nos registros históricos.
> Entrega de frontend/backend e autonomia: [relatório, matriz e execução local](../docs/ENTREGA_FRONTEND_BACKEND_AUTONOMIA.md).
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

Não há lint configurado. O build também executa a checagem de tipos. `dist/` é o artefato de empacotamento posterior, ignorado no Git. O relatório de integração administrativa distingue testes locais, preparação e ativação na VM.

## Conexão e autenticação

A integração administrativa usa `POST /api/v1/admin-auth/login`, valida a sessão em
`GET /api/v1/admin-auth/session` e envia `Authorization: Bearer` nas consultas.
A senha é enviada somente no login, removida do formulário e não é persistida.
O token fica apenas em memória; recarregar a página exige novo login. Logout chama
a API para revogar a sessão e encerra o estado local mesmo se a rede falhar,
exibindo quando a revogação remota não pôde ser confirmada. Expiração ou sessão
recusada exigem novo login, sem fallback para Basic ou contrato legado.

Use `/p11-api`, perfil P11, em `http://127.0.0.1:4174`, com o túnel SSH autorizado
para `127.0.0.1:18000`. O trecho entre Windows e HarpiServer trafega por SSH;
frontend, proxy e API escutam somente no loopback. Uma publicação fora desse fluxo
exige HTTPS de mesma origem e revisão das origens permitidas; não usar HTTP na LAN.
O proxy permite explicitamente as rotas de autenticação e consultas administrativas,
recusa Basic e ingestão técnica, não injeta credenciais, remove cookies e conserva
`Cache-Control: no-store`. A página aplica CSP, no-referrer e nosniff.

Apenas URL e perfil são preferências persistidas no navegador. Nunca colocar senha,
token ou credenciais técnicas em `VITE_*`, URLs, bundle, localStorage ou
sessionStorage. Credenciais de PostgreSQL, MQTT e ingestão continuam somente no host.
O contrato legado foi preservado como referência, mas não oferece login administrativo.

MFA e recuperação por e-mail **não implementados**. Os exemplos visuais continuam
identificados como demonstração, sem efeitos sobre contas reais.

Implantação, backup, provisionamento local e recuperação estão em
[Integração administrativa](../docs/INTEGRACAO_CONTA_ADMINISTRATIVA_20261030.md).
Não substituir o bootstrap P11 ativo por `backend/delivery`.

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
