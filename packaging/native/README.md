# Instaladores nativos — primeira candidata

Branch `feat/native-installers`. A candidata instala a central; não constitui
homologação em sistema limpo. Frontend compilado, mesma aplicação Python para
Windows 11 x64 e Ubuntu 24.04 x86_64. Docker, WSL, VMware, VS Code, Wokwi,
Node e Vite não são requisitos de execução do produto.

## Artefatos

Na raiz da worktree, após build:

- `dist/HarpiSense-Setup-Windows-x64.exe`: instalador gráfico com elevação UAC,
  runtime Python congelado, PostgreSQL 18.4, Mosquitto 2.1.2, WinSW 2.12.0 e
  redistribuível Microsoft VC++ x64. Nenhum download na máquina de destino.
- `dist/HarpiSense-Setup-Ubuntu-24.04-x86_64.run`: instalador nativo com wheels
  Linux/Python 3.12 incluídos e frontend compilado. Requer Internet para pacotes
  do repositório Ubuntu (`postgresql-16`, `mosquitto`, Python/venv e CA).
- Cada arquivo tem `.sha256`. O manifesto Windows inclui hash de cada arquivo
  do payload e suas origens; o Ubuntu inclui `WHEELS.sha256` e versões fixadas.

Windows: abrir o EXE, escolher **Instalar e gerenciar broker local** (padrão),
instalar, copiar o segredo local mostrado somente no formulário de primeiro
acesso, abrir o painel, cadastrar conta/TOTP e guardar os códigos de recuperação.
Nos próximos usos, abrir **HarpiSense** pelo menu Iniciar. Os serviços iniciam
automaticamente. **HarpiSense Primeiro acesso** renova o grant local sob UAC
somente enquanto não há conta; com conta existente, encaminha ao login.

Ubuntu: executar o `.run` como administrador, por exemplo:

```sh
chmod +x HarpiSense-Setup-Ubuntu-24.04-x86_64.run
sudo ./HarpiSense-Setup-Ubuntu-24.04-x86_64.run
```

O instalador entrega o segredo em seu console local autorizado. Depois abrir
**HarpiSense** no menu de aplicações ou `http://127.0.0.1:18080`. O uso diário
não exige terminal nem reiniciar serviços manualmente. Se a instalação foi
iniciada sem console, o grant está no arquivo privado
`/var/lib/harpisense/bootstrap.secret`; a experiência gráfica de entrega desse
grant no Ubuntu ainda precisa ser validada/melhorada em alvo limpo.

Grant expira em 10 minutos. Renovação administrativa Ubuntu antes da criação da
conta, usando código do produto, nunca helper de fixture:

```sh
sudo env PYTHONPATH=/opt/harpisense/backend:/opt/harpisense/backend/domain:/opt/harpisense/genai \
  /opt/harpisense/venv/bin/python /opt/harpisense/packaging/native/entry.py grant \
  --state /var/lib/harpisense/state.json
```

## Isolamento, conflitos e persistência

Antes de escrever arquivos ou registrar serviços, o preflight verifica diretórios,
serviços existentes e portas. PostgreSQL/broker pré-existentes não são adotados,
reconfigurados ou substituídos. Em conflito, a instalação é recusada. Em modo
externo, a presença de um broker externo não autoriza administrá-lo.

Portas: painel/API `127.0.0.1:18080`; PostgreSQL `127.0.0.1:15432`;
Mosquitto TLS local `127.0.0.1:8883`. O preflight local também recusa `1883`
ocupada para evitar confusão com broker instalado. Não abre firewall.

O primeiro broker local atende loopback. Dispositivos em outra máquina precisam
de conectividade/broker externo com TLS/ACL configurados e verificados. Esta
candidata não anuncia conectividade LAN de sensores nem gera certificados LAN.

