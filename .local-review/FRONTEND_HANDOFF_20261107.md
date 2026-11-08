# Repasse Frontend — revisão operacional

Recebido em 2026-11-07. Fonte: repasse do responsável Frontend e leitura do
relatório frontend/docs/REVISAO_OPERACIONAL_20261107.md.

- Branch: feat/frontend-operational-review.
- Base: a8fef1f5810ad5077658a29fe2aa407ffd21df6d.
- HEAD: 89d40eedfcbcb0c8200991f310ebaad89248c9da.
- Alterações frontend locais, sem staging/commit/push. Não integrar como se
  estivessem contidas no HEAD. Preservar autorização de sandbox.
- Prévia da fonte: http://127.0.0.1:5176/; desenvolvimento, demonstração isolada.
  Portas 5174/5175 preservadas conforme repasse. Não representa pacote instalado.

## Evidências e escopo

Responsável reporta typecheck, build (54 módulos), diff check, 66 testes unitários
e 14 Playwright com fixtures aprovados. Arquiteto verificou anteriormente
typecheck, 66 testes unitários e diff check; não repetiu todos os ensaios finais.

Ensaio reportado browser 5176 → proxy → candidato 18082, auth 071d052:
bootstrap, TOTP/enrollment, sessão, reload/login MFA, reemissão dos dois conjuntos,
confirmação de geração, logout e novo login completed sem modal. HTTP auth 200,
logout 204. TOTP calculado localmente; não comprova aplicativo Authenticator.
Sem segredos nas evidências; sem captura/trace/vídeo do modal. Não reproduzir
códigos, credenciais ou chave TOTP neste registro.

Gerenciador começa sem ativo presumido. Navegação e retomada após reload foram
testadas com fixtures; o ensaio HTTP real de auth não exercitou ConfigManager.

## Pendências encaminhadas

- Backend: contrato cases final e commit, contagens por classificação e caso
  distinto sem dupla contagem, IDs navegáveis, proveniência, revisão, validade e
  stale. Contagem source_item não comprova contagem de casos distintos.
- Backend: restart do processo candidato preservando o mesmo banco, consulta
  direta sanitizada de persistência/geração/ciência/uso dos códigos e MFA.
  Reiniciar runner recriando cluster não comprova persistência. Não é reboot do SO.
- Configurações: contrato genérico dispositivo/rede/sensor e aplicadores reais;
  atualmente firmware ESP32 indisponível e aplicação somente presentation.
  Verificar persistência real do rascunho após restart, independente de auth.
- XAI: inventário reportado sem RF/IF aprovados; não declarar ambos explicadores
  com modelos aprovados aceitos nesta rodada. Geração BitNet local real no card
  também não foi ensaiada.
- Edge: manter matriz separada dev HTTP, Windows instalado e Ubuntu instalado;
  offline, reboot, autostart e distribuição completa ainda sem comprovação.

Ownership permanece Frontend somente frontend/. Não editar sua worktree nem
native-installers por este repasse. Candidata 3 Ubuntu preserva aceite anterior
restrito ao escopo original.
