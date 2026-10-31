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

## Atualizacao - usuario MQTT do consumidor backend

Contrato atualizado lido da `main` incorporada:

- Consumidor backend MQTT: `harpisense_backend_consumer`.
- Usuario deve ser dedicado a leitura de telemetria.
- ACL minima: `topic read harpisense/v1/telemetry/#`.
- Sem permissao de publicacao e sem acesso a `harpisense/v1/security/#`.
- Variaveis esperadas pelo consumidor backend: `HARPI_MQTT_USERNAME`, `HARPI_MQTT_PASSWORD`, `HARPI_MQTT_HOST`, `HARPI_MQTT_PORT` e `HARPI_MQTT_TELEMETRY_TOPIC`.

Implementacao preparada nesta rodada:

- `mqtt/config/aclfile`: adiciona `harpisense_backend_consumer` com leitura apenas em `harpisense/v1/telemetry/#`.
- `mqtt/config/create-password-file.sh`: adiciona o usuario backend ao password file a partir de `HARPISENSE_BACKEND_CONSUMER_PASSWORD`; recusa senha desse usuario no arquivo de usuarios; recusa sobrescrever `mqtt/config/passwords` sem `--force`.
- `mqtt/config/lab-users.example`: documenta que a senha do consumidor backend e externa e nao versionada.
- `.gitignore`: ignora `mqtt/config/lab-users.local` para credenciais locais opcionais.
- `tests/integration/run_mqtt_smoke.ps1`: passa a receber `-BackendConsumerPassword` para provisionar o usuario exigido.
- `tests/integration/test_mqtt_backend_consumer_acl.ps1`: prepara teste com broker real para assinatura permitida, publicacao proibida e acesso proibido a topicos de seguranca.
- `mqtt/README.md`: documenta criacao, atualizacao, ACLs e correspondencia com variaveis `HARPI_MQTT_*` usadas pelo consumidor backend, sem alterar arquivos de `backend-data`.

Comandos preparados:

```powershell
cd mqtt
$env:HARPISENSE_BACKEND_CONSUMER_PASSWORD="<senha-mqtt-backend-consumer>"
docker compose --profile init run --rm -e HARPISENSE_BACKEND_CONSUMER_PASSWORD mosquitto-init
docker compose up -d mosquitto
Remove-Item Env:\HARPISENSE_BACKEND_CONSUMER_PASSWORD
```

```powershell
cd mqtt
$env:HARPISENSE_BACKEND_CONSUMER_PASSWORD="<nova-senha-mqtt-backend-consumer>"
docker compose --profile init run --rm -e HARPISENSE_BACKEND_CONSUMER_PASSWORD mosquitto-init /mosquitto/config/create-password-file.sh /mosquitto/config/lab-users.example /mosquitto/config/passwords --force
Remove-Item Env:\HARPISENSE_BACKEND_CONSUMER_PASSWORD
```

```powershell
.\tests\integration\test_mqtt_backend_consumer_acl.ps1 -BackendConsumerPassword "<senha-mqtt-backend-consumer>"
```

Testes preparados, mas dependentes de broker real para validar ACL:

- Assinatura permitida: `harpisense_backend_consumer` assina `harpisense/v1/telemetry/#`.
- Publicacao proibida: `harpisense_backend_consumer` tenta publicar em topico de telemetria.
- Acesso a seguranca proibido: `harpisense_backend_consumer` tenta assinar e publicar em `harpisense/v1/security/#`.

Pendencias mantidas:

- Nao houve alteracao em firmware, sensores, pinagem, NTP ou validacao fisica.
- Sensor fisico e pinagem do Poste 1 continuam pendentes de aprovacao.
- Validacao fisica com ESP32 e broker real continua pendente.
- ACLs so devem ser declaradas validadas apos executar `test_mqtt_backend_consumer_acl.ps1` contra Mosquitto real.

## Proximos passos sugeridos

