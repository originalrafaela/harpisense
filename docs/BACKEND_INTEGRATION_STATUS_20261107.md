# Integração backend: estado em 2026-11-07

Branch feat/backend-incident-shap-integration, base a8fef1f + ficha 94ad619.
Controles 3c81a21/903c595 integrados como e71130a/761207e. Não editarei
operational_queue.py, controls.py, routes.py ou testes pertencentes ao responsável
feat/profile-state-contracts; aguardando seu commit final de cases.

Ao responsável action_review: NÃO implementei ciclo ou rotas de aprovação/execução
equivalentes. Pode concluir delivery/action_review.py e migração aditiva na sua
worktree audit/native-security-acceptance-20261107. Integrarei seu hook após
publicação; preciso assinatura, migração e retorno para montar rotas com sessão
administrativa. incident_dossier e assessment permanecem comigo. Todos usam lock
72611027, nenhum executor real será habilitado.

SHAP: origem feat/shap-library-product ainda em a8fef1f com arquivos não commitados.
Cópia preservada na integração, sem editar a origem. 7 testes SHAP reais passaram
no Python Windows de desenvolvimento, 7 controles e 14 regressões passaram;
4 regressões PostgreSQL foram ignoradas por falta de TEST_DATABASE_URL naquela
execução. Aceite HTTP/PostgreSQL desta candidata ainda em preparação.

Dependências científicas: shap 0.50.0, scikit-learn 1.8.0, numpy 2.3.5,
pandas 2.2.3, scipy 1.17.0, joblib 1.5.3; transitivas no lock científico comum.
Ainda faltam locks nativos validados por Windows/Ubuntu e aceite em pacote novo.
Tree RF explica probabilidade pré-calibração. Permutation RF explica probabilidade
calibrada usada pelo Risk; IF explica -score_samples validado contra a detecção,
não chance de ataque nem o Risk total. Tree IF é recusado por saída incompatível.
SHAPLEY_PERMUTATION histórico permanece com nome e algoritmo próprios.

URL backend desta integração ainda não confirmada. Nenhum serviço novo foi
iniciado nem instalador gerado. native-installers a8fef1f e prévia 5174 preservados.
Não há comprovação de execução em Windows/Ubuntu limpos, reboot ou autostart.
Nenhum desses resultados pode ser apresentado como aceite instalado.
