# Verificação executada — 18/10/2026

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
