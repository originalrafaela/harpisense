# Poste 1 — ESP-WROOM-32, LED e LDR

Implementação para desenvolvimento isolado, baseada em `9e4467e` e na matriz
`fe88645`; decisão do arquiteto em
`harpisense-worktrees/frontend-backend-autonomia/docs/DECISAO_CONTRATO_POSTE1_20261031.md`
na raiz compartilhada. O documento de decisão é a autoridade para este perfil.
Precedência: entregas aprovadas de `referencias/versão_v2`, depois
`referencias/Versões corretas` para componentes sem revisão. P05 é referência
de aquisição/fila; P06/P07 fornecem o envelope; não há importação do pipeline
SQLite P07, do consumidor operacional ou alteração dos contratos compartilhados.

## Organização para futuros firmwares

| Camada | Arquivos | Responsabilidade |
| --- | --- | --- |
| Aplicação | `src/main.cpp` | Agenda de coleta, composição das camadas, tarefas e métricas locais |
| Regras portáveis | `lib/PosteCore/src/` | Perfil, serialização limitada, identidade, histerese, fila e descarte; sem Arduino/rede/heap |
| Hardware | `src/hardware.cpp` | ADC1 de 12 bits e comando do LED; GPIOs propostos condicionados a aceite local |
| Tempo | `src/trusted_clock.cpp` | SNTP, UTC real de coleta e validade monotônica da última sincronização |
| Comunicação | `src/communication.cpp` | Wi-Fi, TLS validado, MQTT QoS 0, backoff e gates |
| Configuração | `include/settings.h`, `include/config.example.h` | Defaults fechados; overrides em `config_local.h` ignorado pelo Git |

A tarefa Arduino lê o LDR a cada 1 segundo e comanda o LED. Uma tarefa de rede
separada, com stack de 8192 bytes, faz conexão e esvazia até 8 entradas a cada
5 segundos; handshake/conexão não seguram o mutex da aquisição. O mutex cobre
apenas operações curtas da fila. Uma publicação em voo pode coincidir com
descarte por overflow/idade: sua conclusão não remove a nova cabeça da fila.
Os contadores distinguem descarte local de aceitação do envio; não representam
contagem comprovada de mensagens recebidas pelo broker.

## Contrato implementado

- Tópico exato `harpisense/v1/telemetry/harpisense.poste.poste-1/ldr`;
  device_id `harpisense.poste.poste-1`, client ID estável `poste-1`.
- schema_version `harpisense.telemetry.candidate.v2`, sensor_type `ldr`;
  nenhuma publicação environment, temperatura/umidade ou identidade Poste 2.
- Origem PHYSICAL, unidade adc_raw; ADC inteiro 0..4095 e qualidade
  RAW_UNCALIBRATED. UNAVAILABLE/OUT_OF_RANGE usam null, sem saturação silenciosa.
  O driver analógico não detecta circuito aberto: 0/4095 continuam leituras válidas.
  As saídas null são exercitadas por testes do core, sem alegar detecção física.
- led_commanded_on é booleano do comando local; não há observação física do LED.
  calibration_version é omitido. Sem campos extras, números não finitos ou
  campos voláteis; buffer do JSON é 1024 bytes + terminador.
- observed_at é coletado junto à leitura, UTC com Z, nunca reconstruído depois.
  Sem callback SNTP válido neste boot, data impossível ou sincronização com mais
  de 1 hora, a amostra é perdida e no_utc incrementa. O LED continua localmente.
  Não há fallback 1970. A faixa defensiva do relógio é 2024..2099.
- SNTP usa o servidor explicitamente configurado. A verificação de sincronização
  não autentica criptograficamente NTP: disponibilidade e confiança da fonte
  de tempo precisam de validação na rede. Sem rede habilitada, não há SNTP nem
  telemetria, apenas controle local e contagem de perdas.
- ID: device_id + '-' + boot aleatório de 16 hex + '-' + sequence. O boot usa
  fonte de entropia do ESP32 antes de inicializar ADC/Wi-Fi; sequência crescente
  até 9007199254740991. Ao esgotar, reinicia para obter novo boot, perdendo a fila
  RAM. Colisão aleatória não é matematicamente impossível.
