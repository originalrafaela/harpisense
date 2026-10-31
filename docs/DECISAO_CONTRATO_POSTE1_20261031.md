# Decisão do arquiteto — contrato de entrada Poste 1

31/10/2026. Decisão documental para implementação e teste isolados; publicação
operacional permanece desabilitada. Não autoriza implantação, alteração do broker,
ACL, rede, firmware operacional ou do caminho Poste 2.

Entregue ao IoT/MQTT via skill maestri nesta rodada; agente confirmou leitura e
recebimento, preservação do Poste 2 e nenhuma implementação iniciada.

## Base e compatibilidade

Matriz recebida e publicação conferida: docs/poste1-compatibility-20261031,
fe88645fee55a9922a3633ff941219f7cb15d176, pai exato
9e4467ea6d57726a9fc65ab88e5f414f9a69c7cb. Documento lido via git show,
sem checkout, merge ou alteração na worktree IoT.

Precedência: referencias/versão_v2 (Versao_v2 do operador), e depois
referencias/Versões corretas para componentes sem atualização. A falta de um
componente em V2 não significa ausência. Proposta dentro de pacote aprovado
não se torna contrato homologado apenas pela localização.

Fontes conferidas na raiz do repositório:

- P03: referencias/versão_v2/03_Contratos/HarpiSense_Etapa03_Contratos_Catalogo_V2/03_Contratos/CONTRATOS_OFICIAIS.md e base_consolidada_atualizada/harpisense_contracts/schema_source.py.
- P05: referencias/versão_v2/05_Firmware_ESP32/HarpiSense_Etapa05_Firmware_ESP32_v2/05_Firmware_ESP32/CONTRATO_TELEMETRIA_E_COMPATIBILIDADE.md.
- P06: referencias/versão_v2/06_Telemetria_MQTT/HarpiSense_Etapa06_Telemetria_MQTT_v2/06_Telemetria_MQTT/: schema/telemetry.candidate.v2.schema.json, telemetry_contract/core.py, POLITICA_ENTREGA_TEMPO_E_IDEMPOTENCIA.md, requirements.txt e tests/test_contract.py.
- P07: envelope e parser compartilhados com P06, conforme matriz; SQLite é referência de pacote, não substituição do PostgreSQL ativo.
- P11: referencias/versão_v2/11_Backend_Dashboard_BitNet/HarpiSense_Pacote11_Backend_Dashboard_BitNet_v2/CONTRATOS_API_E_COMPATIBILIDADE.md.
- Consumidor observado: docs/continuity/2026-10-31/mqtt-consumer-current.sanitized.txt nesta worktree; não executado. Implementação PostgreSQL lida em ../p11-postgres-pagination/backend/p11_postgresql/postgres_store.py e backend/delivery/postgres_store.py.

P03 define detection/explanation/incident/decision/execution, não telemetria ESP32.
O envelope abaixo é aprovado como perfil de entrada do Poste 1 para desenvolvimento
isolado, sem promovê-lo a sexto registro canônico, evidência de segurança ou
autorização de defesa. Não modifica a fonte única P03 nem renomeia schemas.
P11 é projeção: a aceitação de Record não substitui a validação da entrada.

## Decisão concreta para IoT

| Item | Decisão |
| --- | --- |
| Identidade | device_id exatamente harpisense.poste.poste-1 |
| Tópico completo | harpisense/v1/telemetry/harpisense.poste.poste-1/ldr |
| Esquema no fio | schema_version exatamente harpisense.telemetry.candidate.v2; reutilizar o schema P06/P07 existente, sem inventar versão oficial ou alterar o compartilhado |
| Perfil local | Poste 1 físico LDR/LED, revisão documental 1 deste documento; não acrescentar profile_version ao JSON |
| Sensor | sensor_type=ldr; sem temperature/humidity/environment ou lux fictícios |
| Origem | status.origin_type=PHYSICAL; não aceitar SIMULATED neste tópico |
| Entrega inicial | Publish QoS 0 com cliente atual, retain=false; subscribe QoS 1 não eleva QoS do publicador. Melhor esforço, sem promessa de persistência/exatamente uma vez |
| Autenticação | Usuário exclusivo do Poste 1 e segredo externo ao Git; client ID estável poste-1; ACL futura de escrita somente no tópico exato; leitura técnica adicional somente nesse tópico |
| Transporte para habilitação | TLS com CA e verificação de hostname e identidade do broker, implementado e testado no cliente; sem exceção implícita para 1883. Endereço/porta/TLS/ACL reais dependem de proposta posterior; broker atual e Poste 2 permanecem intactos |

