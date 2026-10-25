# HarpIA: consulta de explicações na interface — 25/10/2026

Worktree `harpia-ui`, branch dedicada `integration/harpia-ui`, criada do commit
`280bab4` de `integration/frontend-p11`. Essa base já contém a entrega frontend
`f52d837`; não houve merge na main nem alteração nas worktrees frontend-v2,
integration-p11 ou harpia-bitnet. A alteração local de CSS existente em
integration-p11 foi preservada e não foi copiada para esta entrega.

## O que mudou

Reutilizado o cartão HarpIA na primeira página do dashboard, avatar e estilos
existentes. Explicação permanece vinculada ao incidente selecionado. Agora mostra:

- ID e revisão do incidente; revisão própria da projeção da explicação,
  separada da revisão do incidente à qual ela se refere.
- Horário de geração, quando fornecido; caso contrário, horário do registro na
  API com rótulo explícito. Ausência de horário é exibida como não informada.
- Origem do **texto** (`data.source`): BitNet não verificado, alternativa
  determinística ou origem desconhecida; não confunde produtor trusted-service
  da projeção com origem do texto.
- Estado carregando, sem explicação, indisponibilidade inicial/endpoint não
  integrado, erro de consulta e explicação vinculada a outra revisão.
  Se o vínculo de revisão não veio, mostra atualidade não verificada.
- Consulta manual de explicações registradas, com descarte de resposta atrasada
  após trocar de incidente. Falha não gera fallback fictício nem entra no demo.

`data.incident_revision`, quando disponível, ou `data.revision` do DTO P11,
identificam a revisão explicada. O número do envelope de projeção **não é usado**
como substituto dessa informação. Revisões divergentes são sinalizadas; texto
histórico não é apresentado como explicação atual.

O cartão continua visível enquanto carrega a primeira página. A consulta manual
é limitada à primeira página de até 50 projeções; isso é informado na interface.
Não é uma busca global nem afirma inexistência de explicações em outras páginas.
Histórico usa o ID da projeção da explicação, não o ID do incidente no caminho.

## Contratos e fluxo

Referência local mais recente: `referencias/versão_v2/11_Backend_Dashboard_BitNet/`
`HarpiSense_Pacote11_Backend_Dashboard_BitNet_v2/backend11/service.py` e `bitnet.py`.
Frontend original e integração P11 existentes foram consultados antes de alterar.
Pacotes anteriores de `Versões corretas` continuam válidos para componentes não
atualizados; não houve Drive nem criação de contrato de domínio concorrente.

| Endpoint P11 da referência | Uso nesta interface |
|---|---|
| GET `/api/v1/p11/health` | informação técnica da API; não autoriza geração |
| GET `/api/v1/p11/incident?limit=50&offset=…` | incidentes da página selecionada |
| GET `/api/v1/p11/bitnet?limit=50&offset=0` | consultar projeções persistidas; filtrar pelo incidente no cliente |
| GET `/api/v1/p11/bitnet/{id}/history` | histórico da projeção já identificada |
| GET `/api/v1/p11/explain/{incident_id}` | **não chamado**: a referência executa inferência, não é lookup de projeção |

A referência não oferece contrato explícito de autorização operacional da geração
nem garante persistência de uma nova explicação pelo GET explain. Não se inventou
rota/flag de autorização no frontend. O botão **Gerar explicação permanece desabilitado**,
inclusive se health.bitnet for available. Disponibilidade técnica não habilita
operação. Mensagem distingue essa restrição da leitura de registros já existentes.

Fluxo preparado: navegador → API HarpiServer → serviço HarpIA (futuro, pelo backend).
Nesta rodada somente a primeira ligação foi exercitada com fixtures. Navegador
nunca consulta `/completion`, `/complete`, `/explain` do wrapper ou `/ready`, nem
portas 8091/8092. Nenhum segredo do serviço HarpIA foi incluído no frontend.
Mantida autenticação administrativa P11 em memória, sem armazenar senha/token.
Não houve gravação de projeções, decisões, Risk, Policy, autonomia ou configurações.

Por padrão `VITE_P11_RESOURCES` continua restrito à telemetria. Sem habilitação
explícita dos recursos de leitura na conexão, HarpIA informa que não está integrado.
Nos testes isolados usa-se `all`, sem que isso permita gerar ou executar ações.
Legacy sem esses endpoints continua indisponível, sem dados substitutos.

Demonstração permanece entrada voluntária **Abrir prévia visual**, com aviso
permanente e dados próprios. Os resultados reais do BitNet da rodada 7 não foram
copiados para o demo, nem para registros de incidentes reais.

## Verificações executadas

- **22 testes Node de dados/contratos/transporte aprovados**. Novos testes cobrem
  revisão de vínculo versus revisão da projeção, origem/horário ausentes, seleção
  por incidente, lookup só em bitnet e erro sem dados fictícios.
- **TypeScript e build Vite aprovados**, sem publicação de dist.
- **20 testes Playwright aprovados**, 12,8 s, com navegador real e fixtures HTTP
  sintéticas: demonstração, seleção/histórico, indisponibilidade, revisão antiga,
  health disponível sem liberação, carregamento/erro, resposta atrasada, login,
  navegação e viewport mobile. Um teste adicional direcionado (2,7 s) conferiu o
  rótulo final de horário e gerou captura local.
- Captura inspecionada: `frontend/local-evidence/harpia-stale.png`, somente fixture
  sintética. Capturas novas ficam ignoradas em local-evidence; imagens já entregues
  em docs/evidence foram preservadas. Testes não reutilizam Vite já em execução
  (`reuseExistingServer=false`) e encerram sua instância própria em loopback.

Dependências locais existentes foram reutilizadas, sem instalação global ou novos
pacotes. Primeira chamada npm no diretório raiz estava fora do package.json; foi
corrigida para frontend. Leitura do prefixo npm em AppData exigiu execução
autorizada fora do sandbox. Testes finais acima passaram nesse ambiente.

**Não houve teste end-to-end navegador → HarpiServer real → HarpIA.** Não se
acessaram VMs ou serviços existentes, não se alterou backend/API, não se abriu
túnel nem se publicou site. Contratos locais e mocks não comprovam que os endpoints
estejam implantados ou acessíveis na VM atual.

## Pendências antes de habilitar geração

1. Confirmar, com o responsável pelo HarpiServer, implantação e acesso dos endpoints
   de incidente, projeções bitnet e histórico; configurar escopo de leitura e canal
   autenticado. Localhost da VM não é localhost do Windows.
2. Resolver a qualidade do BitNet: após o patch o texto ficou legível em A/B,
   mas a rodada 7 reprovou fidelidade. Compilação/health/testes de UI não alteram isso.
3. Backend definir autorização operacional explícita separada de readiness, contexto
   sanitizado, revisão de incidente, origem/horário e persistência da explicação,
   tratamento de fila/timeout/fallback e acesso apenas servidor → HarpIA.
4. Avaliar conjunto maior de casos e revisão humana, incluindo ausência de dados,
   estado real de ação, RF/IF/Risk e adversariais. Três exemplos satisfatórios não
   garantem confiabilidade e não autorizam liberação automática.

Reprodução local, dentro de frontend: `npm.cmd test`, `npm.cmd run build`,
`node node_modules/@playwright/test/cli.js test`. Vite de testes usa loopback 5174
e fixtures; deve recusar porta ocupada em vez de reaproveitar outro serviço.