- Fila RAM de 8; cheia descarta a mais antiga, com contador overflow. Ao atingir
  120 segundos monotônicos desde coleta, descarta e incrementa expired. Retry
  conserva exatamente ID, sequência, observed_at e bytes. Cálculo uint32_t de
  idade também funciona no wrap de millis para o intervalo contratado.

MQTT publica QoS 0, retain=false, keepalive 30. `publish=true` significa somente
aceitação local da biblioteca/transporte: não comprova ACK do broker ou commit
PostgreSQL. Pode haver perda e duplicata; reboot perde a fila. Não existe ACK de
aplicação nem promessa de entrega exatamente uma vez. A deduplicação persistente
é responsabilidade do adaptador Backend Data já decidido pelo arquiteto; este
firmware não implementa banco ou consumidor paralelo.

## TLS e configuração fechada

Build padrão não associa Wi-Fi, não conecta MQTT e não configura GPIOs.
Mesmo copiado, `config.example.h` mantém essas condições. O legado `config.h`
não é carregado, evitando reativar credenciais/porta de laboratório antigas.

O futuro `config_local.h` deve ficar fora do Git: SSID/senha, servidor NTP,
hostname DNS do broker, usuário/senha exclusivos e CA PEM confiável. Porta
proposta 8883 não configura nem pressupõe listener existente. Hostname deve
coincidir com o certificado; IP literal é recusado neste perfil.

`WiFiClientSecure.setCACert()` e conexão pelo hostname preservam verificação
de cadeia e hostname/SNI. Sem CA configurada, não conecta. Certificado inválido,
CA incorreta, expiração ou hostname errado devem falhar; não há cliente plaintext
ou API para desabilitar a validação no firmware. Timeout TLS: handshake 5 s,
socket 3 s; backoff de reconexão 1..60 s. DNS/TCP ainda podem atrasar a tarefa
de rede, sem bloquear o controle local. Inspeção da dependência Arduino-ESP32
2.0.17 confirmou VERIFY_REQUIRED e mbedtls_ssl_set_hostname no caminho usado.

Para qualquer teste de rede futuro, gates independentes exigem aceite explícito:
HS_HARDWARE_CONFIRMED, HS_CONTRACT_CONFIRMED, HS_IDENTITY_ACL_VALIDATED,
HS_TLS_VALIDATED e HS_ALLOW_PUBLISH. Todos estão false nesta entrega. A decisão
documental de contrato não comprova hardware, ACL ou TLS e não muda esses defaults.
ACL futura: escrita apenas no tópico exato, credencial exclusiva, sem acesso do
Poste 1 aos tópicos do Poste 2. Isso não foi provisionado nesta rodada.

## Pinagem e montagem propostas — conferir antes de energizar

Identificar pela serigrafia GPIO, não pelo número da posição no conector.
Placas de 30 pinos podem variar; alvo esp32dev compila para ESP32 clássico e
flash de referência 4 MB, sem confirmar revisão/flash do exemplar físico.

| Ligação | Proposta |
| --- | --- |
| LDR | 3V3 → LDR → nó de leitura → resistor 10 kΩ → GND |
| Nó do divisor | GPIO34 / ADC1_CH6, entrada apenas, sem pull-up interno |
| LED externo | GPIO25 → resistor 330 Ω → ânodo LED; cátodo → GND |
| Referência | GND comum; alimentar o divisor em 3,3 V, nunca em 5 V |

