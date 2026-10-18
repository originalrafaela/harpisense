# Entrega ao Arquiteto

## Preparação de integração em worktree separada

O registro original abaixo foi preservado. A rodada atual está na branch `integration/frontend-p11`, worktree `D:\Projetos\tcc - harpisense\harpisense-worktrees\integration-p11`, derivada do frontend `1d7ed4d`. As adaptações são alterações locais nesta worktree, sem novo commit, merge ou push. A branch/worktree original do Frontend permanece limpa e intacta.

Entregues: transporte local restrito até túnel SSH manual, login P11 pelo health protegido, escopo default health/telemetry, apresentação fiel do payload provisório do Poste 2 e testes de contrato/transporte/navegador. Não há recriação do P11, banco, motores ou autenticação. Build/tipos e 17 + 17 testes passaram. O aceite real segue bloqueado pela falta de acesso confirmado à VM e de fontes atuais da adaptação. Veja [matriz, execução e pendências](INTEGRACAO_P11_REAL.md).

## Registro da entrega original do Frontend

Branch: `frontend/harpisense-v2`.

Worktree: `D:\Projetos\tcc - harpisense\harpisense-worktrees\frontend-v2`.

Base: `integration/primeira-entrega`, commit `a7cb501` (contém main e integrações das áreas). Nenhum merge, push ou publicação foi realizado. Alterações limitadas a `frontend/`; backend, persistência, contratos, políticas, credenciais, VMs e firewall preservados. Arquivos não versionados originais não foram sobrescritos.

Entrega registrada em commit local na branch existente `frontend/harpisense-v2`, com a mensagem `feat(frontend): implement HarpiSense V2 dashboard and integration-ready views`. Dependências, dist, caches, resultados temporários e arquivos de ambiente reais ficam fora do commit. Não houve merge, push ou publicação.

Arquivos de entrega:

- `frontend/package.json`, `package-lock.json`, `tsconfig.json`, `playwright.config.ts`, `index.html`, `.env.example`, `.gitignore`, `README.md`.
- `frontend/src/api.ts`, `components.tsx`, `pages.tsx`, `main.tsx`, `demo.ts`, `style.css`, `catalog.json`.
- `frontend/scripts/catalog.mjs` e `docs/harpisense_catalog.source.py` (cópia da fonte oficial).
- `frontend/public/assets/harpy.png` e `brand.png` (proposta visual local).
- `frontend/tests/api.test.ts`, `navigation.spec.ts`.
- `frontend/docs/INTEGRACAO.md`, `VERIFICACAO.md`, `ENTREGA.md`, `evidence/*.png`.

Para revisar, entrar na worktree e executar o README. Verificar matriz de endpoints e limitações antes de conectar a VM. Aprovar mapeamento P11 atual, autenticação e caminho de rede antes de disponibilizar. O Arquiteto poderá integrar o commit local pelo fluxo habitual, após revisão. Não copiar node_modules, dist, .env ou credenciais.

A integração real com a VM permanece pendente. Os testes de autenticação usaram respostas simuladas isoladas; não validaram credenciais nem acesso ao servidor.

Critério entregue: interface navegável, testes isolados, assets e documentação. Integração real, confirmação de serviços/credenciais atuais, ensaios, aprovação e execução permanecem dependentes de contratos e acesso autorizados, listados em INTEGRACAO.md.

## Ajuste posterior ao commit inicial

O dashboard ganhou HarpIA com seleção de incidente, detalhes e histórico, além de controles de autonomia M1/M2/M3 separados do modo e da execução. Novos arquivos: `src/dashboard.tsx`, `tests/dashboard.spec.ts` e `docs/AJUSTE_DASHBOARD.md`. Também foram atualizados cliente HTTP, coordenação/páginas, estilos, testes do cliente, documentação e capturas do dashboard. Este ajuste é registrado em commit adicional na mesma branch local para envio ao destino remoto autorizado `frontend`. Resultados atuais: build e tipos aprovados; 12 testes unitários e 14 testes Chromium passaram.


## Destino remoto autorizado

Repositório origin: https://github.com/originalrafaela/harpisense.git. A branch local permanece frontend/harpisense-v2; o destino remoto solicitado é frontend. O envio deve preservar trabalho remoto, sem force push ou merge em main. A confirmação do hash remoto é feita após o push. A integração real com a VM permanece pendente, e os testes de autenticação usaram respostas isoladas.

## Validação assistida em 18/10/2026 — atualização de estado

As afirmações anteriores de ausência de acesso real descrevem a preparação. Nesta sessão, o operador confirmou serviços, health autenticado, túnel restrito e registro novo coincidente no PostgreSQL e na API, com o mesmo ID/horário/tipo exibidos no dashboard. O payload foi sintético, transportado pelo fluxo real; isso não comprova medição física ou local de execução do publicador. Confira evidências, campos ainda pendentes e limites em [INTEGRACAO_P11_REAL.md](INTEGRACAO_P11_REAL.md).

Checks locais desta rodada: 17 testes Node aprovados, build/tipos aprovados e 3 testes Chromium do fluxo P11 aprovados. Todos os testes automatizados usam respostas isoladas; a evidência da VM foi fornecida pelo operador. A suíte completa Chromium não foi repetida nesta rodada. Nenhum merge ou push foi realizado.
