# Entrega funcional isolada do núcleo

Worktree `harpisense-worktrees/detection-composition`, branch
`feat/detection-composition`, base preservada `9d35906`. A inspeção inicial encontrou
a worktree limpa; não houve reinicialização de trabalho nem alteração da main.

| Entrega | Implementado | Integrado | Validado localmente | Validado na VM | Pendente |
|---|---|---|---|---|---|
| RF/IF → Risk/Policy → PostgreSQL/P11 | Sim | Sim, isolado | Sim, estimadores reais sobre dados sintéticos | Não | Bundles e entrada de laboratório |
| P08 → entrada certificada | Gate e auditor offline | Conversor instalado + P08/P09 comparados | 8 testes novos de formato/features; sem repetir inferência | Fontes/conversão conferidas em leitura; coleta não validada | Console Poste2, relógios, logs/cursores assinados e bundles operacionais |
| M1/M2/M3, proteção e execução | Motor vigente preservado | Sem despacho | Matriz e gates em fixtures declaradas | Não | Revisão posterior do executor Edge |
| Frontend segurança d172a387 / MFA 737ae26 | Entregas dos agentes | Contrato MFA/OpenAPI revisado; não reaplicados | Recibos Backend revisados, não repetidos | Não implantadas | Transporte frontend/instalador e ensaio no ambiente-alvo |

O teste reproduzível está em `backend/detection_composition/README.md`. Evidências:
`docs/evidence/detection-composition-20261104/composition.json` contém os modelos,
hashes de dados/bundles, versões, duas detecções, risco, decisão e respostas P11;
`test-results.json` registra os testes da composição. Os bundles/CSVs sintéticos
ficam somente em `local-evidence/detection-composition/`, sem publicação como
artefato operacional. São 11 testes da composição, 46 regressões dos adaptadores
e 14 de lote/staging; os dois últimos grupos usam fixtures existentes e não
constituem inferência nem validação no laboratório.

A execução sintética produz risco COMPLETE quando há criticidade explicitamente
fornecida; sem inventário, o risco permanece INCOMPLETE e sem score. Sem alvo e
evidência corroborada, a decisão é OBSERVE_ONLY. Probabilidade RF, anomalia IF e
risco permanecem campos diferentes. Não existe contenção, despacho ou geração
operacional BitNet nesta entrega. Decisões de fixtures autorizadas em M2/M3 também
mantêm `execution_requested=false`.

A consulta SSH de 2026-11-05T00:11:52Z mostrou zero units em falha. A busca foi
limitada ao staging P09, profundidade cinco; não encontrou bundles nos caminhos
legíveis e encontrou um backup inacessível. Isso não é aceite de todos os serviços
nem comparação completa de release. Nenhuma implantação, migração, reinício,
ataque ou alteração de topologia foi executada.

O aceite de telemetria informado pelo usuário fica preservado: a mesma mensagem
foi confirmada tecnicamente até PostgreSQL e visualmente pelo relato do operador
na interface autenticada. Isso não comprova passagem pelo gateway, cobertura P08
ou atualização automática. Não é usado como evidência de inferência.

## Dependências exatas e menor próximo trabalho

1. **Edge:** certificar uma janela P08 e o vínculo sessão/sensor/alvo, reconciliar
   controlador/wrapper instalados e candidata antes de qualquer coleta. O código
   entregue `prepare_verified_log_counts` mantém `authorized_for_inference=False`
   e `log_counts={}` inclusive com assinatura verificada. É necessário entregar
   um adaptador certificado das features realmente observáveis, sem habilitar
   contagens de logs auxiliares sem cobertura. Esta composição não remove esse
   bloqueio. Nenhuma janela de laboratório foi aprovada nesta rodada.
