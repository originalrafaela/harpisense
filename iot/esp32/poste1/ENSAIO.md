# Ensaio reproduzível do Poste 1

Base: feat/poste1-ldr-firmware, 49d2eac. A lógica em src/ e lib/PosteCore/ é a mesma para placa e Wokwi. Nenhum firmware alternativo foi criado. O ambiente wokwi apenas injeta configuração de circuito, inverte a orientação do ADC e mantém todos os gates de publicação fechados. Nunca gravar o ambiente wokwi em hardware.

## Referências e precedência

Consultados em referencias/versão_v2: pacote 05 (CONFIGURACAO_HARDWARE.md e perfil PlatformIO), pacote 06 (README e contrato candidate.v2). O pacote 05 ainda descreve uma proposta de payload anterior: usar a decisão de contrato já incorporada em 49d2eac, não substituir src/main.cpp pelo pacote 05. A base consolidada e os demais componentes em referencias/Versões corretas continuam válidos onde não há atualização; ausência na v2 não significa componente ausente. Este ensaio não substitui backend, consumidor ou infraestrutura.

## Placa e montagem

Perfil herdado: espressif32@6.9.0, board=esp32dev, Arduino-ESP32 2.0.17, PubSubClient 2.8, serial 115200. Perfil genérico: ESP32 clássico, flash de referência 4 MB. ESP32-WROOM-32 identifica o módulo, não a placa de desenvolvimento. Antes de gravar: registrar foto frente/verso, fabricante/modelo/revisão, serigrafia dos pinos 3V3/GND/34/25, chip USB-UART (CP210x/CH340/outro), VID/PID e COM, capacidade de flash e botões BOOT/EN. Confirmar correspondência com o esquema do fabricante. Não inferir posição de pino pela imagem do Wokwi.

Montar com USB e qualquer fonte desconectados, sobre a separação central da protoboard. Conferir se os trilhos são interrompidos e unir GNDs. Usar USB para alimentar a placa e a saída regulada 3V3 para o divisor. Não conectar USB e outra fonte simultaneamente neste ensaio.

```text
DIVISOR FÍSICO (LDR sem polaridade)
ESP32 3V3 ─── LDR ───●──── resistor 10 kΩ ─── GND
                     │
                     └──── GPIO34 (ADC1, apenas entrada)

LED EXTERNO (ativo alto)
GPIO25 ─── resistor 330 Ω ─── A  LED  C ─── GND
                             +       -
                    perna longa     perna curta / face chata
```

O nó ● liga apenas a junção do divisor ao GPIO34. O resistor de 10 kΩ é externo: GPIO34 não tem pull-up/pull-down interno. Identificar polaridade pelo datasheet/teste de diodo caso as pernas tenham sido cortadas. Não usar LED integrado como evidência do LED externo. Para LED vermelho com Vf aproximada de 2 V, 330 Ω dá cerca de (3,3−2)/330 = 4 mA; conferir Vf e corrente nominal do LED real. Resistores de 1/4 W são suficientes para essa bancada.

Usar somente 0..3,3 V no divisor e nos GPIOs. Não ligar GPIO34, LED ou LDR ao VIN/5V/USB 5V. O limite absoluto não é tensão operacional; atenuação ADC_11db não torna o pino tolerante a 5 V nem garante leitura linear até o trilho. Medir 3V3 e o nó com multímetro antes de ligar o sinal ao ADC. ADC saturado não comprova sensor desconectado. Fonte, tolerância, luz ambiente e ADC precisam de caracterização real.

No divisor físico, escuro aumenta R_LDR e reduz V_ADC: V_ADC=3,3×10000/(R_LDR+10000). Usar HS_ADC_DARK_IS_LOW=true. Posicionar o LDR sem receber diretamente a luz do LED para evitar realimentação.

## Simulação local Wokwi

Abrir esta pasta no VS Code com extensão Wokwi e PlatformIO disponíveis. Compilar `pio run -e wokwi`; iniciar `Wokwi: Start Simulator`. wokwi.toml aponta para o binário/ELF desse ambiente. Não exige acesso ao broker. A extensão pode exigir ativação/licença do usuário. Wokwi não compila o firmware.

