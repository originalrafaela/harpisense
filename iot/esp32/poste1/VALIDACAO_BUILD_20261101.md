# Build e verificação do projeto de simulação — 01/11/2026

Continuação de `feat/poste1-ensaio-wokwi`, base `fdfd27e`. Resultado: os dois
ambientes ESP32 compilaram. O projeto passou no lint Wokwi com um aviso
informativo. A execução do simulador foi tentada e parou por token ausente;
nenhum comportamento virtual ou físico foi observado nesta rodada.

## Comparação com o build aprovado

Referências: registro `VALIDACAO_20261031.md` da base `49d2eac`, script de build
daquela base, pacote 05 em `referencias/versão_v2/05_Firmware_ESP32` e contrato
06 v2 já preservado. Os pacotes anteriores de `referencias/Versões corretas`
continuam sendo a referência para componentes ainda não atualizados. Nenhum
componente foi declarado ausente e nenhum pacote/contrato foi substituído.

| Item | Build aprovado da base | Nesta rodada |
| --- | --- | --- |
| Python | 3.12, patch não registrado | 3.12.13, venv já existente, usado sem instalar/atualizar pacotes |
| PlatformIO | 6.1.18 | 6.1.18 |
| Plataforma / placa | espressif32 6.9.0 / esp32dev | Mesmos |
| Arduino-ESP32 | 2.0.17, pacote 3.20017.241212+sha.dcc1105b | Mesmo |
| GCC | 8.4.0+2021r2-patch5 | Mesmo; driver e cc1plus com SHA256 iguais entre origem e cópia |
| PubSubClient | 2.8.0 | 2.8.0 |
| Core PlatformIO | `.tools/pio` dentro do projeto, conforme script | Falha reproduzida usando core da worktree irmã; corrigida usando cópia exclusiva em caminho curto |
| Alvo | ESP32 clássico, 240 MHz, flash de referência 4 MB | Mesmo; identificação exata da placa ainda pendente |

O registro antigo não contém a linha interna completa do GCC; não é possível
afirmar retrospectivamente seu comprimento. A diferença comprovada é a forma
de localizar o core: dentro do projeto no script aprovado e absoluto externo
na reprodução da falha. Não houve alteração em `src/`, `include/` ou
`lib/PosteCore/` em relação a `49d2eac`. `platformio.ini` e a configuração
Wokwi também não foram alterados nesta rodada.

## Diagnóstico reproduzido

Diretório de trabalho: `iot/esp32/poste1` desta worktree. Comandos efetivos,
executados pelo Python do venv preexistente:

```powershell
$env:PLATFORMIO_CORE_DIR = 'D:/Projetos/tcc - harpisense/harpisense-worktrees/poste1-firmware/iot/esp32/poste1/.tools/pio'
& 'D:/Projetos/tcc - harpisense/harpisense-worktrees/poste1-firmware/iot/esp32/poste1/.tools/venv/Scripts/python.exe' -m platformio run -e esp32dev -v -j 1
```

Resultado: exit 1 ao compilar `src/communication.cpp`. O SCons escreve os
argumentos em arquivo de resposta e chama:

```text
xtensa-esp32-elf-g++ "@D:\Projetos\tcc - harpisense\harpisense-worktrees\poste1-ensaio\iot\esp32\poste1\.pio\build\esp32dev\tmpb15qy_3r.tmp"
xtensa-esp32-elf-g++: error: CreateProcess: No such file or directory
```

A linha expandida registrada pelo SCons tem **37.711 caracteres**. A chamada
e os argumentos completos estão em [build-original-verbose.log](evidence/build-20261101/build-original-verbose.log).
Não foi um erro de sintaxe, include ausente ou diagnóstico de código C++.

Controles executados, todos sem alterar o firmware:

- O mesmo GCC compilou `int main() { return 0; }` com `-v -c`: exit 0, com
  cc1plus e assembler encontrados. Log: [gcc-probe.log](evidence/build-20261101/gcc-probe.log).
- Reexecução direta via arquivo de resposta com caminhos longos: exit 1,
  mesmo `CreateProcess`. Arquivo [long-command.rsp](evidence/build-20261101/long-command.rsp),
  37.680 caracteres, saída em `gcc-long-replay.log` da mesma pasta.
- Mesmos argumentos de compilação e mesmo código, substituindo os caminhos
  do core pela cópia curta e o nome do objeto de saída: exit 0, objeto
  `test-results/communication-short.o` produzido. Arquivo
  [short-command.rsp](evidence/build-20261101/short-command.rsp), 26.791 caracteres.
  Nenhuma alteração de TEMP/PATH foi necessária nesse teste direto.
- GCC, cc1plus, implementação ADC do framework e manifesto esp32dev têm hashes
  iguais na origem e na cópia: [tool-hashes.json](evidence/build-20261101/tool-hashes.json).

Conclusão operacional: falha ambiental associada ao comprimento dos argumentos
com os caminhos externos longos. O limite de processo do Windows é 32.767
caracteres ([Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)).
A expansão do arquivo de resposta pelo GCC antes de iniciar seus subprocessos
é a explicação consistente com esses controles; não houve instrumentação da
chamada Win32 interna para identificar seu parâmetro exato. Não há evidência
para atribuir a falha ao firmware, à ausência do GCC ou a ferramentas corrompidas.

## Correção isolada e compilação

