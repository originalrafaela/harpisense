# Preparação do aceite nativo e segurança — 2026-11-07

Delta obrigatório offline e percurso por funcionalidade: [matriz atual](offline/FUNCTIONAL_MATRIX.md), [inventário segurança](offline/CAPTURE_EXECUTOR_INVENTORY.md) e [hashes/VMs/testes observados](offline/inventory-observed.json). As evidências anteriores abaixo permanecem com seu escopo original e não aprovam offline completo.

Branch: `audit/native-security-acceptance-20261107`. Base integral: `a8fef1f5810ad5077658a29fe2aa407ffd21df6d`.
Worktree: `harpisense-worktrees/native-security-acceptance`.
Escopo: levantamento, testes isolados e preparação; nenhuma contenção real, reboot do host, alteração de instalação em uso ou build de instalador para revisão visual.

## Preservação e evidências observadas

`native-installers` permanece em a8fef1f, com alterações locais preexistentes em runtime/empacotamento e `review_product.py`; não foram copiadas, descartadas ou editadas. A prévia 5174 consta no portal conectado e não foi reiniciada nem modificada. A base isolada não inclui automaticamente alterações locais de outras equipes.

14 testes existentes de `backend/delivery_tests/test_delivery.py::DeliveryTests` passaram nesta worktree. Resultado: `security-fixture-result.json`. Usam repositório em memória e fixtures isoladas; não são evidência de PostgreSQL instalado ou máquina limpa. Incluem política de 27 combinações caso/modo, bloqueio REAL, emergência, autorização manual, frescor, concorrência e repetição da simulação com um único resultado armazenado. Não executamos a classe PostgreSQL, pois ela exige banco descartável identificado e trunca tabelas.

Evidências históricas lidas em `../native-installers/docs/evidence/`:

- `product-consolidation/product-native-result.json`: 68 checks, executável congelado, PostgreSQL/MQTT/Chromium privados, `machine_reboot=false`, `service_registration=false`; não aprova Windows instalado limpo.
- `model-mount-review/result.json`: 12 checks HTTP nativo/PostgreSQL/Chromium, incidentes sintéticos e explicação persistida; não comprova cálculo Tree/Permutation embarcado.
- `packaging/native/README.md`: relata Ubuntu candidata 3 histórico aprovado e reteste de instalação posterior falho; candidata 4/5 não herdam homologação anterior. Versão, hash e ensaio devem coincidir.

## Executor e contrato M1

Código base: `backend/delivery/controls.py`, `simulation.py`, `routes.py`, `control_store.py`; política: `backend/domain/harpisense_engines/core.py`; composição: `backend/delivery/app.py` e `backend/native_server/runtime.py`. Commits introdutórios devem ser confirmados por responsável; o único SHA atestado aqui é a base acima.

Há apenas executor de simulação isolada: `simulation.py` não registra adaptador REAL e grava `SIMULATED`, `mitigation_confirmed=false`, uma vez por decisão. `Controls.change` recusa REAL, deriva execução de SIMULATION, não despacha ao trocar modo e recusa fila não confiável. `native/status` anuncia `containment=not_available`, `operational=false`; a API de composição anuncia executor não configurado. Não há executor operacional instalado comprovado.

Contrato exigido para aceite completo:

1. Estado inicial M1 + incidente/revisão fixados. Confirmar avaliação deve criar somente evento de avaliação, preservar M1, revisão dos controles e contagem de execuções; não autorizar defesa implicitamente.
2. Aprovação específica registra ator, horário, decisão, incidente/revisão, escopo, alvo, ação/fingerprint, validade e revisão de controle. Aprovação ausente, vencida ou de outra ação/revisão deve ser recusada e auditada.
3. Resultado é registro distinto da avaliação e da aprovação, ligado por IDs; não converter aceite da avaliação em aprovação ou `SIMULATED` em contenção confirmada.
4. Rodar o mesmo pedido simulado duas vezes: uma execução persistida, resposta idempotente, modo M1 preservado e nenhuma alteração em firewall, rotas, processos, serviços, ACL ou regras de contenção. Comparar snapshots antes/depois e logs de adaptadores; em fixtures não há adaptador real, mas isso não substitui medição no SO instalado.
5. Repetir após reinício apenas da VM identificada. Rejeitar replay de decisão antiga, revisão divergente, fila indisponível e emergência ativa.

