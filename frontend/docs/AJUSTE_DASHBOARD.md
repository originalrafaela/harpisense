# Dashboard — HarpIA e controles separados

Worktree e branch existentes reutilizadas: `frontend-v2` / `frontend/harpisense-v2`, sobre o commit local `5bdb154`. Alterações deste ajuste estão no diretório `frontend/`, para revisão, sem merge ou publicação. Backend e contratos oficiais preservados.

A referência `dahs-harpi_v1.png` não foi localizada nas referências locais. Foi inspecionada a referência disponível `referencias/versão_v2/proposta_visual/dash-proposta-visual.png`, mantendo os controles no topo, os painéis azul-acinzentados e os destaques azul/verde.

- `src/dashboard.tsx`: cartão HarpIA com asset da harpia, seleção de incidente, explicação vinculada, detalhes e histórico; componentes de controles operacionais.
- `src/api.ts`: consulta GET de histórico de projeção BitNet com validação e ID codificado na URL.
- `src/main.tsx`: estado exclusivamente local dos controles da demonstração; limpeza no logout e integração do contexto das páginas.
- `src/pages.tsx`: cartão inicial, recurso BitNet no carregamento do dashboard e controles também nas Configurações.
- `src/style.css`: disposição responsiva dos três botões de autonomia, modo, execução e cartão da harpia.
- `tests/dashboard.spec.ts`: testes isolados de demonstração sem requisições, operação desconhecida, valores explícitos do backend, vínculo/histórico de explicação e indisponibilidade.

Os três botões exibem M1 — Supervisionado, M2 — Autonomia parcial e M3 — Autônomo. Valores desconhecidos não selecionam nenhum botão. Modo IDS/SIMULATION/REAL e execution_enabled usam controles separados. Em operação, todos permanecem visíveis e desabilitados: “Alteração ainda não integrada”. Não existe endpoint de mutação integrado, nem confirmação otimista.

O P11 fornecido não informa controles efetivos no health. O adaptador de apresentação aceita campos explicitamente fornecidos, sem inferir a partir de decisões nem inventar endpoint. Os fixtures dos testes com controles no health representam apenas testes isolados desse adaptador, não evidência de suporte no servidor.

HarpIA não produz texto fora da demonstração: apenas apresenta projeções fornecidas e vinculadas ao incidente. Uma alternativa determinística deve vir identificada na própria explicação. Histórico é consultado sob demanda e não presume que o serviço BitNet ou a VM esteja acessível.

Capturas de dashboard em notebook e celular foram atualizadas em `docs/evidence/` e inspecionadas visualmente. A integração real com a VM permanece pendente; a autenticação e o transporte de respostas nos testes de navegador foram simulados isoladamente.
