# Executar o ensaio de circuito

Atualização 02/11/2026: o caminho **web com binário já compilado** dispensa o
token da CLI e foi usado nesta rodada. Os builds anteriores continuam válidos;
não é necessário recompilar para repetir o mesmo ensaio. Consulte os resultados
em [VALIDACAO_SIMULACAO_20261102.md](../VALIDACAO_SIMULACAO_20261102.md).

## Caminho web: abrir os arquivos prontos

Na pasta `iot/esp32/poste1`, executar apenas a preparação dos arquivos:

```powershell
./scripts/prepare-web.ps1
```

Isso verifica o hash do binário aprovado de `d746d43` e copia o diagrama
canônico, sem compilar nem acessar USB. Nesta máquina, os arquivos estão em
`.tools/wokwi-web/` e o pacote está em `.tools/wokwi-web.zip`. Extrair o ZIP
se for usá-lo em outro local. O binário é exclusivo da simulação.

1. Abrir [Novo ESP32 no Wokwi](https://wokwi.com/projects/new/esp32) no navegador.
   Alternativa oficial: [template de aplicação pré-compilada](https://wokwi.com/projects/305457271083631168).
2. Abrir a aba **diagram.json** e substituir **todo** o texto pelo conteúdo
   de `.tools/wokwi-web/diagram.json`. Conferir ESP32, LDR, LED e resistor.
3. Clicar dentro do editor e pressionar **F1**. Procurar **Upload Firmware
   and Start Simulation…** (algumas versões usam **Load HEX File and Start
   Simulation…**). Selecionar `.tools/wokwi-web/firmware.bin`.
4. Esse comando carrega o binário e inicia a simulação. **Não usar o botão
   normal de compilar o sketch.ino do template**: ele não é o nosso firmware.
   Não escolher **Flash firmware to device**: isso seria acesso físico.
5. Esperar o serial mostrar `network_closed: configuration/acceptance gates`
   e amostras `ldr_adc_raw=... led_commanded=... utc_valid=0`.
6. Clicar no módulo LDR. Ajustar o controle de luz em lux, nesta sequência:
   **100000 → 100 → 0.1 → 100 → 100000**. Esperar **duas novas linhas de
   amostra** após cada ajuste. Esperar pelo tempo simulado/serial, não só pelo
   relógio real: o navegador pode simular lentamente em segundo plano.
7. Guardar o serial completo e observar o LED externo virtual. Os dois passos
   em 100 lux devem manter estados diferentes conforme a condição anterior,
   demonstrando a histerese. Os resultados medidos nesta rodada estão no relatório.

Nesta sessão anônima não foi necessário login nem WOKWI_CLI_TOKEN para carregar
o binário. Salvar um projeto permanente na conta pode exigir login; isso não
foi feito. Reabrir/recarregar a página pode exigir repetir diagrama e upload.
O portal Maestri criado para este ensaio chama-se **Poste 1 Wokwi**; os arquivos
locais/Git são a fonte reproduzível, não a sessão temporária do navegador.

O `wokwi.toml` é usado por VS Code/CLI; no caminho web o firmware é escolhido
manualmente. Não copiar os fontes para sketch.ino nem manter outra lógica.
Binário SHA256: `a01327f11ac8102e3b1d138b71b105efc112040162ab0b0383d26ea51d6d33f6`.
O script publica também `SHA256.json` no pacote local.

Referência: [carregar aplicação pronta no Wokwi](https://docs.wokwi.com/guides/esp32).

## Autenticação local, se preferir VS Code ou CLI

O caminho web acima funciona sem o token da CLI. Para a extensão, ativar a
licença no navegador conforme a opção A abaixo. Para CLI, criar o token no
dashboard e inseri-lo **somente no terminal local**, com entrada oculta:

```powershell
$wokwiSecret = Read-Host 'Token Wokwi (somente nesta sessão)' -AsSecureString
$env:WOKWI_CLI_TOKEN = [Net.NetworkCredential]::new('', $wokwiSecret).Password
try {
    & .tools/wokwi/wokwi-cli.exe . --scenario simulation/circuit.yaml --timeout 30000 --serial-log-file test-results/wokwi-serial.log
    if ($LASTEXITCODE -ne 0) { throw 'Cenário não concluído' }
} finally {
    Remove-Item Env:WOKWI_CLI_TOKEN -ErrorAction SilentlyContinue
    $wokwiSecret.Dispose()
}
```

O exemplo substitui/remove a variável apenas nesta sessão. Se ela já estiver
configurada pelo usuário, usar diretamente o comando CLI da opção B. Não
colocar o token no código, Git, screenshots, histórico de comandos ou chat.

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
7. Clicar no módulo LDR e variar `lux`: **100000 → 100 → 0.1 → 100 → 100000**,
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
GPIO25, verificando claro→intermediário→escuro→intermediário→claro e comando serial com UTC inválido. Exige
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