Lacuna: não foi demonstrado fluxo integrado de confirmação de avaliação M1, aprovação específica e auditorias separadas no runtime instalado. Os 14 testes não cobrem esse fluxo completo. Solicitação de contrato/evidências enviada ao Edge Security, sem delegar execução real.

## Dependências e funcionalidades Docker versus nativo

| Componente | Observação na base | Inclusão/fechamento necessário |
|---|---|---|
| PostgreSQL + API delivery | `backend/delivery/compose.local.yml` compõe postgres:18.6 e API; ambos já têm caminho nativo | Usar cluster privado do instalador, migrações idempotentes e usuário sem superuser; nunca reutilizar senhas/volumes Compose |
| MQTT/observação | Nativo já tem Mosquitto TLS e consumidor automático | Preservar identidades/ACL, ordem DB/broker/API/consumer, heartbeat e prontidão; sem exigir Docker |
| Leitura XAI persistida | `build_native_app` monta `install_xai_api`; leitura existente não prova cálculo | Contrato de incidente + revisão exata e ausência explícita; autenticação e no-store |
| Cálculo SHAP Tree/Permutation e composição de detecção | Não integrados no runtime/requirements desta base; alterações locais de outra equipe não são entrega revisada | Backend Data deve fornecer commits, módulo produtor, pesos/modelos, schema e locks. Incluir SHAP/numpy/scipy/scikit-learn/pandas/numba/llvmlite e transitivas conforme resolução real por plataforma, sem inventar versões |
| Ficha unificada e produtor persistente | Não atestados no runtime congelado desta base | Empacotar módulos/SQL/catálogo e conectar produtor ao mesmo store; se worker necessário, serviço explícito com dependências/recuperação e estado protegido |
| Executor/coletores/defesa | Executor REAL ausente; Scapy em `edge/requirements.txt` não comprova captura instalada | Manter indisponível até contrato específico por SO. Linux pode exigir capacidades e captura; Windows requer driver/adaptador próprio. Não instalar privilégios/driver ou habilitar defesa por inferência |
| BitNet | Fora do aceite de geração | Não iniciar modelo/servidor nem baixar pesos; exigir flag e health de geração desabilitada |

Não há base para afirmar que SHAP seja intrinsecamente dependente de Docker: o bloqueio é composição e empacotamento não comprovados. Backend Data recebeu solicitação de locks, commits e serviços que só existem na composição Docker; resposta pendente.

Windows: runtime congelado deve conter DLLs/extensões nativas, módulos, dados e modelos validados por hash; atualizar lock com hashes e gate de imports no payload, sem usar Python do desenvolvedor. Ubuntu 24.04/Python 3.12: wheelhouse próprio compatível, hashes e dependências do SO declaradas; não reutilizar wheels Windows/Python 3.13. Rodar ambos os explainers no payload final, pois import bem-sucedido não comprova cálculo. Serviços existentes: Windows WinSW `HarpiSensePostgres/Api/Mqtt/Broker`; Ubuntu units `harpisense-postgres/api/mqtt/broker`. Novo worker só após definição do responsável e contrato de readiness.

## Máquinas de ensaio e disponibilidade

| Alvo identificado | Evidência de existência | Disponibilidade atual |
|---|---|---|
| Host Windows do usuário | Ambiente de desenvolvimento com ferramentas e laboratório | Excluído do aceite limpo; não instalar, reiniciar ou alterar serviços |
| VM Ubuntu 24.04 | `../native-installers/.native-test/clean-os/ubuntu2404/HarpiSense-Clean.vmx` e disco/logs | Existência confirmada; estado ligado, acesso, snapshot limpo e reserva de RAM não confirmados; instalação existente deve ser preservada |
| VM Windows 11 | `../native-installers/.native-test/clean-os/windows11/HarpiSense-Clean.vmx` e disco | Existência confirmada; boot, licença, acesso e limpeza não confirmados; README relata bloqueio histórico de RAM |

