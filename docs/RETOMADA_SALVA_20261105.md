# Checkpoint salvo em 05/11/2026

## Entregas preservadas

- Composição: branch/worktree `feat/detection-composition` /
  `harpisense-worktrees/detection-composition`; commits `7fe8294` e `4c30d59`
  publicados. Composição RF/IF → Risk/Policy → PostgreSQL/P11 validada com
  estimadores reais treinados sobre dados sintéticos explicitamente identificados.
  Depois, auditor de compatibilidade P08 entregue com oito testes específicos,
  sem repetir treino/inferência. Evidências, comandos e dependências permanecem
  nos documentos de composição/compatibilidade e em `docs/evidence/`.
- Backend MFA: `feat/admin-bootstrap-mfa`, `737ae26`, worktree limpa e alinhada ao
  tracking local. Contrato candidato/OpenAPI revisado; não implantado na VM.
- Frontend: `feat/frontend-auth-defense-v2`, `79c5fe6`, worktree limpa e alinhada ao
  tracking local. Alterações posteriores à revisão `d172a387` ainda precisam de
  revisão coordenada; não assumir validação pelo integrador.
- Gerenciador: `feat/installer-orchestration`, `b42eb4e`, worktree limpa e alinhada
  ao tracking local. Responsável por instalação, configuração posterior e catálogo.
- Edge: `feat/p08-evidence-coverage`, `a59a8c0`, worktree limpa. Preservar sua entrega
  posterior a `d6a2380`, sem substituir captura pela versão da composição.
- Firmware/ensaio: `feat/poste1-ldr-firmware` em `49d2eac` e
  `feat/poste1-ensaio-wokwi` em `69cd62d`, ambas as worktrees limpas e alinhadas ao
  tracking local consultado.

Nenhum arquivo, agente, branch ou worktree foi excluído ou reorganizado.
Os projetos/artefatos locais não versionados da raiz foram preservados em disco;
não foram adicionados indiscriminadamente ao Git nem publicados. Bundles e CSVs
sintéticos permanecem no diretório local ignorado indicado pela composição.

## Auditoria Wokwi — resultado disponível

`maestri list` identifica **Poste 1 Wokwi como portal de navegador**, conectado ao
agente **Gerenciador de configurações**. Não há agente separado chamado Wokwi na
listagem consultada. Portal não possui cwd, branch ou worktree próprios.

O Gerenciador confirmou cwd real `D:\Projetos\tcc - harpisense`, branch `main`,
e trabalho isolado em `harpisense-worktrees/installer-orchestration`, branch
`feat/installer-orchestration`, `b42eb4e`, limpa. Declarou não ter assumido/delegado
firmware, alterado arquivos de firmware/Wokwi, iniciado build ou publicação MQTT.
O histórico dessa branch após `9d35906` não mostrou alterações em `iot/`.

Inspeção direta do portal: `https://wokwi.com/projects/new/esp32`, título
New ESP32 Project, sketch padrão e botão **Start the simulation**. Nenhuma
simulação estava rodando nesse portal; não foi iniciada pelo integrador. A busca
local pelos nomes de processos PlatformIO/Wokwi/QEMU/ESPTool consultados não
retornou processo correspondente; essa busca é delimitada, não um inventário
universal de toda execução possível.

O ensaio versionado em `69cd62d` usa `platformio.ini`: ambiente `wokwi` estende
`esp32dev`, mesmas fontes e bibliotecas, com configuração local de simulação.
`scripts/prepare-web.ps1` exporta o firmware.bin existente e verifica seu hash
contra o manifesto, sem gerar outra implementação. O commit `69cd62d` alterou
documentação, evidências, circuito e preparação do ensaio, não criou firmware
paralelo pelo Gerenciador. Não há tarefa incorreta dele identificada que precise
ser pausada; nenhum recurso foi removido ou reconectado.

Há divergência da identidade apresentada pelo CLI: terminais consultados se
identificam como HarpiSense Arquiteto apesar de suas funções de conversa. Isso
limita a atribuição por nome; não foi corrigido por renomeação/reorganização.
O terminal IoT consultado também atingiu limite de uso, portanto não há nova
confirmação independente dele sobre execução global. O caminho
`D:\Projetos\tcc - harpisense\HarpiSense_MQTT` foi indicado no seu terminal como
projeto físico e existe com `src/`, `include/` e `platformio.ini` ESP32/Arduino;
nenhuma alteração ou migração desse projeto foi feita por esta auditoria.

Responsabilidade vigente: **IoT/MQTT mantém o firmware ESP32-WROOM-32 em C++,
VS Code/PlatformIO; Wokwi apenas simula as mesmas fontes.** Gerenciador mantém
instalador, configuração e catálogo, sem assumir manutenção do firmware.

## Retomada do núcleo

Continua pendente o recibo do console Poste2 para confirmar sensor ens33,
ferramenta/permissões/link type e relógio; falta também fechar sincronismo temporal,
logs/cursores assinados de broker/consumidor/API e bundles operacionais confiáveis.
A proposta de observação no endpoint não exige mudança de rede e não habilita
contenção pelo gateway. Não houve nova coleta, ataque, sincronização de relógio,
migração ou implantação nesta continuação.

Próximo trabalho: receber o recibo, revisar a entrega Edge `a59a8c0`, fechar fontes
e perfil real assinado, coordenar a janela legítima e executar o auditor offline
antes de propor avanço. Não contornar gates nem usar o ensaio sintético como
aceite de laboratório. Não implantar MFA antes de transição/recuperação no alvo.