UTF-8 JSON objeto, máximo 1024 bytes recebidos, sem chaves extras ou duplicadas,
sem NaN/Infinity; limites também no JSON canônico. Validar pelo core P06 e depois
pelo perfil estrito. Strings/inteiros/booleanos devem ter tipos reais: bool não é ADC
ou sequence; não aceitar decimal 1.0 como inteiro no perfil de entrada.

Campos obrigatórios:

- schema_version, device_id, sensor_type conforme tabela.
- message_id: até 64 caracteres, padrão P06 [A-Za-z0-9_.-]+;
  formato do firmware device_id + '-' + boot aleatório 16 hex + '-' + sequence.
  sequence inteiro 0..9007199254740991, crescente por boot; novo boot antes de
  esgotar a faixa. Reenvio conserva message_id, sequence, observed_at e bytes.
- observed_at: coleta em UTC, serializada com Z e validada como instante.
  Sem sincronização NTP válida não publicar nem reconstruir hora de coleta
  usando horário posterior; contar a perda local. Nunca fallback 1970.
- measurements.ldr_adc_raw: inteiro 0..4095, ADC explicitamente 12 bits;
  null para leitura indisponível ou fora da faixa. Não saturar silenciosamente.
- measurements.led_commanded_on: booleano do comando local; não prova LED físico.
- status.origin_type=PHYSICAL, status.reading_unit=adc_raw.
- status.reading_quality=RAW_UNCALIBRATED com inteiro; UNAVAILABLE ou OUT_OF_RANGE
  com null. Zero e 4095 são valores possíveis, não diagnóstico de desconexão.
- status.calibration_version omitido até existir calibração aprovada.

GPIOs, circuito, sentido da leitura, limiares e histerese ainda não homologados.
Não inferir essas propriedades da placa de 30 pinos.

### Horário, fila e recepção

Fila RAM limitada a 8 amostras, descartar a mais antiga ao lotar e contabilizar;
idade máxima local 120 segundos desde a coleta, medida por relógio monotônico.
Após esse prazo descartar e contar; não renovar horário/ID em retry. Remover da
fila após aceitação local do publish QoS 0 não comprova recepção pelo broker.
Reboot perde fila; não alegar durabilidade. Sem fila ou relógio válidos, registrar
perdas locais em vez de fabricar amostras.

No backend, atraso e fora de ordem não são erro automático de schema: preservar
observed_at e não rejuvenescê-lo. created_at existente é horário de persistência,
não de coleta. Não inserir received_at variável no payload deduplicado; se houver
metadado de recepção já suportado, mantê-lo separado e imutável. Não inventar
campo/tabela para isso nesta etapa. Limites futuros de frescor para uso em decisão
exigem contexto/proveniência; esta telemetria não habilita defesa por si só.

## Ajuste mínimo — responsável Backend Data

Adicionar adaptador de entrada específico ao consumidor existente, fechado por
flag por padrão: dispatch por tópico exato, parse estrito, validação P06 e perfil
acima, construção do Record existente e store.insert('telemetry', record).
Reutilizar o pacote de contrato P06 como dependência identificada, sem copiar
uma fonte de schema concorrente; não importar o loop MQTT/SQLite P07.

Poste 1: Record.id = 'poste1-' + SHA256(device_id UTF-8 + NUL + message_id UTF-8),
revision=1, source='trusted-service', data=envelope validado sem campos voláteis.
message_id inclui a identidade para compatibilidade com a referência P06 de
unicidade por message_id; namespace do Record impede colisão com Poste 2.
Fingerprint P06 SHA256(encode(payload)) pode ser calculado para diagnóstico,
sem novo índice ou coluna: a decisão persistente reutiliza comparação canônica
de conteúdo e source em PostgresStore.insert, sob advisory lock transacional.
Retorno False = duplicate; ValueError de revisão imutável conflitante =
identifier_conflict, auditado sem sobrescrever nem tentar revision=2.
Outros erros de persistência são falhas operacionais, nunca duplicatas.
Não introduzir SQLite, tabela de deduplicação ou pipeline paralelo.