Criado o core exclusivo `D:/Projetos/tcc - harpisense/.p1-build`, copiando
`platforms/` e `packages/` da instalação preexistente, sem removê-la ou
atualizá-la. Não foi alterado PATH global nem instalado pacote Python global.
Cache/temp do build ficam no core exclusivo; binários e objetos ficam no
`.pio/` desta worktree. O Python antigo foi apenas executado, não atualizado.

`scripts/build.ps1` agora recebe CoreDir e Python, compila os dois ambientes,
salva logs e restaura PLATFORMIO_CORE_DIR/TEMP/TMP. Não possui caminho de upload.
Comando executado a partir da raiz do workspace:

```powershell
$python = Join-Path $PWD 'harpisense-worktrees/poste1-firmware/iot/esp32/poste1/.tools/venv/Scripts/python.exe'
& ./harpisense-worktrees/poste1-ensaio/iot/esp32/poste1/scripts/build.ps1 -CoreDir (Join-Path $PWD '.p1-build') -Python $python
```

| Ambiente | Resultado | RAM estática | Flash da aplicação | firmware.bin |
| --- | --- | --- | --- | --- |
| esp32dev | SUCCESS, 67,55 s | 55.668 / 327.680 B | 910.813 / 1.310.720 B | 917.392 B |
| wokwi | SUCCESS, 57,73 s | 55.668 / 327.680 B | 911.069 / 1.310.720 B | 917.648 B |

Logs completos: [esp32dev](evidence/build-20261101/build-esp32dev.log) e
[wokwi](evidence/build-20261101/build-wokwi.log). SHA256 do firmware.bin:

- esp32dev: `1e398a3eba9917b8a17081047f6c6b6d15f0e1c632c20b1e8821ec9e07cfee4e`.
- wokwi: `a01327f11ac8102e3b1d138b71b105efc112040162ab0b0383d26ea51d6d33f6`.

As cópias dos logs publicadas tiveram apenas espaços finais de linha removidos;
comandos, mensagens e resultados foram preservados.

Tamanhos e hashes também dos ELF: [artifacts.json](evidence/build-20261101/artifacts.json).
Os artefatos locais estão em `.pio/build/<ambiente>/firmware.bin` e
`firmware.elf`, ignorados pelo Git; fontes, logs e instruções foram publicados.
Builds não são declarados bit a bit idênticos ao da base: caminhos/metadados
e configuração do ambiente podem afetar os artefatos. Não existe config_local.h
nesta rodada. Perfil físico mantém defaults fechados; perfil Wokwi confirma
apenas circuito virtual e mantém publicação/contrato/ACL/TLS fechados.

## Verificação do projeto Wokwi

Instalado apenas em `.tools/wokwi/wokwi-cli.exe`, desta worktree, o executável
oficial **0.29.1 (0aa185144b92)**. Não houve instalação global.

```powershell
& .tools/wokwi/wokwi-cli.exe lint .
& .tools/wokwi/wokwi-cli.exe . --scenario simulation/circuit.yaml --timeout 30000 --serial-log-file test-results/wokwi-serial.log
```

- Lint: **exit 0**, uma informação `unsupported-part`: o catálogo do lint chama
  `board-esp32-devkit-c-v4` de tipo não documentado. A
  [documentação oficial PlatformIO/Wokwi](https://docs.wokwi.com/vscode/platformio)
  indica esse modelo para esp32dev. Não substituído por outra família ESP32.
  Esse resultado não equivale à validação dinâmica dos pinos/circuito.
- Tentativa de simulação: **exit 1**, `Missing WOKWI_CLI_TOKEN environment
  variable`. A simulação não iniciou. Não houve serial do firmware, leitura
  de luminosidade virtual ou observação do LED virtual.
- Logs: [lint](evidence/build-20261101/wokwi-lint.log) e
  [tentativa](evidence/build-20261101/wokwi-attempt.log).
- Cenário pronto: `simulation/circuit.yaml`, claro→escuro→claro, verificando
  comando serial e GPIO25. Comandos, ativação VS Code e alternativa CLI em
  [simulation/EXECUTAR.md](simulation/EXECUTAR.md). Dependência restante:
  usuário ativar licença da extensão ou fornecer token **na própria sessão**.

## Leitura e comando verificados em host

Compilados com Zig 0.13.0 o `src/hardware.cpp` e o `poste_core.cpp` reais,
injetando `simulation/config.h` e doubles apenas das funções Arduino. Resultado
exit 0: GPIO34 de entrada, resolução 12 bits, ADC_11db, GPIO25 de saída ativo
alto, estado inicial desligado e histerese preservados:

```text
synthetic_adc=500 GPIO34_read=34 GPIO25_command=0
synthetic_adc=2000 GPIO34_read=34 GPIO25_command=0
synthetic_adc=3000 GPIO34_read=34 GPIO25_command=1
synthetic_adc=2000 GPIO34_read=34 GPIO25_command=1
synthetic_adc=500 GPIO34_read=34 GPIO25_command=0
PASS: real hardware.cpp and hysteresis; synthetic ADC; MQTT closed
```

Log: [circuit-host.log](evidence/build-20261101/circuit-host.log). Isso verifica
o adaptador e controle com ADC sintético; **não é execução Wokwi, modelo de
luminosidade ou ensaio físico**. Não foi criada outra implementação de leitura
ou controle. Os doubles não entram no firmware ESP32.

Nenhum upload, monitor serial físico, acesso a broker ou VM foi executado.
Nenhum contrato, identidade ou credencial do Poste 2 foi alterado/utilizado.
Publicação MQTT permanece bloqueada no circuito. Compilação aprovada não
comprova comportamento virtual, montagem física, TLS ou entrega MQTT.
