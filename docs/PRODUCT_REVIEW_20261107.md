# Composição para revisão — 7 de novembro de 2026

Base: `feat/native-installers`, após `c5483cd`. Esta composição não altera as
releases anteriores nem atualiza a VM do usuário. A candidata publicada continua
`native-installers-20261106-candidate.5`; a instalação conhecida permanece na
candidata 4. O aceite histórico Ubuntu da candidata 3 e o ensaio Windows limpo
pendente permanecem separados. Este commit ainda não é uma candidata empacotada
ou homologada em sistema limpo.

## XAI integrado

Incorporados somente o pacote leitor `backend/xai_api` e os dois documentos XAI
do commit Backend `48bb43aa2e86b5de433759a6698972dde7534a6f`. Não foi aplicado o
commit inteiro nem substituídos autenticação, recuperação, ativos ou controles.
O adaptador identifica ativos por `device_id`; a leitura de nome foi ajustada
para o campo `name` do cadastro nativo já integrado. Nenhuma migração XAI nova.
O runtime instala o leitor após a autenticação existente. Os builders Ubuntu e
Windows e o gate de importação foram preparados para incluí-lo, ainda sem novo
build de distribuição nesta rodada.

`ModelAnalysis` foi copiado da worktree `feat/product-visual-refinement`, sem
editar essa worktree. SHA-256 dos arquivos sincronizados:

- `model-analysis-data.ts`: `75356aee84aa2fca0b0a916cb392334ebf0dcf04cd804143c1e969ece292ff7e`
- `model-analysis.tsx`: `814f23a751812d0521f2b41d6331c5ba78d58cbbe250d3d1017d34f256c733d6`

No componente, removido apenas um espaço ao fim de linha em relação à origem
`b22ad9c8141e64535fc3918b86fd456dd53e73f7805d587b836e7f9d3898442f`.

Montado em `#ai`, separado de HarpIA. Cliente autenticado existente, GET de
`/api/v1/p11/incidents/{id}/explanations?incident_revision={revision}` via
`/p11-api`. O proxy de desenvolvimento libera somente esse GET com a query
estrita. Dashboard oferece “Ver explicação do modelo” junto ao incidente,
mesmo sem texto HarpIA. A seleção fica no componente raiz e persiste no retorno
entre dashboard, detalhes e análise.

`check_model_mount.py` agora testa a aba real: bootstrap e TOTP no Chromium,
HTTP nativo e PostgreSQL isolados. As 12 verificações passaram: sessão exigida,
envelope autenticado/no-store, revisão inexistente recusada, nomes do cadastro,
RF e IF renderizados, ausência explícita e seleção preservada. O ensaio inicial
de cinco verificações cobria apenas navegação/indisponibilidade e foi preservado
em `navigation-only-result.json`; ele não comprovava explicações reais.

Registros canônicos são uma cópia byte a byte da fixture local publicada pelo
Backend, SHA-256 `4aeda134461f1d2a3a1d0f988bcd9cfd6e79cc80ff2e0c6358fc48bd2be90ee1`.
Entradas são sintéticas, com explicações previamente geradas pelo Backend; não
houve treinamento/inferência nesta aceitação do leitor e não há aceite
estatístico ou de tráfego físico. A primeira conversão PowerShell dos registros
alterou sua representação e foi rejeitada pelo contrato; o teste final usa os
bytes originais. A outra falha preservada foi um seletor de mensagem que não
considerava o ícone de acessibilidade; a tela já mostrava ausência corretamente.

[Resultado e capturas](evidence/model-mount-review/result.json).
[Aba montada](evidence/model-mount-review/model-integrated.png).
Os processos exclusivos do ensaio foram encerrados. Não foi usado nem declarado
conectado o listener Ubuntu 18089. A geração operacional de XAI, referências e
artefatos confiáveis continua dependente da composição produtora; a consulta
não fabrica explicações quando não existem registros válidos.

## Backup em nuvem — planejamento opcional

A seção permanente do Gerenciador atende primeiro uso e alterações posteriores.
O assistente e a navegação de backup apontam para essa mesma seção. “Configurar
depois” não impede o restante da configuração. O rascunho reutiliza a persistência
de progresso existente, sem cadastro ou assistente paralelo.

Catálogo: Amazon S3, Azure Blob Storage, Google Cloud Storage e API S3 compatível,
todos planejados, sem conector implementado/testado. Campos neutros de provedor,
destino lógico, inclusão, periodicidade e retenção. Nenhuma conta, credencial,
SDK, envio, agendamento operacional ou recurso pago. Conectar, executar e
restaurar permanecem desabilitados. O estado distingue “não configurado” e
“Rascunho salvo”; execução/restauração não possuem evidência. Exportação de logs
é explicitamente distinta de backup para restauração.

75 verificações da aceitação fonte passaram com HTTP/PostgreSQL/MQTT reais,
incluindo salvar/ler rascunho, retorno após login/reinício dos processos e revisão
desktop/mobile. Esses reinícios não equivalem a reiniciar uma VM instalada.
Três testes do contrato de nuvem passaram. Build e 60 testes frontend passaram
após a sincronização final XAI.

[Resultado](evidence/cloud-backup-review/product-native-result.json),
[desktop](evidence/cloud-backup-review/cloud-desktop.png),
[mobile](evidence/cloud-backup-review/cloud-mobile.png).

## Encaminhamento e limites

Maestri permaneceu indisponível pelo pipe anteriormente registrado. Este documento
é o encaminhamento para repasse manual ao Frontend, Backend e Gerenciador; não
representa confirmação de recebimento deles. Não foram editadas suas worktrees.
O contrato leitor foi aceito para esta composição de fonte; a aprovação do
pacote instalável continua pendente. Nenhuma contenção real foi habilitada.
Preservados dados, snapshots, ensaios e evidências anteriores. Uma próxima
candidata precisa de versão/checksums próprios e nova regressão do pacote.
