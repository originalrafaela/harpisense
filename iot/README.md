# HarpiSense IoT Firmware

## Poste 1 ESP32

O firmware em `iot/esp32/poste1` implementa o perfil físico LDR/LED aprovado
para desenvolvimento isolado em 31/10/2026. Publicação e hardware ficam
bloqueados por padrão. Tópico exclusivo do Poste 1:

```text
harpisense/v1/telemetry/harpisense.poste.poste-1/ldr
```

Identidade `harpisense.poste.poste-1`, client ID `poste-1`, envelope
`harpisense.telemetry.candidate.v2`. Credencial e ACL exclusivas ainda dependem
de coordenação; a ACL histórica de laboratório não é aceite operacional.

### Build configuration

Consulte [o guia do firmware](esp32/poste1/README.md) para arquitetura, configuração,
build/testes locais, pinagem proposta e montagem. O novo arquivo local é
`config_local.h`, ignorado pelo Git; o legado `config.h` não é carregado.

```powershell
cd iot\esp32\poste1
./scripts/build.ps1
```

### Hardware dependency

Hardware confirmado pelo operador: ESP-WROOM-32, placa de 30 pinos, LED e LDR.
GPIOs/circuito/limiares ainda são propostas. ADC bruto não é lux; o comando do
LED não é prova de acendimento. Nenhum upload ou teste físico integra esta entrega.
Poste 2, backend, broker e VMs permanecem preservados.