2. **Modelos:** fornecer diretórios confiáveis RF e IF contendo `model.joblib` e
   `metadata.json`, SHA256 fixado externamente, `model_version`, schema, perfil,
   janela e ordem de features compatíveis, versões de ambiente e proveniência dos
   dados. RF requer treino/calibração separados por sessão; IF requer baseline
   normal revisado e calibração separados. Não é necessário recriar os algoritmos:
   os treinadores existentes são reutilizáveis. Não treinar modelo operacional
   com os CSVs artificiais desta entrega. As nove features de pacote não suprem
   cenários que precisam de logs de autenticação/MQTT/API.
3. **Integrador:** após esses dois insumos, ligar a entrada certificada ao mesmo
   caminho de inferência/persistência, reexecutar incompatibilidades e reprocessamento
   e comparar hashes/backup da VM antes de propor implantação. Não promover o
   método sintético a serviço operacional.

## Coordenação e repasse manual

A comunicação Maestri foi tentada uma vez por destinatário; o retorno consultado
da Edge informa falha de comunicação com o arquiteto. Não se tomou a ausência de
resposta como aprovação e não se repetiram mensagens ao próprio terminal.

- **Edge:** dona de `p08_captura/`. O repasse `d6a2380` confirma edição exclusiva de
  `backend/p08_p09/` pela composição nesta worktree. Em `7fe8294`, os dois diretórios
  foram incorporados sem alteração de `c314ca5`. A continuação acrescenta somente
  auditor e snapshots de conversão em `backend/p08_p09/`; não altera a captura Edge
  nem libera os gates. Detalhamento: `docs/COMPATIBILIDADE_P08_LAB_20261105.md`.
- **Frontend:** `feat/frontend-auth-defense-v2`, `d172a387`, usa consultas P11
  existentes e risco em `incident.data.risk`, com vínculos por `incident_id` e
  `decision_id`. Não há endpoint operacional de aprovação liberado por esta
  composição. `GET /api/v1/p11/{kind}` e `/{kind}/{id}/history` permanecem iguais.
- **Backend:** `feat/admin-bootstrap-mfa`, `3b5aa70`, mantém propriedade de
  `admin_auth/`, operações e testes MFA. O ponto candidato
  `install_candidate_admin_auth` substitui a instalação legada depois de P11 e
  controles, antes da API de configuração. É opt-in; não compor duas camadas de
  autenticação. Validar adesão da conta existente e recuperação antes da VM.
- **Gerenciador de Configurações:** instalador, custódia da chave MFA,
  configuração posterior e migrações explícitas permanecem nessa frente.

Esses commits dos agentes foram revisados por conteúdo e não reaplicados nesta
branch. `de3fefe`, `086cb16`, `bcba816` e `1be0503` já pertencem à base `9d35906`.

## Próximo ensaio proposto, ainda não executado

Primeiro, ensaio **somente de detecção** com tráfego legítimo Poste 2 → broker
Windows pelo percurso confirmado pela Edge; alvo permitido é a janela desse
publicador e tópico já contratados. Registrar um payload único e seu identificador,
horários UTC sincronizados, sessão P08, interfaces, hashes de captura, cobertura
por fonte e janela de 10 s. Conferir as nove features e eventuais logs exigidos
pelo bundle antes de inferir. O perfil será M1/IDS, sem executor ou regras novas.

Critério de aceite: a mesma janela identificada gera os dois registros de detecção,
incidente/risco/decisão e as respectivas consultas P11; falta de cobertura ou feature
deve bloquear, sem score inventado. Tráfego legítimo pode produzir OBSERVED ou
OBSERVE_ONLY; isso não reprova o ensaio nem demonstra eficácia contra C01–C09.
Preservar acesso administrativo e configuração atual; interromper se houver
divergência de rota/relógio, perda de cobertura ou erro de persistência. Recuperação:
encerrar apenas a coleta do ensaio e preservar seus artefatos; sem alteração de
firewall/topologia a desfazer. Cenários de ataque exigem plano e alvos apresentados
separadamente antes de execução.
