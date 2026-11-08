# Backend — repasse desta integração

Branch feat/backend-incident-shap-integration, base a8fef1f + ficha94ad619.
Native-installers/candidata3 e prévias5174/5175 preservados. Sem instalador novo.

## Commits e ownership

- e71130a/761207e/2aa0ca4: controles recebidos de profile-state-contracts;
  não dupliquei nem editei seus controls/routes/operational_queue.
- a3eb885: SHAP real preservado da origem shap-library-product.
- dd7d813: ficha, avaliação, produtor transacional e sidecars de perfil/política.
- 071d052: primeiro acesso por conta, finalidades separadas e rotação das listas.
- 596120b/10acba5: matriz e ActionReview do responsável de segurança integrados.
- 5608399 + fb0f8e9: cases V2, dedup explícito, stale/UNKNOWN e origem imutável.

## Runner e contrato para Codex

API V2 em http://127.0.0.1:18083, processo iniciado em fb0f8e9, sobre o MESMO
PostgreSQL do E2E de18082. Origin http://127.0.0.1:5176 aceita, GET session sem
credencial retorna401 esperado. 18082 e prévias preservados. O dono do frontend
pode reiniciar SOMENTE5176 com HARPI_API_TUNNEL_TARGET=http://127.0.0.1:18083.
O proxy remove /p11-api; não acrescentar o prefixo ao alvo do servidor.

GET /api/v1/security/settings/mode/default → cases; health → operational_controls.cases.
Campo correto cases.contract_version=2, NÃO schema_version.
count_basis=distinct_incident_id. classification_counts={anomaly,confirmed_attack,incident}
conta IDs distintos por categorias sobrepostas; NÃO somar categorias. total_active_count
fica null sob observação insuficiente. Navegação só por incident_refs/links exatos.
Contrato docs/CASES_V2_CONTRACT_20261107.md; fixtures cases-v2/*.json em envelope.response.
Marcador de cobertura e UNKNOWN sem fato ativo anterior não criam caso ativo.

A API lê PG real, mas os payloads positivos de casos/modelos publicados são
fixtures artificiais/controladas, não ataques/tráfego operacional certificado.
Sem produtores com cobertura suficiente, retornar unknown/partial, nunca zero
saudável por ausência. Executor real continua not_integrated em qualquer M1/M2/M3.

## Primeiro acesso e persistência

GET first-access; POST first-access/codes {current_password,code} retorna
username,recovery_codes,password_reset_codes,first_access; POST first-access/confirm
{password_reset_generation}. Prefixo instalado existente /p11-api/api/v1/admin-auth.
Finalidades authenticator_recovery e password_reset são distintas. Originais apenas
na emissão; reemitir ambas revoga anteriores atomicamente. Ack da geração atual
é idempotente por conta. Reset não concede sessão nem remove TOTP.
Contrato docs/FIRST_ACCESS_AUTH_CONTRACT_20261107.md e migration auth/004_first_access.sql
no provisionamento, sem nova dependência/serviço.

Codex reportou E2E REAL browser5176 → proxy → API18082 → PG: bootstrap/TOTP/listas,
reload/login/reemissão/ack/logout/login completed sem modal. Não foi fixture de rota.
Consulta direta ao MESMO banco confirmou completed/geração2, MFA obrigatório,
listas gen1 revogadas/gen2 ativas e somente verificadores. Setup segue versão0/
not_started: onboarding não obriga wizard nem prova draft salvo/retomado.

Reinício de processos API A/B, com PIDs reais/boot IDs distintos e porta fechada
entre processos, preservou banco/ack/geração/MFA/setup. Upgrade do processo V2
para fb0f8e9 também preservou metadados. Nenhum cluster recriado, senha alterada
ou código do E2E consumido. Sem novo login browser após esse teste de restart.
Evidências process-restart.json, cases-process-upgrade.json, cases-live.json.
Não comprova reboot/serviço instalado nem uso do aplicativo Microsoft Authenticator.

## Checks e limites

- 11 testes próprios de primeiro acesso: HTTP/PG nativos, reset/replay concorrente,
  rotação das listas, escopo de conta, MFA preservado e rollback atômico.
- 12 testes de casos: HTTP/PG nativos, concorrência entre conexões, dedup/origem,
  nunca observado, fechamento, vínculo ausente, stale/UNKNOWN.
- 7 testes SHAP reais + 6 ficha/atividade HTTP/PG. BitNet off mantém estruturados.
- 7 controles e 14 regressões passaram inicialmente; 4 PG foram ignorados naquela
  regressão sem DSN (não confundir com suítes nativas posteriores).
- Hook ActionReview tem testes do responsável; o bridge HTTP aprovação/simulação
  ainda precisa de aceite end-to-end próprio. Não declarar defesa real disponível.

## Bloqueios do payload completo offline

Manifesto docs/evidence/backend-integration-20261107/payload-inventory.json.
Matriz docs/BACKEND_OFFLINE_PAYLOAD_MATRIX_20261108.md.
RF/IF aprovados: zero identificado, somente artefatos sintéticos de teste, nunca
substituídos pelos aprovados. Caminho/commit dos aprovados foi perguntado ao usuário.
BitNet: peso local confere com hash fixado e executáveis Windows encontrados;
não está no payload nativo; geração real pelo produto não exercitada e runtime
Ubuntu não localizado. Nunca rotular fallback determinístico como geração BitNet.
Wheels/binários/notices por SO, captura certificada, ativos genéricos/aplicadores/
executor/verificação e EXE/.run completos permanecem pendentes. Ubuntu ainda usa
apt-get update/install: bloqueio concreto de offline. Exigir aceites separados
Windows/Ubuntu limpos, sem Docker/checkout/rede externa, antes/depois reboot,
com painel/login/serviços e operações reais consultáveis na UI.
