# Verificação executada — 18/10/2026

## Worktree de integração P11 — rodada atual

Executado em `integration/frontend-p11`, separada da worktree original do Frontend:

| Verificação | Resultado |
|---|---|
| `npm.cmd ci --no-audit --no-fund` | dependências instaladas pelo lockfile existente, sem novas dependências |
| `npm.cmd run build` | TypeScript + Vite passaram; 34 módulos; JS 183,91 kB / gzip 59,24 kB |
| `npm.cmd test` | 17 testes passaram, incluindo proxy HTTP Vite com servidor de fixture isolado |
| `npx.cmd playwright test` | 17 testes passaram; regressão das telas, login, vazio, indisponível e correspondência da projeção |
| Script `open-p11-tunnel.ps1` | sintaxe validada pelo parser PowerShell; não aplicado à VM |
| `git diff --check` | sem erros de whitespace |
| Worktree original `frontend-v2` | limpa, HEAD preservado em `1d7ed4d` |

O teste de transporte efetivamente inicia um proxy Vite e um servidor HTTP de fixture locais, confirma preservação de Basic e status, reescrita do prefixo, no-store, remoção de cookies, recusa de POST/recurso fora da lista/origem externa/query não prevista e ausência de credenciais nos logs capturados. Isso comprova o transporte local sob teste, não um túnel SSH ou backend real.

Os testes de navegador usam fixtures isoladas para conferir ID, revisão, source, created_at e payload `poste2/temperatura/tipo`, além de rejeição de credenciais inválidas, rede indisponível, lista vazia, senha fora de localStorage/sessionStorage/cookies/console e demonstração sem requisições operacionais. A captura [dashboard com fixture de contrato](evidence/p11-contract-dashboard-isolated.png) contém aviso explícito de teste isolado e foi aberta para inspeção visual. Capturas de notebook/celular também foram atualizadas nesta worktree.

Na primeira execução, o hook de configuração do proxy retornava incidentalmente o objeto de middleware e impedia o Vite de iniciar; corrigido para não retornar esse objeto. Uma primeira asserção do fluxo visual esperava o caminho após o proxy em vez do prefixo visto pelo navegador; corrigida. Os resultados acima são da rodada final, após essas correções.

**Não foi comprovado o aceite real.** Não houve acesso à VM, autenticação real, publicação MQTT, leitura PostgreSQL ou confirmação visual de uma medição recém-publicada. O procedimento e os arquivos necessários estão em [Integração P11 real](INTEGRACAO_P11_REAL.md). As seções seguintes preservam resultados históricos da entrega original.

## Rodada posterior — HarpIA no dashboard e controles separados

Na mesma worktree e branch, após o commit inicial, o ajuste passou por `npm.cmd run build` (inclui checagem TypeScript), `npm.cmd test` (**12 testes passaram**) e `npx.cmd playwright test` (**14 testes passaram**). Bundle atual: JS 181,59 kB / gzip 58,62 kB; CSS 9,74 kB. Nenhuma nova dependência.

Novos testes: alternância independente de M1/M2/M3, IDS/SIMULATION/REAL e execução na demonstração sem requisições; valores desconhecidos sem seleção ativa; valores explicitamente retornados em fixture de saúde; controles reais desabilitados; explicação ligada ao incidente mais recente e seleção de outro incidente; identificação de alternativa determinística; histórico com revisões e exclusão de outro incidente; serviço de explicações indisponível; histórico inválido e codificação de ID no cliente HTTP. Os fixtures de controles não comprovam existência desses campos na VM.

As capturas de dashboard em notebook e celular foram atualizadas e abertas para inspeção. Os seletores iniciais dos novos testes não localizavam os selects pela correspondência exata do texto do label; a rodada final usa o papel acessível `combobox` e seu nome, e passou integralmente.

Nenhuma alteração de backend/contratos nem comando operacional. A integração real com a VM permanece pendente. Veja [ajuste do dashboard](AJUSTE_DASHBOARD.md). Os resultados abaixo registram a rodada inicial da entrega.

Ambiente: Windows, Node v24.12.0, npm 11.6.2. Execução na worktree `frontend/harpisense-v2`, dentro de `frontend/`. APIs usadas nos testes são respostas simuladas isoladas; não são evidência de conexão à VM.