1. Amanha: ativar Docker Desktop ou disponibilizar Mosquitto local e validar as ACLs reais do broker com o usuario `harpisense_backend_consumer`.
2. Instalar Python e criar ambiente virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python -m pip install -r lab\legitimate-traffic\requirements.txt
   ```

3. Subir o broker de laboratorio:

   ```powershell
   cd mqtt
   $env:HARPISENSE_BACKEND_CONSUMER_PASSWORD="<senha-mqtt-backend-consumer>"
   docker compose --profile init run --rm -e HARPISENSE_BACKEND_CONSUMER_PASSWORD mosquitto-init
   docker compose up -d mosquitto
   Remove-Item Env:\HARPISENSE_BACKEND_CONSUMER_PASSWORD
   ```

4. Validar ACLs do consumidor backend contra broker real:

   ```powershell
   .\tests\integration\test_mqtt_backend_consumer_acl.ps1 -BackendConsumerPassword "<senha-mqtt-backend-consumer>"
   ```

5. Rodar smoke test simulado:

   ```powershell
   .\tests\integration\run_mqtt_smoke.ps1 -Python .\.venv\Scripts\python -BackendConsumerPassword "<senha-mqtt-backend-consumer>"
   ```

6. Alternativa manual para teste simulado:

   ```powershell
   $env:MQTT_PASSWORD="<definir fora do Git>"
   .\.venv\Scripts\python lab\legitimate-traffic\test_subscriber.py --expected-count 2
   ```

   Em outro terminal:

   ```powershell
   $env:MQTT_PASSWORD="<definir fora do Git>"
   .\.venv\Scripts\python lab\legitimate-traffic\simulate_poste.py --device poste-2 --count 2 --interval 1 --exercise-reconnect
   ```

7. Depois de aprovar sensor/pinagem do Poste 1, implementar leitura real em `readEnvironment()`.
8. Instalar PlatformIO e validar firmware:

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

- `30132e7 Add backend MQTT consumer credentials and ACL`
- `d92120c Expand synthetic MQTT simulator`
- `e72790f Merge branch 'main' into iot-mqtt`
- `c7aa9e0 Add IoT MQTT lab delivery`
- `b87f592 docs: prepare first delivery contracts`

## Encerramento em 2026-09-17

Estado final da area `iot-mqtt`:

- Worktree usada: `D:\Projetos\harpisense-worktrees\iot-mqtt`.
- Branch confirmada: `iot-mqtt`.
- Remoto confirmado: `origin` aponta para `https://github.com/originalrafaela/harpisense.git`.
- Implementacao existente preservada: simulador, firmware ESP32 e configuracao do broker foram mantidos.
- Nao houve alteracao em `main`, contratos compartilhados ou arquivos de `backend-data`.

Resumo implementado:

- Simulador sintetico configuravel preserva o contrato MQTT, suporta multiplos postes, IDs configuraveis, intervalo, duracao, semente, reconexao e geracao JSONL local com metadados sinteticos fora do payload compartilhado.
- Firmware do Poste 1 permanece publicando no topico contratado de ambiente, sem inventar sensor, pinagem ou leitura fisica.
- Broker Mosquitto permanece com autenticacao obrigatoria, password file local ignorado pelo Git e ACLs separadas.
- Usuario `harpisense_backend_consumer` foi adicionado como consumidor MQTT dedicado do backend.
- ACL do `harpisense_backend_consumer`: somente leitura em `harpisense/v1/telemetry/#`; sem publicacao e sem acesso a `harpisense/v1/security/#`.
- Provisionamento de credenciais exige `HARPISENSE_BACKEND_CONSUMER_PASSWORD`, nao versiona senha do consumidor backend e nao sobrescreve `mqtt/config/passwords` sem `--force`.
- Credenciais seguem separadas entre publicador IoT, subscriber de teste e consumidor backend.

Testes e verificacoes realmente executados nesta rodada:

- `git branch --show-current`
  - Resultado: `iot-mqtt`.
- `git remote -v`
  - Resultado: `origin` em `https://github.com/originalrafaela/harpisense.git` para fetch e push.
- `git status --short`
  - Resultado antes do resumo: limpo.
- `git diff --check`
  - Resultado: sem erros; apenas avisos esperados de CRLF do Windows.
- Parser PowerShell de `tests\integration\run_mqtt_smoke.ps1`
  - Resultado: `run_mqtt_smoke.ps1 parse OK`.
- Parser PowerShell de `tests\integration\test_mqtt_backend_consumer_acl.ps1`
  - Resultado: `test_mqtt_backend_consumer_acl.ps1 parse OK`.
- `docker compose -f mqtt\docker-compose.yml --profile init config`
  - Resultado: Compose renderizado com sucesso; houve aviso de acesso ao `C:\Users\amara\.docker\config.json`, mas codigo de saida foi 0.
- `docker ps`
  - Resultado: falhou porque o daemon Docker nao estava ativo em `npipe:////./pipe/docker_engine`.

Testes preparados, mas nao executados:

- `.\tests\integration\test_mqtt_backend_consumer_acl.ps1 -BackendConsumerPassword "<senha-mqtt-backend-consumer>"`
- `.\tests\integration\run_mqtt_smoke.ps1 -Python .\.venv\Scripts\python -BackendConsumerPassword "<senha-mqtt-backend-consumer>"`
- `.\.venv\Scripts\python -m pytest tests\integration\test_mqtt_contract.py`
- Build e upload do firmware com PlatformIO.
- Validacao fisica com ESP32 e broker real.

