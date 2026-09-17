# Progresso - iot-mqtt

## Estado em 2026-09-16

- Pasta de trabalho: `D:\Projetos\harpisense-worktrees\iot-mqtt`
- Branch atual: `iot-mqtt`
- Remoto confirmado: `origin` aponta para `https://github.com/originalrafaela/harpisense.git`
- Estado antes deste resumo: branch limpa em `iot-mqtt`

## Implementacao realizada

Entrega IoT/MQTT inicial implementada no commit `c7aa9e0 Add IoT MQTT lab delivery`.

Arquivos principais:

- `mqtt/docker-compose.yml`: broker Mosquitto reproduzivel via Docker Compose.
- `mqtt/config/mosquitto.conf`: configuracao do broker com autenticacao obrigatoria, ACL, persistencia e logs.
- `mqtt/config/aclfile`: ACLs de laboratorio para publicador IoT, subscriber de teste e futuro exportador de evento de autenticacao.
- `mqtt/config/lab-users.example`: usuarios e senhas somente de exemplo para laboratorio; nao sao credenciais reais.
- `mqtt/config/create-password-file.sh`: geracao local do arquivo `mqtt/config/passwords`, ignorado pelo Git.
- `mqtt/README.md`: comandos de operacao do broker, ACLs e logs.
- `lab/legitimate-traffic/mqtt_contract.py`: constantes e validacao local dos topicos/payloads acordados.
- `lab/legitimate-traffic/simulate_poste.py`: simulador de poste para `poste-2` e `poste-3`, com teste de reconexao do cliente MQTT.
- `lab/legitimate-traffic/test_subscriber.py`: subscriber de teste que assina `harpisense/v1/telemetry/#` e valida payloads recebidos.
- `lab/legitimate-traffic/requirements.txt`: dependencia Python `paho-mqtt==2.1.0`.
- `tests/integration/test_mqtt_contract.py`: testes de contrato do payload simulado.
- `tests/integration/run_mqtt_smoke.ps1`: roteiro de smoke test para broker, subscriber, publisher e reconexao simulada.
- `iot/esp32/poste1/platformio.ini`: projeto PlatformIO para ESP32.
- `iot/esp32/poste1/include/config.example.h`: configuracao local de exemplo para Wi-Fi/MQTT, sem segredo real.
- `iot/esp32/poste1/src/main.cpp`: firmware do Poste 1 publicando no topico contratado de ambiente.
- `iot/README.md` e `lab/README.md`: comandos, limites e dependencias.
- `.gitignore`: ignora `mqtt/config/passwords`, `mqtt/data/`, `mqtt/log/` e `iot/esp32/poste1/include/config.h`.

## Contratos e decisoes usados

Fontes lidas e respeitadas:

- `docs/AREAS_DE_TRABALHO.md`
- `docs/CONTRATOS_COMPARTILHADOS.md`
- `docs/DECISOES_ARQUITETURAIS.md`
- `docs/PLANO_PRIMEIRA_ENTREGA.md`

Contratos aplicados:

- Identificadores: `harpisense.poste.poste-1`, `harpisense.poste.poste-2`, `harpisense.poste.poste-3`.
- Topico ESP32 Poste 1: `harpisense/v1/telemetry/harpisense.poste.poste-1/environment`.
- Topicos simulados: `harpisense/v1/telemetry/harpisense.poste.poste-2/environment` e `harpisense/v1/telemetry/harpisense.poste.poste-3/environment`.
- Payload JSON UTF-8 com `schema_version`, `message_id`, `device_id`, `observed_at`, `sensor_type`, `sequence`, `measurements` e `status`.
- Timestamps produzidos em UTC com sufixo `Z`.
- Valores desconhecidos representados como `null`.

Decisoes tomadas:

- Nao criar contratos paralelos nem alterar os documentos compartilhados.
- Nao implementar deteccao, ML, bloqueio, backend ou API.
- Nao publicar topico `power` no firmware porque sensores de tensao/corrente/potencia nao estao definidos.
- Nao inventar sensor ou pinagem do ESP32. O firmware publica `temperature_c` e `humidity_pct` como `null` ate haver sensor/pinagem aprovados.
- Usar nomes de variaveis de ambiente para credenciais de execucao: `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`.

## Validacao realmente executada

Validacoes concluidas com sucesso:

- `docker compose -f mqtt\docker-compose.yml --profile init config`
  - Resultado: configuracao Compose renderizada corretamente.
  - Observacao: apareceu aviso de acesso ao `C:\Users\amara\.docker\config.json`, mas o comando terminou com codigo 0.
- Parser PowerShell do arquivo `tests\integration\run_mqtt_smoke.ps1`
  - Resultado: `PowerShell parse OK`.
- `git diff --cached --check`
  - Resultado: sem erros.
- Verificacao de EOL do script `mqtt/config/create-password-file.sh`
  - Resultado: `i/lf`, `w/lf`, atributo `text eol=lf`.

