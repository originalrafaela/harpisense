# Próxima sequência curta: USB e placa física

**Preparação para uma rodada futura. Nada abaixo foi executado nesta rodada.**
Avançar à gravação somente depois de o usuário confirmar explicitamente a placa
conectada e pronta. O ensaio web não autoriza gravação nem calibra o LDR físico.

1. Confirmar placa ESP32-WROOM-32, modelo da dev board, flash, foto/pinagem,
   montagem e alimentação conforme ENSAIO.md. Manter LDR GPIO34, LED GPIO25.
   Desligar a alimentação para montar/verificar o circuito.
2. Usar cabo USB de dados. Depois da confirmação de conexão, comparar portas
   antes/depois com `platformio device list`; registrar COM, VID/PID e conversor
   USB-UART. Não assumir COMx de outra placa.
3. Revisar `include/config_local.h` físico a partir de `config.example.h`.
   Confirmar hardware só após inspeção elétrica, polaridade física
   `HS_ADC_DARK_IS_LOW=true` e limiares numéricos ordenados válidos. Limiares
   exploratórios devem ser registrados como provisórios, não copiados da
   simulação como calibração. Manter **HS_ALLOW_PUBLISH=false** e gates de
   contrato/ACL/TLS falsos; não colocar credenciais de rede.
4. Compilar **apenas esp32dev**, revisar log e hash. O binário físico anterior
   tem gates fechados e não exercita leitura/LED enquanto não configurado.
   Nunca gravar `.pio/build/wokwi/firmware.bin` nem o binário do ZIP web.
5. Após confirmação explícita da gravação e porta identificada, executar o
   upload físico; fechar qualquer monitor serial antes. Guardar saída da
   verificação e abrir monitor 115200. Se houver `hardware_closed`, revisar a
   configuração; isso não é um ensaio de luz aprovado.

Na pasta `iot/esp32/poste1`, caminhos disponíveis nesta máquina:

```powershell
$python = 'D:/Projetos/tcc - harpisense/harpisense-worktrees/poste1-firmware/iot/esp32/poste1/.tools/venv/Scripts/python.exe'
$core = 'D:/Projetos/tcc - harpisense/.p1-build'
$env:PLATFORMIO_CORE_DIR = $core
# Somente na rodada futura de reconhecimento USB:
& $python -m platformio device list
# Após revisar a configuração física:
./scripts/build.ps1 -CoreDir $core -Python $python -Environment esp32dev
```

**Separado: somente após confirmação de gravação, usando a COM identificada:**

```powershell
& $python -m platformio run -e esp32dev -t upload --upload-port COMx
& $python -m platformio device monitor --port COMx --baud 115200
```

Registrar ADC por pelo menos 30 amostras em claro e escuro, comando do LED e
observação independente do acendimento físico. Guardar logs/fotos e versão do
binário. Ajustar limiares pela dispersão medida na montagem real. Wi-Fi/NTP/TLS/
MQTT continuam fora desse ensaio de circuito e exigem validação separada.
