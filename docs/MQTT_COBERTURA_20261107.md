# Cobertura MQTT — revisão isolada de 2026-11-07

Branch `feat/mqtt-observational-coverage`, base
`a8fef1f5810ad5077658a29fe2aa407ffd21df6d`. Nenhuma mudança na worktree
native-installers, prévia 5174, dispositivos, serviços existentes ou instaladores.

## Comportamento

A rota autenticada existente `/api/v1/config/mqtt/status` separa conexão,
assinatura e amostra recebida. SUBACK sem mensagem mantém dispositivo
`not_verified`. O heartbeat continua com validade de 45 segundos; telemetria
tem política explícita de 120 segundos, substituível no estado instalado por
`mqtt.telemetry_max_age_seconds` inteiro positivo. Esse prazo não representa
contrato de amostragem de todos os sensores.

`coverage.scope=mqtt_telemetry` cobre exclusivamente a identidade `poste2`
vinculada à ACL desta composição. `complete` significa somente essa cobertura
restrita; não autoriza mudança de perfil nem comprova ausência de ataques.
`incident_state` permanece `unknown`. Sem amostra há cobertura `unknown`;
com amostra histórica indisponível/vencida há cobertura `partial`.

O horário exibido é de primeira ingestão da revisão de telemetria no PostgreSQL,
com fuso (`timestamp_basis=consumer_received_at`), não o horário declarado pelo
sensor. A atualização usa kind/ID/revisão 1 exatos. Retransmissão QoS não renova
esse horário; revisão antiga não substitui amostra mais recente. Perda de
comunicação conserva message_id/projection_id e nunca altera incidentes.

O JSON original da origem continua imutável na projeção. A observação não infere
origem física por autenticação MQTT: `source_origin=unknown`. Faltam vínculos
validados com janela/detecção/incidente e resolução de origem pela cadeia de
contratos; são declarados em `missing_links`. Não há vínculo por aproximação
de horários ou nomes. Não foi criado ativo nem nome de exibição artificial.

## Evidência desta alteração

Sete testes unitários passaram: conexão sem mensagem, escopo restrito,
telemetria vencida, desconexão/reconexão preservando identidade, heartbeat
vencido/futuro, telemetria futura e política inválida/observação ausente.

[Ensaio real Windows](evidence/mqtt-coverage/win32.json): oito verificações
aprovadas com Python existente, PostgreSQL e Mosquitto nativos, TLS/autenticação,
consumidor do produto e banco descartável em portas livres. Inclui parada e
reinício do broker, reconexão e assinatura automáticas, deduplicação e origem
SIMULATED preservada no PostgreSQL. Somente publicador de aceitação isolado;
nenhum ataque ou publicação em dispositivos do usuário. O envelhecimento
artificial de amostra ocorreu exclusivamente nesse banco descartável.

Reprodução de desenvolvimento, na worktree:

```powershell
..\native-installers\.venv\Scripts\python.exe packaging/native/acceptance_mqtt_coverage.py --postgres-bin D:/Programas/PostgreSQL/bin --mosquitto D:/Programas/Mosquitto/mosquitto.exe
```

## Dependências e aceite por ambiente

Nenhuma dependência ou migração nova. A mudança usa psycopg já declarado e a
tabela existente. Windows já empacota PostgreSQL/Mosquitto/WinSW/VC++; Ubuntu
declara PostgreSQL16/Mosquitto/Python/CA via apt e wheels Python no pacote.
Os builders existentes incluem `native_server` (Windows via coleta PyInstaller;
Ubuntu por cópia do pacote). Não foi gerado novo instalador: os artefatos
publicados ainda não contêm esta alteração.

| Ambiente | Resultado desta revisão | Falta |
| --- | --- | --- |
| Prévia 5174 | Preservada; não alterada nem homologada | Integrar contrato no Frontend/Backend/Configurações e revisar IDs reais |
| Windows existente | Ensaio TLS/PostgreSQL e reconexão aprovado, sem Docker | Build congelado, instalador e máquina limpa, reboot, serviços automáticos, painel/login |
| Windows limpo | Não executado | Todo aceite separado desta revisão |
| Ubuntu | Script de ensaio aceita binários sem sufixo .exe; não executado | Build, ingestão/reconexão real, instalação limpa, reboot, serviços e painel/login |

Broker local escuta somente loopback. Conectividade LAN, certificados/ACL de
dispositivos externos, Poste 1 habilitado e cobertura de captura/rede continuam
ausências explícitas. Nada nesta entrega depende apenas de Docker.

Coordenação via skill Maestri: Backend Data confirmou não editar observation.py
e solicitou origem/ID/horário/freshness/coverage explícitos. O CLI identifica
este terminal como Arquiteto e o pedido dirigido a `HarpiSense Arquiteto`
retornou `No connection`; houve também mensagem de coordenação retornando ao
próprio terminal. Relatório deve ser reencaminhado quando o roteamento correto
estiver disponível, sem interpretar telas/approvals de outros agentes como
autorização. Não houve alteração de arquivos das demais worktrees.
