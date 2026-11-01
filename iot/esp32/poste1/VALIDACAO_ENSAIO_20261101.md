# Registro desta entrega — 01/11/2026

Branch feat/poste1-ensaio-wokwi, base exata 49d2eac. Nenhuma alteração em src/, include/ ou lib/PosteCore/; fontes de leitura, histerese, identidade, fila e comunicação preservadas. Perfil wokwi herda o perfil esp32dev e somente injeta simulation/config.h, sem credenciais e com publicação fechada. Configuração física de exemplo continua em include/config.example.h.

## Executado

- Revisão de P05 v2 (hardware/perfil), P06 v2 (contrato) e inventário dos pacotes anteriores em Versões corretas. Não foi declarada ausência de componente por não constar na v2.
- Compilação nativa do mesmo poste_core.cpp com Zig 0.13.0 e execução: PASS: 7 core test groups (includes 128 gate combinations). Avisos da libunwind ao gerar cache da ferramenta; sem falha da suíte.
- Validação dos sete payloads do executável C++ contra P06 v2: PASS: 7 firmware-generated payloads accepted by P06 and local physical-profile assertions. Usado Python do venv de contrato preexistente, sem modificar dependências.
- `git diff --check`: passou. JSON do projeto verificado por parser; fontes src/lib sem diferença contra base.

## Compilação ESP32 tentada, não concluída nesta rodada

Comando: PlatformIO 6.1.18 `run -d <pasta deste projeto> -e esp32dev -e wokwi` usando core preexistente em poste1-firmware/.tools/pio. Dependência PubSubClient 2.8.0 baixada. Foram resolvidos espressif32 6.9.0, Arduino-ESP32 2.0.17, xtensa-esp32 8.4.0+2021r2-patch5, alvo 240 MHz / 4 MB.

Ambos falharam ao iniciar o compilador: `xtensa-esp32-elf-g++: error: CreateProcess: No such file or directory`. Repetir com PATH explícito e GCC_EXEC_PREFIX não resolveu. Não se concluiu a causa ambiental. Não alterada a instalação de ferramentas da entrega anterior. Não há binário/ELF aprovado nem hash de nova compilação ESP32 nesta rodada. O sucesso registrado em VALIDACAO_20261031.md pertence à rodada anterior, não à configuração Wokwi.

Próxima verificação: instalar o requirements-dev.txt num venv/core PlatformIO local novo conforme ENSAIO.md e repetir os dois builds; preservar os logs. Os artefatos Wokwi apontados por wokwi.toml só estarão disponíveis depois do build bem-sucedido.

## Preparado, não executado

- Wokwi: diagram.json, wokwi.toml e configuração isolada preparados. Wokwi CLI não disponível; execução virtual/serial/LED não observada. A conferência estática não aprova a simulação.
- USB, identificação física, montagem, medição elétrica, calibração, gravação e monitor serial reais: não executados. Nenhum upload foi feito. Gravação depende da confirmação do usuário de placa conectada e pronta.
- Wi-Fi, sincronização NTP, TLS positivo/negativo, ACL, publicação e reconexão reais: não executados; critérios em ENSAIO.md. Nenhum acesso/alteração de broker, consumidor ou VMs. Poste 2 não foi usado.

Não há garantia de entrega QoS 0 nem comprovação física de luz a partir do comando do LED. Entrega documental e preparação de ensaio; aprovação funcional depende das etapas pendentes acima.