Com esse divisor, escurecer tende a baixar o ADC: HS_ADC_DARK_IS_LOW=true.
LED proposto ativo em HIGH. Confirmar isso no circuito real. Resistor de 10 kΩ
é ponto inicial de bancada, não calibração. GPIO34 usa ADC1 para coexistir com
Wi-Fi; GPIO25 é usado como saída digital, sem ler ADC2. A documentação oficial
identifica [GPIO34 como entrada ADC1 e GPIO25 como GPIO disponível](https://documentation.espressif.com/esp32-wroom-32_datasheet_en.html)
e [GPIO34–39 como entradas sem pull-up/pull-down internos](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/gpio.html).

1. Com USB/alimentação desconectados, conferir placa, serigrafia, polaridade
   do LED e valores dos resistores; montar o divisor e LED conforme tabela.
2. Conferir continuidade e ausência de curto; medir o nó, garantindo que não
   ultrapasse 3,3 V. Saturação ADC não é medida em volts/lux.
3. Em uma rodada física posteriormente autorizada, manter publicação fechada,
   confirmar somente o hardware local e observar ldr_adc_raw pela serial 115200
   em luz/escuro. Não usar limiares inventados: valores iniciais permanecem -1.
   Para coletar inicialmente, escolher um par provisório explicitamente de bancada
   dentro de 0..4095 após medir o divisor com instrumento; revisá-lo pelos logs.
4. Definir DARK_THRESHOLD < BRIGHT_THRESHOLD para histerese e confirmar direção;
   testar oscilações próximas aos limiares. Configuração inválida mantém GPIOs
   intocados. Em leitura inválida, o comando de LED vai a desligado.
5. Confirmar montagem/limiares antes do aceite físico. Este roteiro não executou
   upload. Não ligar carga de poste/lâmpada ao GPIO: o escopo é LED de bancada.

## Reproduzir build e testes locais no Windows

Na pasta deste firmware, usando Python 3.12 local (sem instalar no Python global):

```powershell
& C:/Users/amara/.local/bin/python3.12.exe -m venv .tools/venv
& ./.tools/venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./scripts/build.ps1
```

Build fixa PlatformIO 6.1.18, espressif32 6.9.0, PubSubClient 2.8 e Arduino-ESP32
2.0.17 via plataforma. Cache, ferramentas, ELF/binários e credenciais locais
são ignorados. O script executa apenas `platformio run`, sem alvo upload.

Para validar o serializador real contra a dependência P06, fornecer caminhos
absolutos do pacote e de um venv Python 3.12 com seu requirements.txt instalado:

```powershell
$p06 = 'D:/Projetos/tcc - harpisense/referencias/versão_v2/06_Telemetria_MQTT/HarpiSense_Etapa06_Telemetria_MQTT_v2/06_Telemetria_MQTT'
& ./.tools/venv/Scripts/python.exe -m pip install -r "$p06/requirements.txt"
./scripts/test-local.ps1 -P06 $p06 -ContractPython (Resolve-Path .tools/venv/Scripts/python.exe).Path
```

Testes C++ usam Zig 0.13.0 como compilador nativo Windows, exercitando o mesmo
core do ESP32: UTC/calendário/frescor, histerese/ADC, 128 combinações de gates,
identidade, fila/overflow/TTL/wrap/retry, coleta sem UTC e serialização. Sete
payloads gerados por esse executável são validados pelo P06 e por asserções do
perfil físico. Quatro variantes da comunicação usam doubles de Arduino/Wi-Fi/
TLS/MQTT: gates fechados, CA ausente, IP literal e fluxo habilitado sintético.
Elas verificam API de CA/hostname, ausência de fallback, espera por UTC,
backoff, falha/aceitação local, tópico, client ID e retain=false. Não são
handshakes reais nem ensaios do broker. Nenhuma fonte de schema foi copiada.

## Aceite físico e de rede ainda pendente

Compilação e testes de host não validam ADC, polaridade, LED físico, flash real,
pilha/heap sob handshake, perdas de energia ou RF, fonte NTP, TLS real, ACL ou
persistência no backend. Roteiro posterior: montagem e limiares; reboot e fila;
Wi-Fi indisponível; NTP ausente/expirado; broker indisponível; certificado válido,
CA errada, hostname errado e expirado; recusa de identidade/tópicos não autorizados;
correlação com o adaptador oficial preservando Poste 2. Tudo em ambiente isolado
autorizado antes de qualquer habilitação operacional. Não alterar broker/VMs
para fazer o firmware passar nesses gates.
