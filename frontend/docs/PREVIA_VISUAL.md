# Prévia visual HarpiSense V2

Esta entrega amplia as telas e os fluxos demonstrativos existentes na branch `feat/frontend-backend-autonomia`. Os caminhos de operação P11/legacy foram preservados. A prévia é uma entrada separada, usa somente fixtures locais e exibe permanentemente **“Prévia visual — dados de demonstração, sem ações reais.”** Ela não é o modo operacional `SIMULATION`.

## Abrir no Windows

No PowerShell, na worktree `harpisense-worktrees/frontend-backend-autonomia`:

```powershell
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

Abra `http://127.0.0.1:5174` e selecione **Explorar demonstração visual**. Não é necessário criar `.env`, iniciar uma VM ou abrir túnel. A prévia não faz requisições a `/api/`, ao backend, ao túnel ou a serviços externos. A entrada administrativa continua usando o fluxo HTTP existente; estados de credencial inválida/serviço indisponível podem ser vistos como exemplos no painel **Ver estados de acesso (demonstração)**, sem enviar requisições.

O servidor Vite também mantém a rota operacional já existente; não use credenciais reais para a prévia. Não há comparação de usuário/senha no navegador. Campos demonstrativos não persistem valores.

## Telas e fluxos visuais

- **Login e conta:** usuário/senha com mostrar/ocultar, recuperação, MFA ilustrativo, cadastro/verificação de e-mail, alteração de senha/nome, sessão expirada e estados de falha. O QR é decorativo; nenhuma mensagem, código ou segredo é emitido.
- **Dashboard:** HarpIA em destaque, indicadores rotulados como demonstrativos, telemetria, serviços, última atualização e perfil. RF, IF e Risk continuam conceitos distintos.
- **Autonomia:** M1/M2/M3 com confirmação e pendências visuais, parada de emergência separada, e seletores independentes para IDS/SIMULATION/REAL e `execution_enabled`. A prévia não implementa Policy nem envia alterações.
- **Anomalias e incidentes:** filtros, detalhes, estrutura temporal e formulário de avaliação separado em evento, decisão de defesa e resultado. Uma aprovação não altera a classificação do evento.
- **Aprovações e defesas:** exemplos locais de proposta, aprovação, execução e resultado; alternativas vêm do catálogo oficial já gerado. Nenhum botão envia comandos.
- **IA/XAI:** cartões didáticos marcados como fictícios para RF calibrado, score IF, fatores de Risk, XAI/SHAP e Policy.
- **Configurações:** grupos Conta e segurança, Ambiente e Avançadas; serviços separados da URL usada pelo navegador; fluxo editar/validar/impacto/confirmar/aplicar/resultado. Assistente inicial com oito etapas, sem aplicar configuração.
- **Demais páginas preservadas:** telemetria, tráfego, inventário, saúde, cenários C01–C09, backup/restauração e auditoria. Cenários continuam “não executados” sem evidências; logs permanecem separados da HarpIA.

## Capturas

As imagens são capturas do Chromium na prévia local; login e telas de notebook usam viewport 1366×768, dashboard mobile usa 390×844:

- `docs/evidence/visual-login-notebook.png`
- `docs/evidence/visual-dashboard-notebook.png`
- `docs/evidence/visual-dashboard-mobile.png`
- `docs/evidence/visual-settings-notebook.png`
- `docs/evidence/visual-approvals-notebook.png`

## Integrações futuras

As telas são apenas apresentação; nada nesta entrega declara novas funções integradas. Futuramente, contratos/API devem especificar:

- gestão da conta administrativa, recuperação e mudança de senha/nome, e-mail e MFA/sessões;
- configurações operacionais tipadas (ambiente, dispositivos/redes, backend, MQTT, banco sem exposição de segredos, monitoramento, modelos, backup/VPN), validação, confirmação, revisão concorrente e resultado de aplicação;
- configuração inicial/idempotência e estado de instalação;
- avaliação administrativa de anomalias/eventos, separada de aprovação de defesa, com justificativa e resultado observado;
- consulta paginada de anomalias/telemetria/rede/incidentes, cronologia e filtros no servidor;
- detalhes completos de aprovação (alvo, nível, impacto, duração, alternativas, validade) e estados finais de execução, verificação e reversão;
- metadados de RF calibrado, IF, XAI/SHAP, Risk e Policy, incluindo versões e vínculo com a saída explicada;
- evidências de laboratório C01–C09, backup gerado/enviado/restauração verificada e auditoria com filtros.

O login existente e as consultas P11/HarpIA existentes foram preservados. Testes que usam respostas HTTP mockadas continuam isolados e não são prova de nova integração. A prévia não precisa deles.

## Verificações

Executar dentro de `frontend/`:

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npx.cmd playwright test
```

Os testes de `tests/visual-preview.spec.ts` também comprovam que as ações demonstrativas não geram requests operacionais. Relatórios efêmeros Playwright, `dist/`, caches e dependências não fazem parte da entrega.