Antes de qualquer instalação, identificar VM UUID, SO/build, RAM disponível, snapshot descartável dedicado e ausência de Docker/WSL/VS Code. Não tratar arquivos VMX como prova de máquina pronta. Nenhum comando de boot/reboot ou instalação foi executado nesta preparação.

## Matriz de aceite — ambientes independentes

Legenda: P = pendente de execução neste ciclo; H = evidência histórica limitada; B = bloqueado por alvo/contrato. Nenhuma célula equivale a aprovação instalada.

| Critério e evidência mínima | Prévia 5174 | Ubuntu instalado | Windows instalado |
|---|---|---|---|
| Identidade: commit + hash artefato + VM/SO/snapshot | P: commit servido não atestado | B: alvo e candidata fixos | B: alvo e candidata fixos |
| Máquina limpa sem Docker/WSL/VS Code, inventário antes/depois | Não aplicável à prévia | B | B |
| Instalação por fluxo do produto sem preparação manual de serviços | Não aplicável | B | B |
| Reboot real, boot ID alterado, serviços automáticos sem comandos manuais | Não aplicável | B | B |
| Painel via atalho abre; bootstrap/admin, MFA e novo login após reboot | P | H apenas candidata antiga; B novo ciclo | H processos privados; B instalado |
| PostgreSQL + API + broker + consumidor prontos após reboot | Não comprova serviços | H versão histórica; B novo ciclo | B |
| Tree e Permutation realmente calculados no runtime instalado | P; screenshots isolados insuficientes | B payload/locks | B payload/locks |
| Ficha, gráfico e tabela: mesmo incidente/revisão/modelo/hash dos dados | H outro ensaio sintético; P na prévia | B | B |
| Trocar ID explicado para ID sem explicação, sem gráfico residual/latest fallback | H outro ensaio; P na prévia | B | B |
| BitNet off, geração desabilitada e ausência de processo de modelo | P | B | B |
| Confirmar avaliação M1 mantém M1 e não executa defesa | B contrato integrado | B | B |
| Aprovação específica + resultado em registros auditáveis separados | B contrato integrado | B | B |
| Repetir simulado: idempotência e zero contenção real observada | H 14 testes fixtures; P UI | B | B |

Cada evidência deve conter ambiente, horário UTC, commit, hash instalador/runtime, IDs e revisões, ação humana e resultado observado. Guardar respostas HTTP sanitizadas, consulta SQL só de leitura e screenshots correspondentes; nunca publicar senha, grant, DSN ou TOTP. Coletor do laboratório pode obter boot ID e serviços automaticamente; operador não deve precisar iniciar serviços ou executar comandos para o painel funcionar.

## Sequência concreta e responsáveis

1. Backend Data fecha SHAP/locks/contratos de registro e serviços; Edge Security fecha avaliação/aprovação/resultado, executor e limites por SO. Selecionar commits em nova integração revisável sem tocar a base protegida.
2. Validar composição nativa em portas descartáveis, imports do pacote e cálculo dos dois explainers. Executar M1 e repetição simulada, verificando auditorias e ausência de efeitos reais; falha bloqueia próxima etapa.
3. Responsável do laboratório confirma máquinas/snapshots limpos e recursos. Fixar hash candidato; gerar instalador somente para ensaio funcional do runtime completo.
4. Instalar e reiniciar exclusivamente a VM identificada. Abrir painel pelo atalho, login admin/MFA e prontidão automática; coletar matriz Ubuntu e Windows separadamente.
5. Enviar evidências ao Arquiteto com falhas e bloqueios. Aprovação só para versão/ambiente/critério realmente executados; prévia e processo privado não homologam instalação.

## Entrega Maestri

`maestri ask "HarpiSense Arquiteto"` foi tentado com plano, branch e caminhos de evidência, mas retornou `No connection`. `maestri debug` confirmou transporte saudável; `maestri list` identifica o terminal atual como o próprio HarpiSense Arquiteto, sem conexão para esse nome. Portanto o envio ao destinatário solicitado não foi concluído. Backend Data recebeu o levantamento; a tela retornada mostra integração própria de controles em andamento e não constitui resposta sobre SHAP. A solicitação ao Edge Security retornou a tela deste trabalho; não há resposta independente do executor atestada. Não contornar identidade do terminal ou declarar coordenação concluída.