Preservar integralmente o handler Poste 2: tópico harpisense/poste2/telemetry,
device_id=poste2, payload original e Record.id 'poste2-' + SHA256(tópico UTF-8
+ NUL + payload bruto), revisão 1. Não traduzir Poste 2 ao novo envelope.
Dispatch deve impedir identidade trocada nos dois tópicos. Não alargar a
condição de identidade do handler antigo para aceitar Poste 1 arbitrariamente.

O store local já fornece os mecanismos citados; antes de implementação/ativação,
Backend Data deve confirmar a mesma implementação na base de integração/runtime
alvo. Essa leitura estática não equivale a ensaio do banco ativo.

IoT/MQTT cuida somente do firmware/serialização/configuração de exemplo e testes;
Backend Data cuida do adaptador e integração isolada ao store existente. Mudanças
de broker/credenciais/ACL exigem coordenação posterior, sem efeito colateral no
Poste 2. Assinante MQTT não recebe o principal autenticado do publisher: ACL no
broker autentica a origem autorizada; checar tópico/payload não substitui isso.

## Validação isolada e gates

Usar Python 3.12 em venv, dependências fixadas pelo requirements.txt P06;
não instalar no Python global. A partir da raiz, no PowerShell:

```powershell
$p06 = (Resolve-Path 'referencias/versão_v2/06_Telemetria_MQTT/HarpiSense_Etapa06_Telemetria_MQTT_v2/06_Telemetria_MQTT').Path
$venv = Join-Path $PWD 'harpisense-worktrees/frontend-backend-autonomia/frontend/local-evidence/poste1-contract-venv'
& C:/Users/amara/.local/bin/python3.12.exe -m venv $venv
& "$venv/Scripts/python.exe" -m pip install -r "$p06/requirements.txt"
& "$venv/Scripts/python.exe" -m unittest discover -s "$p06/tests" -v
& "$venv/Scripts/python.exe" 'harpisense-worktrees/frontend-backend-autonomia/docs/continuity/2026-10-31/validate_poste1_contract_example.py' --p06 $p06
```

O script valida o exemplo da matriz exata publicada fe88645 e o tópico decidido,
sem acessar broker, firmware, banco ou VM. Teste do core não comprova o adaptador
estrito ainda não implementado: Backend deve provar rejeições de identidade,
tópico, tipos, faixa ADC, UTC inválido, bytes/chaves duplicadas/extras e tamanho;
duplicata/conflito/concorrência em PostgreSQL isolado e regressão byte a byte do
Poste 2 (inclusive whitespace). IoT deve testar hardware/relógio/fila/queda de
energia e publicação fechada. TLS e ACL separados devem ser comprovados antes
de habilitar. Nenhuma dessas provas é substituída por aceite documental.

Resultado executado nesta rodada: 21 testes P06 aprovados; exemplo sintético da
matriz fe88645 aprovado pelo core P06 com o tópico completo decidido. Fingerprint
do exemplo: a63cc464fce7ce900db78381743d1519b116ce1877730b239384f26aa20ed582.
Ambiente virtual Python 3.12 local, jsonschema 4.25.1 e paho-mqtt 2.1.0 conforme
requirements.txt; Python global preservado. Isso resolve a pendência de importação
do exemplo, sem comprovar adaptador, hardware, persistência ativa ou TLS/ACL.

## Gerenciador e continuidade

GitHub confirmou feat/config-manager-stage1 em
edd0cb7e1d92e14a2518790db61a7b0c0ffef8dd nesta rodada: entrega disponível
para integração, ainda não operacional. Supera a pendência anterior de push.
Sem API/aplicadores/migração/ativação autorizados; preservar mínimo de senha 8
de 9e4467e na integração futura. mqtt_tls_mode=required não descreve o fluxo
1883 atual, que não foi migrado.

Próxima alteração mínima: Backend Data preparar adaptador de entrada e testes
isolados sobre a linha de integração aprovada, com flag fechada; IoT adequar
firmware somente ao perfil decidido e ainda sem publicar. Não executar esses
ajustes de terceiros nesta entrega documental. Aceite de login no portal e
rotas do Poste 2 continuam pendentes independentes, sem bloquear esta decisão.
