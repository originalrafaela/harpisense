# Recibo de validação local — 31/10/2026

Branch de entrega: `feat/poste1-ldr-firmware`, criada sobre `fe88645`, cuja base
é `9e4467ea6d57726a9fc65ab88e5f414f9a69c7cb`. Alterações limitadas a `iot/`.
Decisão lida na worktree do arquiteto: `docs/DECISAO_CONTRATO_POSTE1_20261031.md`,
SHA-256 dos bytes locais
`233da21a2d55d81e6f5524e5f0bf73a661b163dc8407371a4acdc815fe6e14dc`.

## Compilação concluída

Comando na pasta do firmware: `./scripts/build.ps1` (somente build).
Resultado final: exit 0, `[SUCCESS] Took 15.98 seconds`.

| Item | Valor observado |
| --- | --- |
| Host | Windows, venv Python 3.12; sem instalação no Python global |
| PlatformIO | 6.1.18 |
| Plataforma/alvo | espressif32 6.9.0 / esp32dev (ESP32 clássico, flash de referência 4 MB) |
| Framework resolvido | framework-arduinoespressif32 3.20017.241212+sha.dcc1105b (Arduino-ESP32 2.0.17) |
| Toolchain | xtensa-esp32 8.4.0+2021r2-patch5 |
| Cliente | PubSubClient 2.8.0 |
| RAM estática reportada | 55.668 / 327.680 bytes, 17,0% |
| Flash da partição de aplicação | 910.453 / 1.310.720 bytes, 69,5% |
| Tamanho de firmware.bin | 917.024 bytes |

Artefatos locais ignorados pelo Git:

- `.pio/build/esp32dev/firmware.bin`: SHA-256
  `c48c30889d62a7a392cdca792481214fcd314505412c3f1bad43754f4eb578f3`.
- `.pio/build/esp32dev/firmware.elf`: SHA-256
  `5643143a50fbb027ab5dabb2d4016ac91ce3746c89db5583239a0023bc0d4924`.

Os hashes identificam esta compilação local; caminhos/metadados do compilador
podem afetar builds posteriores. Artefatos foram produzidos com gates fechados,
sem config_local.h/segredos. Não houve upload, porta serial ou placa conectada.

## Testes concluídos

Comando: `scripts/test-local.ps1`, parâmetros absolutos P06 e ContractPython.
P06 resolvido em
`referencias/versão_v2/06_Telemetria_MQTT/HarpiSense_Etapa06_Telemetria_MQTT_v2/06_Telemetria_MQTT`.
ContractPython utilizado: venv Python 3.12 já preparado pelo arquiteto em
`harpisense-worktrees/frontend-backend-autonomia/frontend/local-evidence/poste1-contract-venv/Scripts/python.exe`.
Nenhuma instalação ou alteração feita nesse venv nesta rodada. Compilador
nativo Zig 0.13.0 instalado apenas no venv local de ferramentas deste firmware.

Saída final, exit 0:

```text
PASS: 7 core test groups (includes 128 gate combinations)
PASS: 7 firmware-generated payloads accepted by P06 and local physical-profile assertions
PASS: 4 communication orchestration variants with test doubles; no real TLS handshake
```

- Core: calendário UTC/frescor monotônico, faixa ADC/histerese/pinos, defaults e
  combinações de gates, formato/estabilidade de identidade, fila/retry idêntico,
  overflow, prazo exato de 120 s, wrap de millis, publicação em voo com cabeça
  descartada, perda sem UTC e recuperação sem reconstruir amostra antiga.
- Serialização: executável C++ usa o mesmo arquivo `poste_core.cpp` do firmware;
  sete casos cobrem 0, 4095, leitura intermediária, UNAVAILABLE, fora de faixa e
  sequência máxima. Bytes emitidos são parseados pelo core P06 original, sem
  schema concorrente, com asserções adicionais do perfil físico.
- Comunicação: testes compilam `src/communication.cpp` real com doubles.
  Verificam gates fechados, CA ausente, IP literal bloqueado e caminho sintético
  com CA/hostname, espera por UTC, reconexão/backoff, falha de envio, client ID,
  tópico/retain e expiração. Nenhum socket real é aberto; a CA desse teste é
  deliberadamente uma string sintética inválida para uso TLS real.
- `git diff --check` passou; revisão de arquivos de entrega não encontrou
  credencial operacional ou chave privada. Bibliotecas, binários, venv, caches
  e configurações locais estão ignorados; código fonte `lib/PosteCore` incluído.

Na preparação, o compilador nativo emitiu avisos da própria libunwind ao montar
seu cache. A checagem `-Werror` também identificou uma expressão de configuração
constante, corrigida antes do resultado final. O primeiro build apontou include
SNTP obsoleto, substituído por esp_sntp.h. A revisão da API real identificou
setTimeout em segundos e o ajustou para 3; a compilação final passou após essas
correções. Esses estados intermediários não são o resultado entregue.

## Limites do aceite

Não foram executados: gravação/ensaio em ESP32, leitura física do LDR/LED,
confirmação da pinagem/circuito/limiares, handshake TLS real (positivo/negativos),
ACL ou autenticação no broker, tráfego MQTT real, PostgreSQL e regressão ativa
do Poste 2. A suíte P06 de 21 testes mencionada pelo arquiteto é evidência de sua
rodada anterior; aqui o teste de contrato foi dos sete payloads gerados pelo C++.

TLS foi preparado usando CA e hostname na API real; inspeção da dependência
confirmou verificação obrigatória de cadeia e hostname. Isso não comprova
certificados/rede operacionais. QoS 0 só confirma aceitação local; não há
durabilidade RAM, ACK de aplicação ou promessa de exatamente uma vez.

Próximo passo: revisão do código/pinagem pelo arquiteto, coordenação com o
adaptador Backend Data e autorização posterior de bancada isolada. Publicação
operacional continua fechada. Nenhum contrato compartilhado, broker, VM,
consumidor ou caminho Poste 2 foi alterado.