Pendencias separadas:

- Broker real: validar publicacao/assinatura MQTT fim a fim e validar ACLs reais do `harpisense_backend_consumer` contra Mosquitto.
- Docker: iniciar Docker Desktop ou disponibilizar alternativa local; no ambiente atual `docker ps` nao conecta ao daemon.
- Python: instalar Python e criar `.venv`; `py --version` retornou `No installed Python found!` e `python` nao estava no PATH.
- ESP32: conectar hardware fisico para build/upload/monitoramento e teste real.
- Sensores: definir sensor fisico aprovado para temperatura/umidade antes de implementar leitura real.
- Pinagem: aprovar pinagem do Poste 1 antes de alterar firmware.
- NTP: validar sincronizacao/estrategia de tempo no dispositivo fisico antes de tratar timestamps de hardware como leitura final.

Proximo passo para amanha:

1. Ativar Docker Desktop.
2. Provisionar o password file com senha local nao versionada do consumidor backend.
3. Subir Mosquitto.
4. Executar `test_mqtt_backend_consumer_acl.ps1`.
5. Instalar Python e executar os testes do simulador/contrato.

## Retomada auditada em 2026-10-31

- Entrada da sessão: raiz D:\Projetos\tcc - harpisense, branch main em 9d58e69. Nenhum commit feito na main. Após fetch, main está 3 commits atrás de origin/main (39720e4); nenhuma integração realizada.
- Worktree IoT real: D:\Projetos\tcc - harpisense\harpisense-worktrees\iot-mqtt; branch iot-mqtt em 30132e7787a1f481db576f2386cd2b09d9d31912. Consulta GitHub confirmou esse mesmo SHA remoto antes deste registro.
- Cadastro da worktree ainda aponta ao caminho antigo e aparece prunable. Nenhum reparo, prune, reset, remoção ou recriação realizado. Git -C consegue ler a worktree.
- Inventário IoT: somente este documento estava modificado, já staged; nenhum arquivo não rastreado ou ignorado listado. A raiz contém documentos, referencias/ e outras worktrees não rastreados, preservados integralmente.
- Implementação já salva: c7aa9e0 (entrega inicial), d92120c (simulador sintético) e 30132e7 (credenciais externas e ACL de consumidor). Não havia implementação adicional pendente no índice ou na árvore IoT.
- Lido o trecho IoT/MQTT de docs/ENCAMINHAMENTOS_CONSOLIDADOS_20261031.md na worktree frontend-backend-autonomia. Base exata da próxima integração isolada: 9e4467ea6d57726a9fc65ab88e5f414f9a69c7cb, branch feat/frontend-backend-autonomia, resolvida localmente. Os três arquivos de iot/esp32/poste1 são idênticos entre essa base e iot-mqtt (diff vazio). Este commit documental não inicia essa integração.
- Precedência: entregas aprovadas em referencias/versão_v2; componentes sem atualização continuam em referencias/Versões corretas. P05 proposal.v2 e P06 candidate.v2 foram lidos e continuam propostas, não contratos homologados.
- Preservar Poste 2: harpisense/poste2/telemetry, device_id=poste2, assinatura QoS 1 e ID poste2- + SHA-256(tópico UTF-8 + byte nulo + payload bruto). Poste 1 mantém identidade harpisense.poste.poste-1 e tópico histórico environment, com credencial/ACL/client ID próprios; não habilitar publicação operacional.
- Interrupção funcional: reconciliação de sensor/envelope e matriz de campos, tipos, unidades, identidade, tópico, ACL, tempo e deduplicação ainda não entregues. Adaptador adicional do Poste 1, rejeição de identidade trocada e regressão do Poste 2 permanecem pendentes. O firmware histórico ainda usa timestamp 1970 sem NTP e gera novo ID por publicação; não está pronto para habilitação. Nenhuma correção de código realizada nesta retomada.
- Evidências históricas disponíveis neste documento: renderização Compose, parser dos scripts PowerShell e diff --check concluíram; MQTT/ACL real, smoke, pytest e build PlatformIO não têm aprovação registrada. Não repetir instruções operacionais antigas de setembro como próximo passo autorizado.
- Nesta retomada: inspeção Git, leitura dos contratos e diff --cached --check sem erros; nenhum teste funcional ou compilação executado. Revisado todo o delta documental: apenas placeholders e senha explicitamente demonstrativa de laboratório, sem credenciais operacionais no delta.
- Próxima tarefa: preparar, em integração isolada baseada no SHA aprovado, a matriz de compatibilidade para decisão de contrato, reutilizando o firmware existente. VMs, broker, consumidor e placa não foram alterados nesta rodada.
