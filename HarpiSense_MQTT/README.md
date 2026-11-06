# Poste 1 — projeto local de trabalho

Abra **esta pasta HarpiSense_MQTT** no VS Code. Instale PlatformIO IDE e,
somente para simular, Wokwi Simulator (`Wokwi.wokwi-vscode`).

Procedimento único, no terminal PowerShell desta pasta:

```powershell
./scripts/build.ps1 -CoreDir '../.p1-build' -Python "$env:USERPROFILE/.platformio/penv/Scripts/python.exe"
```

O comando compila `esp32dev` e `wokwi`, sem upload. Requer o Python do
PlatformIO IDE (Core 6.2.0 nesta validação); a primeira execução pode baixar
dependências. A plataforma está fixada em espressif32 6.9.0 e PubSubClient 2.8.
Logs ficam em `test-results/`. Para compilar sem qualquer simulador instalado,
acrescente `-Environment esp32dev`. O instalador não deve depender de Wokwi,
licença, token ou aba de navegador.

Após ambos os builds terminarem com SUCCESS, execute **F1 → Wokwi: Start
Simulator**. Ative a licença da extensão se solicitada. `wokwi.toml` seleciona
exclusivamente `.pio/build/wokwi/firmware.bin` e `.elf`, com `diagram.json`
desta pasta. Confirme `network_closed: configuration/acceptance gates` no serial.
Não use Upload nem Flash. Não use o binário `esp32dev` na simulação.

LDR AO em GPIO34, LED externo ativo alto em GPIO25, resistor de 330 ohms.
O sensor virtual tem ADC crescente no escuro; limiares 1200/2800 são apenas
virtuais. MQTT/Wi-Fi ficam fechados pelos gates do perfil. Não crie
`include/config_local.h` para simular: o build rejeita essa mistura.

O ensaio de histerese registrado em `69cd62d`,
`iot/esp32/poste1/VALIDACAO_SIMULACAO_20261102.md`, continua sendo a evidência
de execução. Os fontes, configuração e diagrama usados aqui são idênticos
àquela entrega. Esta rodada verifica integração/build local; não representa
novo ensaio Wokwi nem homologação física. A aba aberta no Maestri não é fonte.

## Comparação antes da incorporação

A pasta estava não rastreada e continha somente o template Arduino
`myFunction(2, 3)` e PlatformIO sem versões fixadas. Não havia `diagram.json`,
`wokwi.toml` ou perfil de simulação. Os bytes originais dos dois arquivos
substituídos estão preservados em `LOCAL_ORIGINAL.json` (base64). As demais
configurações locais, inclusive `.vscode`, foram preservadas.

`49d2eac` fornece fontes, núcleo, identidade Poste 1 e gates de TLS/ACL.
Entre essa entrega e `69cd62d`, `src/`, `include/` e `lib/` não mudaram.
`eafcd7e` acrescenta circuito/perfil Wokwi/teste de circuito; `fdfd27e`
normaliza o diagrama; `d746d43` fixa plataforma e adapta o build Windows;
`69cd62d` registra a execução web e o pacote reproduzível.
`PROVENIENCIA.json` relaciona os arquivos incorporados e hashes SHA256.
Não foi criada outra árvore de projeto ou worktree.

## Contrato e limites

Identidade `harpisense.poste.poste-1`, client ID `poste-1`, tópico
`harpisense/v1/telemetry/harpisense.poste.poste-1/ldr`, schema
`harpisense.telemetry.candidate.v2`. Medições: `ldr_adc_raw` e
`led_commanded_on`; ADC bruto não é lux calibrado nem LED confirmado fisicamente.
O serializador mantém `origin_type=PHYSICAL`; por isso o perfil virtual nunca
publica. Sem UTC confiável, não produz amostras publicáveis.

Permanecem pendentes: montagem/calibração e polaridade reais no ESP32-WROOM-32,
ensaio físico, CA/hostname/SAN e relógio para TLS, credencial própria do Poste 1
e ACL por tópico. QoS 0 indica aceitação local, não ACK de persistência.
Nenhuma identidade Poste 2, broker, VM ou gravação USB integra esta rodada.