## Testes nao executados, bloqueios e dependencias

Testes nao executados:

- Publicacao/recebimento MQTT real com Mosquitto, simulador e subscriber.
- Smoke test `tests\integration\run_mqtt_smoke.ps1`.
- Testes Python com `pytest`.
- Build do firmware ESP32 com PlatformIO.
- Upload e teste em hardware real.

Bloqueios observados no ambiente:

- Docker CLI existe, mas o daemon Docker nao estava ativo: falha ao conectar em `npipe:////./pipe/docker_engine`.
- Launcher Python confirmado em `C:\Windows\py.exe`, mas `py --version` retornou `No installed Python found!`.
- Ambiente virtual Python nao foi criado nem confirmado.
- `pio`/PlatformIO nao foi encontrado no PATH.
- ESP32 fisico, sensor de temperatura/umidade e pinagem aprovada nao estavam disponiveis.

Dependencias pendentes:

- Definir sensor fisico e pinagem do Poste 1.
- Confirmar IP/host do broker no laboratorio.
- Ativar Docker ou disponibilizar Mosquitto local.
- Instalar Python e dependencias para executar simulador/subscriber.
- Instalar PlatformIO para build/upload do firmware.

## Trabalho incompleto e alinhamentos pendentes

- Validacao MQTT fim a fim permanece pendente por falta de runtime local.
- Validacao em hardware real permanece pendente por falta de ESP32/sensor/pinagem.
- O firmware contem o caminho MQTT correto, mas ainda nao le sensor real.
- A configuracao de laboratorio usa credenciais de exemplo e exige substituicao fora do Git antes de uso real.
- Logs reais de Mosquitto nao foram gerados nesta sessao porque o broker nao foi iniciado.

## Atualizacao - simulador sintetico configuravel

Implementacao preparada nesta rodada:

- `lab/legitimate-traffic/simulate_poste.py`: simulador agora aceita quantidade de postes, identificadores, intervalo, duracao, semente aleatoria e modo JSONL local sem broker.
- `lab/legitimate-traffic/mqtt_contract.py`: helpers para derivar topico por `device_id` e validacoes de faixas plausiveis para temperatura, umidade e RSSI.
- `lab/legitimate-traffic/test_subscriber.py`: saida estruturada com `status` `VALID` ou `INVALID`, mantendo erros de validacao visiveis.
- `tests/integration/test_mqtt_contract.py`: testes preparados para geracao multi-poste, JSONL, variacao plausivel, classificacao do subscriber e retransmissao com o mesmo `message_id`.
- `lab/legitimate-traffic/README.md`: comandos exatos atualizados e marcacao dos dados como sinteticos nos metadados/wrappers, sem alterar o payload MQTT compartilhado.

Comandos documentados para uso posterior:

```powershell
$env:MQTT_PASSWORD="change-me-iot-lab"
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --devices poste-2,poste-3,poste-4 --count 5 --interval 2 --duration 30 --seed 12345
```

```powershell
.\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --devices poste-2,poste-3 --count 2 --interval 0 --seed 123 --jsonl lab\legitimate-traffic\samples\synthetic-telemetry.jsonl
```

Testes preparados, mas nao executados neste ambiente por falta de Python:

```powershell
.\.venv\Scripts\python -m pytest tests\integration\test_mqtt_contract.py
```

## Proximos passos sugeridos

1. Ativar Docker Desktop ou Mosquitto local.
2. Instalar Python e criar ambiente virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python -m pip install -r lab\legitimate-traffic\requirements.txt
   ```

3. Subir o broker de laboratorio:

   ```powershell
   cd mqtt
   docker compose --profile init run --rm mosquitto-init
   docker compose up -d mosquitto
   ```

4. Rodar smoke test simulado:

   ```powershell
   .\tests\integration\run_mqtt_smoke.ps1 -Python .\.venv\Scripts\python
   ```

5. Alternativa manual para teste simulado:

   ```powershell
   $env:MQTT_PASSWORD="<definir fora do Git>"
   .\.venv\Scripts\python lab\legitimate-traffic\test_subscriber.py --expected-count 2
   ```

   Em outro terminal:

   ```powershell
   $env:MQTT_PASSWORD="<definir fora do Git>"
   .\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --device poste-2 --count 2 --interval 1 --exercise-reconnect
   ```

6. Depois de aprovar sensor/pinagem do Poste 1, implementar leitura real em `readEnvironment()`.
7. Instalar PlatformIO e validar firmware:

   ```powershell
   cd iot\esp32\poste1
   pio run
   pio run --target upload
   pio device monitor
   ```

## Python e ambiente virtual

- Caminho confirmado do launcher: `C:\Windows\py.exe`.
- Python instalado: nao confirmado; `py --version` retornou `No installed Python found!`.
- Ambiente virtual: nao criado nesta sessao.

## Commits relevantes

- `c7aa9e0 Add IoT MQTT lab delivery`
- `b87f592 docs: prepare first delivery contracts`