Windows: aplicação em `%ProgramFiles%/HarpiSense`, estado separado em
`%ProgramData%/HarpiSense`, ACL restrita a instalador/administradores, SYSTEM e
LocalService. Serviços `HarpiSensePostgres`, `HarpiSenseApi`,
`HarpiSenseMqtt`, `HarpiSenseBroker` (somente local), com dependências, reinício
em falha e início automático sob LocalService.

Ubuntu: aplicação `/opt/harpisense`, estado `/var/lib/harpisense`, usuário de
serviço `harpisense`, diretório 0700/arquivos 0600 e units systemd
`harpisense-postgres`, `harpisense-api`, `harpisense-mqtt` e
`harpisense-broker` (somente local). O cluster padrão vazio criado por apt nesta
invocação é parado; a central usa seu próprio cluster 15432. Instalação Ubuntu
com cluster ou broker anterior é recusada antes do apt.

Uma reinstalação encontra os diretórios e **recusa substituição antes de qualquer
escrita**. Não é um atualizador. Nunca remove conta, MFA, chave, configuração ou
projeções. Uma instalação parcial também é preservada para diagnóstico; não há
limpeza automática de dados. Atualização e desinstalação destrutiva ficam fora
desta primeira candidata.

Chave Fernet, credencial PostgreSQL, identidade do consumidor MQTT e identidade
do publicador são geradas separadamente. A aplicação PostgreSQL não é superuser.
`pg-admin.secret` tem custódia administrativa local. O operador não inventa
“senha de API”. Não guardar a chave MFA junto com dump público ou exportá-la ao
navegador. Conta humana é criada unicamente pelo fluxo publicado de bootstrap/MFA.

## Dois modos MQTT e observação real

Contrato base: [backend/config_manager/MQTT.md](../../backend/config_manager/MQTT.md),
commit de origem `5898cf6`. Modos `local_managed` e `external`.

Local: instalador copia/instala e inicia Mosquitto, TLS, identidades e ACL.
Consumidor `harpisense-consumer` só lê `harpisense/poste2/telemetry`;
publicador `poste2` só escreve esse tópico. Credencial do dispositivo fica no
arquivo privado `device-poste2.json`, entregue por operador autorizado.

Windows oferece a escolha gráfica de broker externo. Ubuntu aceita opção
avançada `--external-broker /caminho/privado/broker.json`, arquivo 0600 com
`host`, `port` (inteiro), `username`, `password`, `ca_file`. A credencial deve
ser uma identidade de consumidor já autorizada no broker, separada das
identidades de dispositivos. O instalador não emite comandos administrativos,
edita ACL ou configura serviços de terceiros. TLS, CONNACK e SUBACK são verificados.

A composição nativa injeta um observador na rota autenticada
`GET /api/v1/config/mqtt/status`. Sem esse observador, o comportamento original
`not_verified` é preservado. As operações web de aplicar/instalar/gerenciar
serviços continuam desabilitadas. Salvar `mqtt_broker_mode` não modifica o broker
ativo, não cria configuração efetiva e não altera `operational=false`.

Observações são persistidas em `hs_native_mqtt_observation`: CONNACK confirma
broker autenticado, SUBACK confirma assinatura do consumidor, heartbeat a cada
10 segundos expira em 45 segundos. Uma mensagem só é observada depois de inserção
ou duplicata confirmada pelo adaptador PostgreSQL. A resposta informa identidade,
message_id (ou hash do payload), projection_id, origem e horário.

O inventário observado nesta primeira versão é apenas o publicador `poste2`,
vinculado à ACL. Broker ativo + consumidor com SUBACK + inventário conhecido sem
mensagens produz `AWAITING_FIRST_MESSAGE`. Sem observador, sem SUBACK ou com
heartbeat antigo não se presume ausência de dispositivos. Última mensagem
histórica permanece identificada, mesmo quando a conexão não é mais comprovada.

## Build de desenvolvimento

Usar Python 3.13 no Windows, Node somente no build e ambiente Python isolado:

