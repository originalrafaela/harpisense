# Executar o ensaio de circuito

Este projeto usa as fontes originais do firmware. GPIO34 recebe AO do módulo
LDR e GPIO25 comanda o LED externo. O módulo virtual tem divisor interno e
resposta inversa à montagem física proposta. Não copiar os limiares virtuais
1200/2800 para a placa. Não executar upload.

## Compilar no Windows

Na pasta `iot/esp32/poste1` desta branch, criar o Python local se necessário:

```powershell
py -3.12 -m venv .tools/venv
& .tools/venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

Escolher um diretório curto, exclusivo desta entrega para o core PlatformIO.
Não apontar para outra instalação ativa nem reutilizar o core de outra worktree.
O script cria o diretório se necessário; PlatformIO instala as versões fixadas
caso estejam ausentes. Exemplo nesta máquina:

```powershell
./scripts/build.ps1 -CoreDir 'D:/Projetos/tcc - harpisense/.p1-build'
```

Também se pode passar `-Python <caminho absoluto do python.exe>` para usar um
Python existente sem instalar ou alterar seus pacotes. É necessário PlatformIO
6.1.18 nesse Python. O script restaura as variáveis de ambiente, nunca grava
placa, e guarda logs em `test-results/build-esp32dev.log` e `build-wokwi.log`.
Não deve existir `include/config_local.h` ao compilar Wokwi: a configuração
virtual bloqueia essa mistura deliberadamente.

## Opção A: Wokwi no VS Code (interação do usuário)

1. Abrir **esta pasta** `iot/esp32/poste1` no VS Code.
2. Instalar a extensão **Wokwi Simulator**, ID `Wokwi.wokwi-vscode`.
3. Executar **F1 → Wokwi: Request a New License** e completar a ativação no
   navegador se solicitada. Não enviar tokens/licenças ao Git ou ao chat.
4. Compilar com o comando acima; confirmar SUCCESS nos dois ambientes.
5. Executar **F1 → Wokwi: Start Simulator**. O `wokwi.toml` carrega
   `.pio/build/wokwi/firmware.bin` e `firmware.elf`.
6. Confirmar no serial `network_closed: configuration/acceptance gates`.
   `utc_valid=0` é esperado, pois a rede está fechada.
7. Clicar no módulo LDR e variar `lux`: **100000 → 0.1 → 100000**,
   aguardando pelo menos 3 segundos em cada condição.
8. Salvar o serial completo e capturas do circuito nas três condições.
   Confirmar ADC alto no escuro, baixo no claro, `led_commanded=0 → 1 → 0`
   e LED virtual correspondente. ADC cru não é medição calibrada de lux.

Arquivos necessários: `diagram.json`, `wokwi.toml`, os dois artefatos do ambiente
`wokwi` e as fontes/configuração deste projeto para reproduzir o build. Não
carregar o binário `esp32dev` no simulador: seus gates físicos ficam fechados.

## Opção B: Wokwi CLI (requer token do usuário)

A CLI **v0.29.1** foi instalada localmente nesta rodada. Em outra máquina,
baixar [o executável Windows da mesma versão](https://github.com/wokwi/wokwi-cli/releases/download/v0.29.1/wokwi-cli-win-x64.exe)
e salvá-lo em `.tools/wokwi/` como `wokwi-cli.exe`, preservando instalações
globais. Criar o token no [Wokwi CI Dashboard](https://wokwi.com/dashboard/ci).
Definir `WOKWI_CLI_TOKEN` somente na sessão local, sem imprimi-lo ou registrá-lo.

Depois do build, nesta pasta:

```powershell
& .tools/wokwi/wokwi-cli.exe lint .
if ($LASTEXITCODE -ne 0) { throw 'Diagrama inválido; verificar lint' }
& .tools/wokwi/wokwi-cli.exe . --scenario simulation/circuit.yaml --timeout 30000 --serial-log-file test-results/wokwi-serial.log
if ($LASTEXITCODE -ne 0) { throw 'Simulação não aprovada; verificar erro e log' }
```

O cenário usa a API documentada `set-control` para lux e `expect-pin` para
GPIO25, verificando claro→escuro→claro e comando serial com UTC inválido. Exige
saída 0; timeout, falha de autenticação ou cenário não concluído não são sucesso.
Guardar também versão da CLI, saída do processo e hashes do binário/ELF.
Se um limiar não for alcançado pelo modelo, registrar o ADC e o resultado real
antes de alterar exclusivamente os valores de simulação.

Nenhum dos modos exige broker. A configuração injeta `HS_ALLOW_PUBLISH=false`
e os gates de contrato/ACL/TLS permanecem falsos. Nenhuma CA, identidade Poste 2
ou credencial operacional deve ser adicionada ao ensaio virtual.

## Verificação em host, distinta do Wokwi

O teste `tests/circuit_test.cpp` compila `src/hardware.cpp` e o núcleo reais
com doubles apenas das chamadas Arduino e ADC sintético. Verifica GPIO34,
ADC de 12 bits/atenuação, GPIO25 ativo alto, histerese e publicação fechada.
Não modela luminosidade, circuito analógico, execução ESP32 ou LED físico.

Com Zig 0.13.0 disponível (ajustar o caminho para sua instalação):

```powershell
$zig = '.tools/venv/Lib/site-packages/ziglang/zig.exe'
New-Item -ItemType Directory -Force test-results | Out-Null
& $zig c++ -std=c++11 -Wall -Wextra -Werror -include simulation/config.h -I tests/circuit_fakes -I include -I lib/PosteCore/src lib/PosteCore/src/poste_core.cpp src/hardware.cpp tests/circuit_test.cpp -o test-results/circuit-test.exe
if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar teste host' }
& ./test-results/circuit-test.exe
if ($LASTEXITCODE -ne 0) { throw 'Teste host falhou' }
```

Fontes: [instalação CLI](https://docs.wokwi.com/wokwi-ci/cli-installation),
[uso e autenticação](https://docs.wokwi.com/wokwi-ci/cli-usage),
[cenários](https://docs.wokwi.com/wokwi-ci/automation-scenarios),
[controle lux do LDR](https://docs.wokwi.com/parts/wokwi-photoresistor-sensor).
