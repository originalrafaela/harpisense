# Consolidação do produto instalável

Base preservada: `96511ee9dffe62c646ace71717097684b3a9957f`, branch
`feat/native-installers`, worktree `harpisense-worktrees/native-installers`.
O checkout principal em `mqtt` não é base desta integração. Nenhum componente
foi substituído por uma versão antiga e nenhum cherry-pick foi feito sem auditoria.

## Versões e preservação

VM do usuário: `harpisense-ubuntu-reteste`, IP `192.168.155.149`.
Instalação confirmada da candidata 4: artefato SHA-256
`ec6b3dc27850fa4653a6218c78604023c0e9ee09913022bc02f36c49255ca11d`;
runtime instalado SHA-256
`c610b33fecbb56500716f79b1ba54ee6dd408a5bcd40cfc1dfeb5f0f0e6a9675`.
PostgreSQL/broker/API/consumidor ativos na consulta. A conta do usuário, MFA,
configuração e discos dessa VM não são usados nem alterados nos novos testes.

O [aceite Ubuntu da candidata 3](evidence/native-installers/ubuntu-candidate3-trial/README.md)
é preservado como execução histórica. O [reteste que revelou a corrida MQTT](evidence/native-installers/ubuntu-candidate3-retest-failure/README.md)
é uma evidência separada, corrigida na candidata 4. **Windows limpo segue
pendente**; processos nativos isolados no host Windows não são esse ensaio.
Nova candidata não herda aprovação de anteriores.

## Responsabilidades e comunicação

| Responsável | Arquivos/escopo |
|---|---|
| Frontend visual externo | Novos `product-header.tsx`, `product-incidents.tsx`, `product-harpia.tsx`, `product-visual.css`; sem alterar composição sem repasse |
| Frontend funcional / Arquiteto | `account-mfa.tsx`, `password-recovery.tsx`, `api.ts`, `controls.tsx`, pontos de montagem em `main.tsx`/`pages.tsx` |
| Backend | `backend/admin_auth`, `backend/delivery`, persistência, regras e testes correspondentes |
| Gerenciador | `backend/config_manager`, `asset-registry.tsx`, `config-manager.tsx`, `mqtt-devices.tsx` |
| Arquiteto | `backend/native_server`, `packaging/native`, migrações explícitas, composição, browser/HTTP/PostgreSQL e artefatos |

Maestri `list` e `debug` falharam dentro e fora do sandbox: pipe de daemon
encerrado, terminal `6af29098-2fb1-4da5-bf49-2d273df3a790`. Não houve entrega
confirmada aos terminais do canvas. Três agentes internos foram designados;
Frontend/Backend/Gerenciador falharam por limite de uso. Backend chegou a
informar um contrato, mas nenhum agente entregou código. O Arquiteto assumiu
as implementações funcionais para evitar paralisação silenciosa.

Encaminhamento manual confirmado ao Frontend externo: criar branch
`feat/product-visual-refinement`, worktree `harpisense-worktrees/product-visual-refinement`,
a partir de `96511ee`; entregar commits, arquivos, contratos, testes e pontos
de montagem. Não integrar em `mqtt`; Arquiteto incorpora após revisar.
Não presumir edição ativa de um Gerenciador cujo agente falhou.

### Entregas externas identificadas depois da primeira composição

Foram encontrados por inspeção Git (fora dos agentes internos que falharam):
Backend `c44bd6f551b43db8b4d478930cf366ab24422f39` em
`harpisense-worktrees/reusable-software`, branch `feat/reusable-software`;
Gerenciador `ac2b3b698cea90609b9c1e4241eb1091e869cbbb` em
`harpisense-worktrees/permanent-config-manager`, branch `feat/permanent-config-manager`.
Não estão incorporados nesta composição. Suas bases divergem do instalador;
substituir a árvore inteira perderia correções e evidências posteriores.

Há colisão real de contratos: Backend usa `/password-recovery/validate|reset`
com autorização intermediária e `/config/assets/{technical_id}` PUT, enquanto
esta composição usa `/password-reset/confirm` e `/config/assets` POST. O esquema
de `hs_config.asset` também difere (`technical_id` versus `device_id`). Não
compor os dois stores ou duas recuperações em paralelo. Integração posterior
exige escolher contrato canônico, adaptar os consumidores, migração preservando
dados e nova rodada de testes. Não sobrescrever nenhuma das worktrees.

Encaminhamento manual XAI aceito: preservar IDs `ai`/`#ai` e `harpia`/`#harpia`;
componente novo `model-analysis.tsx`/CSS, recebendo GET autenticado e incidente
com revisão. Backend prepara `/p11/incidents/{incident_id}/explanations` e
`/p11/detections/{detection_id}/explanations`. Na inspeção, `backend/xai_api`
e alterações de composição ainda não estavam commitados. Aguardar hash final;
validar vínculos de revisão/modelo/janela/ativo antes de integrar. Proxy somente
GET explícitos dessas rotas, sem wildcard de escrita. HarpIA não é substituída.

Base funcional própria publicada: `e103510`; ajuste de proveniência do
empacotamento: `8b9c9ef`. Não transferir aceite de VM para esses commits.

## Contratos e fluxos

Todos os caminhos abaixo recebem prefixo `/p11-api` no software instalado.
Dados humanos usam sessão Bearer em memória, não credenciais técnicas.