| Verificação | Resultado |
|---|---|
| `npm.cmd install --no-audit --no-fund` | concluída; package-lock gerado |
| `npm.cmd run typecheck` | passou |
| `npm.cmd run build` | passou; TypeScript + Vite 6.4.4, 31 módulos |
| Bundle final | JS 174,94 kB, gzip 56,82 kB; CSS 7,71 kB |
| `npm.cmd test` | 10 testes passaram |
| `npx.cmd playwright test` | 9 testes Chromium passaram |
| Lint | não configurado; não declarado como executado |
| Catálogo oficial | cópia e original com SHA-256 idêntico: `b65e351f97ab008b2022f27eb66bd9b76fa3ac230f31bd9e1e5be857a2fb071b` |
| Git | sem alterações fora de frontend na worktree; sem merge/push/publicação |

## Cobertura dos testes isolados

Testes unitários: lista P11 válida/vazia/inválida; projeção incompatível; LDR bruto sem conversão; temperatura sem luminosidade inventada; leitura desatualizada; autenticação por consulta protegida com Basic; cancelamento preservando sessão; logout impedindo novas consultas; HTTP 401/403/404/503; falha de rede; JSON inválido; URL inválida/com credenciais; timeout.

Chromium: navegação pelas 14 telas da prévia; nenhuma requisição `/api/` em demonstração; aviso permanente; aprovação desabilitada; login protegido e navegação preservando Basic; logout limpando campos; credenciais ausentes do localStorage; HTTP 401/403/503 mantendo login; resposta inválida após login gerando erro sem lista vazia nem fallback; teclado alcançando usuário/senha/botão; botão acessível em notebook 1366×768; mobile 390×844 com menu e sem overflow global.

As tabelas mantêm rolagem horizontal local. Controles não suportados ficam desabilitados com motivo textual. Não existe comando de mutação cujo envio precise ser repetido ou cuja confirmação seja simulada.

## Inspeção visual

Capturas produzidas pelo Chromium e abertas para inspeção visual:

- [Login em notebook](evidence/login-notebook.png): campos vazios e botão acessíveis; emblema e logo como imagens, formulário como elementos reais.
- [Dashboard em notebook](evidence/dashboard-notebook.png): sidebar, cartões, controles independentes, telemetria, tabelas e saúde.
- [Dashboard móvel](evidence/dashboard-mobile.png): cartões em coluna, navegação recolhida e tabelas com rolagem local.

As capturas representam demonstração, não operação real. Saúde desconhecida permanece desconhecida.

## Correções durante a verificação

O primeiro teste Node revelou sintaxe de parameter properties incompatível com strip-only; o cliente passou a declarar campos explicitamente. O primeiro teste de login Chromium revelou chamada de fetch sem vínculo ao contexto global; corrigido com bind antes da rodada final. A primeira tentativa de Chromium não pôde iniciar por ausência do navegador; após instalação autorizada, a suíte final passou. Essas falhas iniciais não estão contadas como sucesso.

## Limitações

Não houve conexão real à API Ubuntu nem inspeção remota do servidor. Não foram validadas credenciais administrativas das VMs, conectividade/proxy/CORS/HTTPS, inventário real, modelos, aprovação/execução, ensaios Kali, backup ou restauração. O relatório fornecido é evidência externa do fluxo Poste 2, não uma execução realizada por este agente. Nenhum dado de exemplo foi apresentado como medição real.

## Validação assistida em 18/10/2026 — atualização de estado

As afirmações anteriores de ausência de acesso real descrevem a preparação. Nesta sessão, o operador confirmou serviços, health autenticado, túnel restrito e registro novo coincidente no PostgreSQL e na API, com o mesmo ID/horário/tipo exibidos no dashboard. O payload foi sintético, transportado pelo fluxo real; isso não comprova medição física ou local de execução do publicador. Confira evidências, campos ainda pendentes e limites em [INTEGRACAO_P11_REAL.md](INTEGRACAO_P11_REAL.md).

Checks locais desta rodada: 17 testes Node aprovados, build/tipos aprovados e 3 testes Chromium do fluxo P11 aprovados. Todos os testes automatizados usam respostas isoladas; a evidência da VM foi fornecida pelo operador. A suíte completa Chromium não foi repetida nesta rodada. Nenhum merge ou push foi realizado.