O diagram.json usa módulo wokwi-photoresistor-sensor: já contém divisor de 10 kΩ, AO em GPIO34, VCC em 3V3, GND comum; DO fica desconectado. Não adicionar outro resistor de divisor na saída AO. Esse módulo sobe AO no escuro, ao contrário do circuito físico acima. simulation/config.h usa HS_ADC_DARK_IS_LOW=false, limiares numéricos 1200 e 2800; nesta orientação liga em ADC >=2800 e desliga em <=1200. Entre eles mantém estado. São valores sintéticos, não calibração física nem medição de lux.

Variar lux no componente de 0,1 até 100000 e voltar, em passos, esperando pelo menos 2 s por passo. Registrar ADC observado, comando e imagem do LED. Esperar LED ligado no escuro e desligado no claro, com retenção dentro da banda. Se o modelo não alcançar um limiar, registrar os ADCs e ajustar somente simulation/config.h; nunca copiar esses valores para a placa. Estado inicial desligado. Esperar `network_closed: configuration/acceptance gates`, `utc_valid=0` e contador no_utc crescente: isso é aprovação do isolamento, não falha de integração.

Sem publicação, o payload PHYSICAL do firmware não é emitido como se fosse evidência real. Não usar Wi-Fi aberto Wokwi-GUEST para contornar o requisito atual de senha não vazia. Não expor broker, desativar TLS ou usar identidade do Poste 2. Wi-Fi/NTP/TLS/MQTT reais são ensaio separado em placa na rede autorizada.

## Preparação e comandos (PowerShell, nesta pasta)

Instalar dependências locais, caso ainda não existam:

```powershell
py -3.12 -m venv .tools/venv
& .tools/venv/Scripts/python.exe -m pip install -r requirements-dev.txt
$env:PLATFORMIO_CORE_DIR = Join-Path $PWD '.tools/pio'
& .tools/venv/Scripts/python.exe -m platformio device list
& .tools/venv/Scripts/python.exe -m platformio run -e esp32dev
& .tools/venv/Scripts/python.exe -m platformio run -e wokwi
```

Para placa, copiar include/config.example.h para include/config_local.h (ignorado). O exemplo preserva GPIO34/25, polaridade física, rede vazia, limiares -1 e gates fechados. Após conferir montagem, escolher limiares exploratórios ordenados dentro de 0..4095 e marcar somente HS_HARDWARE_CONFIRMED=true para ensaio offline. Registrar que esses limiares são provisórios. Obter séries de 30 amostras em claro/escuro, registrar dispersão, selecionar limiares separados sem oscilação e recompilar. Não converter ADC cru em lux sem calibração.

Para integrar, preencher localmente SSID/senha próprios, NTP acessível, hostname DNS coberto pelo SAN do certificado, CA confiável e usuário/senha exclusivos do Poste 1. Só marcar os gates HS_CONTRACT_CONFIRMED, HS_IDENTITY_ACL_VALIDATED, HS_TLS_VALIDATED e HS_ALLOW_PUBLISH após registrar as validações correspondentes. O firmware só inicia Wi-Fi/NTP quando todos os gates e campos de rede estão válidos; ausência de Wi-Fi com gates fechados é esperada. Não colocar segredos no Git ou logs.

Apenas depois da confirmação explícita do usuário de placa conectada e pronta, executar (substituir COMx pela porta identificada):

```powershell
& .tools/venv/Scripts/python.exe -m platformio run -e esp32dev -t upload --upload-port COMx
& .tools/venv/Scripts/python.exe -m platformio device monitor --port COMx --baud 115200
```

Não executar upload como parte do build. Fechar monitor antes de gravar; BOOT/EN somente conforme procedimento da placa. Não gravar outra placa que compartilhe a máquina.

## Evidências e aprovação por etapa

Guardar data, operador, revisão Git, ambiente, configuração sem segredos, hashes SHA256 do binário/ELF, identificação da placa e resultado por linha. Usar APROVADO / REPROVADO / NÃO EXECUTADO, com link do log/foto/captura e justificativa. Etapa posterior não aprova automaticamente a anterior.