| Fluxo | Interface → contrato → serviço/persistência → leitura |
|---|---|
| Primeiro acesso/MFA | `AdminAccess` → `admin-auth/bootstrap`, `mfa/enrollment/begin|confirm` → MFAAdminAuth/PostgreSQL → sessão/login; grant não reutilizado após criar conta |
| Senha esquecida | `PasswordRecovery` → POST `admin-auth/password-reset/confirm` → tabela exclusiva `hs_admin_password_reset_code`, consumo transacional → novo login ainda exige TOTP |
| Códigos de senha | Emissão na confirmação MFA ou POST autenticado `password-reset/codes` com senha+TOTP → apenas hashes no banco → exibição única, lista distinta da recuperação MFA |
| Autenticador perdido | Login com senha → `mfa/recover` com código MFA → desafio de enrollment, sem sessão → novo autenticador confirmado; fluxo pré-existente preservado |
| Recuperação assistida local | `local-recovery` exige grant de finalidade recover e senha; não equivale a reset de senha; entrega operacional do grant continua limitada |
| Ativos permanentes | `AssetRegistry`, nos mesmos Configurações/primeiro uso → GET/POST `config/assets` → `AssetStore`, revisão esperada, auditoria e escopo instalação → releitura GET e após reinício |
| MQTT | `MqttDevices` → `config/mqtt/status` → observador do runtime/broker/heartbeat PostgreSQL → estados reais; rascunho não administra broker |
| Apresentação permanente | Proposta/validação/aplicação já existentes → `PresentationApplicator` agora na composição instalada → PostgreSQL+journal/arquivo privado atômico → consumidor confirma nome/fuso |
| M1/M2/M3 | Seleção local, confirmação explícita → `security/settings/mode/default` → lock/revisão/auditoria → estado efetivo só após resposta; executor acompanha IDS/SIMULATION |
| Pendências operacionais | `OperationalQueue` → fontes autoritativas frescas sob lock de controles → bloqueio por incidentes/anomalias/aprovações/execuções/verificações; ausência de produtor não vira fila vazia |
| Incidentes/evidências/modelos/risco/decisões/aprovações/execuções/verificações | Leitura P11 por espécie, paginação, histórico de revisões PostgreSQL; não transformar projeções em autorização ou inventar execução |
| HarpIA | Capacidade `deterministic_only`, explain vinculado ao incidente e histórico; sem geração/modelo habilitado implicitamente e sem autoridade de execução |

Novas migrações aditivas explícitas no empacotamento: `admin_auth/003_password_reset.sql`,
`config_manager/003_assets.sql`, `delivery/002_operational_authority.sql`.
Nenhum checksum das migrações anteriores foi alterado. A aplicação não cria
conta, não reseta identidade e não migra banco automaticamente no startup.

## Limites que não podem ser encobertos pela interface

- Os produtores autoritativos de ciclo de vida operacional ainda precisam
  publicar snapshots completos e atuais. Sem isso, a troca efetiva continua
  bloqueada. Histórico encerrado não constitui bloqueio quando reportado
  como estado terminal; projeções históricas não atestam ausência de pendências.
- Aprovação/execução/verificação mostradas por projeções não constituem
  comandos operacionais já integrados. Contenção REAL permanece bloqueada.
- Registrar ativo não grava firmware, emite identidade MQTT, altera ACL ou
  comprova presença física. O catálogo conserva suas limitações observadas.
- Conexões externas, captura e backup não são aplicados por um botão fictício.
- Microsoft Authenticator é o aplicativo TOTP de referência. Não há OAuth Microsoft.

## Validação e candidata 5

Fonte funcional: `e103510`; fonte exata dos pacotes: `8b9c9efe9eb5cd01b0be6812777da7ed08f0df4a`.
Versão embutida: `native-installers-20261106-candidate.5`, disponível em
`GET /p11-api/api/v1/native/status` autenticado.

- 64 verificações de composição fonte passaram com Chromium, HTTP,
  PostgreSQL e Mosquitto nativos exclusivos de teste.
- 68 verificações passaram com o **executável congelado distribuído**,
  incluindo versão real do runtime, recuperação de senha de uso único,
  preservação/reinscrição MFA, ativos, conflitos de revisão, persistência após
  reinício de API/consumidor/banco, nome/fuso efetivos e erro de API encerrada.
- Autoridades ausentes/vencidas e cada categoria ativa impediram troca;
  histórico encerrado não impediu. Executor derivado do modo e parada de
  emergência persistida foram conferidos; API permaneceu consultável.
- 51 testes frontend passaram. Regressão de controles: 14 passaram e quatro
  testes PostgreSQL antigos foram pulados por não configurar sua fixture;
  a aceitação acima exercitou PostgreSQL real e não equivale a esses skips.
- Ambos os builds concluídos; imports do runtime Windows aprovados. O próprio
  `.run` Ubuntu teve checksum, origem, migrações e módulos comparados à fonte Git.
- Transporte Vite permite somente endpoints novos explícitos; métodos e
  parâmetros indevidos continuam recusados. Não habilita rotas XAI ainda sem
  contrato final incorporado. Esse transporte de desenvolvimento não é o
  servidor do produto instalado.

[Relatório e limites](evidence/product-consolidation/README.md).
[Recibo da candidata 5](evidence/native-installers/published-assets-candidate5.json).
Esses resultados não são ensaio de instalação/reboot de uma nova VM Ubuntu
nem Windows limpo. O usuário permanece na candidata 4, sem migração ou alteração
de seus dados. A consolidação completa aguarda reconciliação e integração das
entregas externas descritas acima e os produtores operacionais autoritativos.
