# Entrega ao Arquiteto

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