| Etapa | Ação e evidência esperada | Critério de aprovação |
| --- | --- | --- |
| USB | Comparar `platformio device list` antes/depois da conexão autorizada; guardar COM/VID/PID e descrição | Porta inequívoca, cabo de dados e driver reconhecidos; não confundir outra placa |
| Montagem | Foto e medições de 3V3/nó/GND, valores e polaridade | Ligações iguais ao diagrama, sem curto, nó dentro de 0..3,3 V |
| Compilação | Log `run -e esp32dev` e `run -e wokwi`, versões e SHA256 | SUCCESS nos dois; origens src/ e lib/ únicas; hardware sem configuração de simulação |
| Gravação | Registrar confirmação do usuário, COM e saída do upload | Escrita/verificação concluídas no dispositivo identificado; pendente até autorização |
| Serial | Monitor 115200 por pelo menos 30 s | Linhas a cada ~1 s, sem reset contínuo; hardware_closed indica configuração incompleta, não ensaio aprovado |
| LDR | 30 amostras em cada condição claro/escuro, voltímetro e posição da luz | ADC varia no sentido esperado; faixa/dispersão permitem histerese; extremos não usados como diagnóstico de desconexão |
| LED | Repetir claro→escuro→claro 3 vezes, registrar led_commanded e foto/vídeo | Comando acompanha limiares e mantém estado na banda; observação independente comprova acendimento físico. Comando sozinho não comprova iluminação |
| Wokwi | Captura do circuito, ADCs e serial nas duas direções | Polaridade simulada correta, LED virtual responde, rede fechada; não aprova montagem/calibração física |
| Wi-Fi real | Após gates validados, observar associação no AP autorizado ou diagnóstico de bancada | Dispositivo associado e rede alcançável. O firmware não imprime sucesso de associação; serial sozinho é insuficiente |
| Relógio | NTP autorizado e serial `utc_valid=1`; comparar observed_at recebido com UTC de referência | Sincronização recebida e tempo plausível; antes disso nenhuma amostra publicável. Após >1 h sem nova sincronização, utc_valid deve voltar a 0 |
| TLS | Registrar validação prévia com cliente autorizado, CA/hostname corretos e negativos de CA errada/hostname divergente; repetir com placa em configurações locais separadas | Correto conecta; negativos não publicam nem têm fallback inseguro. Teste de cliente externo sozinho não aprova handshake da placa |
| MQTT | Observação autorizada no broker/assinante existente, sem alterar configuração | Client ID poste-1, tópico/identidade/schema exatos; ACL específica. Credenciais Poste 2 proibidas |
| Publicação | Capturar payload recebido, hora e ID; correlacionar com amostra | QoS 0, retain=false, ID por boot+sequência estável ao reenviar a mesma entrada; mudança de ID apenas para nova amostra/boot. Recepção independente necessária: accepted_local não é ACK |
| Reconexão | Interromper apenas o Wi-Fi/alimentação do dispositivo de teste ou seu acesso local, restaurar, manter serial/assinante | Coleta/LED continuam offline, reconecta com backoff até 60 s; fila limitada e validade 120 s; perdas/expiração registradas. Reboot perde RAM e troca boot ID; não prometer replay/durabilidade |

Para observar o contrato usar somente acesso de leitura já autorizado, sem alterar broker, consumidor ou VM. Para negativos TLS, recriar configuração local e recompilar/gravar somente durante sessão autorizada de bancada. Não encerrar broker compartilhado. A ausência de telemetria é evidência negativa somente quando a janela de observação e o assinante estão comprovadamente ativos.

Contrato preservado: tópico `harpisense/v1/telemetry/harpisense.poste.poste-1/ldr`, device_id `harpisense.poste.poste-1`, schema `harpisense.telemetry.candidate.v2`, client ID `poste-1`, TLS com validação, QoS 0 e retain=false. QoS 0 é melhor esforço, sem garantia de entrega; retorno publish/accepted_local mede apenas aceitação local.

## Fontes técnicas

- [Perfil esp32dev](https://docs.platformio.org/en/stable/boards/espressif32/esp32dev.html).
- [ESP32: restrições de GPIO e projeto](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32/schematic-checklist.html): GPIO34 somente entrada, sem pulls internos.
- [Datasheet ESP32](https://documentation.espressif.com/esp32_datasheet_en.html): conferir limites do chip e datasheet específico da placa.
- [Módulo LDR Wokwi](https://docs.wokwi.com/parts/wokwi-photoresistor-sensor): divisor interno e resposta AO.
- [Wokwi com PlatformIO](https://docs.wokwi.com/vscode/platformio): configuração de binário e alvo. A imagem de aplicação usa bootloader/partições padrão do simulador; não comprova o bootloader físico.

Diagrama para abrir/imprimir: [montagem física](simulation/montagem-fisica.svg). O desenho físico é distinto do módulo LDR do diagram.json, conforme a diferença documentada acima.