```powershell
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r packaging/native/requirements.txt pyinstaller==6.16.0 pip==25.3
uv pip install --python .venv/Scripts/python.exe -r packaging/native/runtime-windows.lock --require-hashes
cd frontend
npm.cmd ci --ignore-scripts
npm.cmd run build
cd ..
.venv/Scripts/python.exe packaging/native/build_windows.py --postgres-dir D:/Programas/PostgreSQL --mosquitto-dir D:/Programas/Mosquitto --winsw .native-build/vendor/WinSW-x64.exe --vc-redist .native-build/vendor/VC_redist.x64.exe
.venv/Scripts/python.exe packaging/native/build_ubuntu.py
```

Os diretórios de fornecedores são apenas fontes de **binários redistribuíveis**.
O empacotador seleciona explicitamente arquivos e nunca copia `data`,
`mosquitto.conf`, `passwords.txt`, configurações ou credenciais existentes.
Para reproduzir em outro computador, fornecer distribuições limpas equivalentes,
WinSW 2.12.0 e seu `LICENSE.txt` renomeado `WinSW-LICENSE.txt`, além do
redistribuível Microsoft oficial. Fontes:
[PostgreSQL](https://www.postgresql.org/download/windows/),
[Mosquitto](https://mosquitto.org/download/),
[WinSW](https://github.com/winsw/winsw/releases/tag/v2.12.0),
[Microsoft VC++](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).

## Evidência e limites

Ensaio real concluído **no Windows 11 existente**, com PostgreSQL 18.4,
Mosquitto 2.1.2 e Chromium 141, sem Docker, sem registrar serviços e sem tocar
nas VMs ou nos serviços do laboratório. Processos próprios em
`25432/28883/28080`; dados privados em `.native-test/<uuid>`.
Comando, com dependências de teste `playwright==1.56.0`, `httpx==0.28.1`:

```powershell
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe packaging/native/acceptance_windows.py --postgres-bin D:/Programas/PostgreSQL/bin --mosquitto D:/Programas/Mosquitto/mosquitto.exe
```

Para validar o runtime congelado, acrescentar
`--runtime .native-build/runtime/HarpiSense/HarpiSense.exe` após seu build.
O teste usa provisionamento/composição do produto com portas privadas, e não
importa `http_fixture`, `http_candidate` ou credenciais de testes anteriores.
Não é uma execução completa do instalador com registro de serviços.

[Resultado JSON](../../docs/evidence/native-installers/windows-native-result.json)
e screenshots antes/depois da mensagem no mesmo diretório. O ensaio verifica
bootstrap, TOTP inválido recusado, TOTP válido, códigos de recuperação, dashboard,
salvar/retomar, reinício dos processos/API/consumer/DB e novo login, MQTT TLS/ACL,
ausência de publicação, publicação identificável até PostgreSQL/API, modo externo
somente leitura, rascunho sem aplicação, observação vencida e recusa de reinstalação.
Publicação de aceitação não representa sensor físico, laboratório P08 ou RF/IF.

Resultado final: **23 verificações reais aprovadas com o executável congelado**,
incluindo preparação das migrações SQL embarcadas. Complementos: build/typecheck,
51 unitários frontend, 16 cenários de navegador da UI com fixtures e quatro
testes do contrato MQTT. Esses complementos não homologam instalação nativa.

**Bloqueio Windows limpo:** este host já possui PostgreSQL/Mosquitto do laboratório;
instalar aqui violaria o escopo e é recusado pelo preflight. Não houve reboot da
máquina nem verificação de serviços automáticos em alvo limpo.
**Bloqueio Ubuntu:** não foi disponibilizado alvo Ubuntu 24.04 limpo independente
das duas VMs do laboratório. O `.run` foi gerado, mas instalação/reboot/serviços
e recepção real nessa plataforma não foram executados.

Central instalada não comprova captura/IF/RF, firmware físico, defesa Linux ou
contenção Windows. A composição mantém `operational=false`, sem habilitar IPS.
