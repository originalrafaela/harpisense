# Adaptador mínimo Poste 1 — entrega Backend Data

Base confirmada antes da edição: `9e4467ea6d57726a9fc65ab88e5f414f9a69c7cb`,
linha `feat/frontend-backend-autonomia`. Branch própria: `feat/poste1-input-adapter`.
Responsabilidade conforme `DECISAO_CONTRATO_POSTE1_20261031.md`: Backend Data
implementa entrada/Record/store e testes; IoT mantém firmware, relógio e fila.
Arquivos desta entrega: `backend/delivery/mqtt_input.py`,
`backend/delivery_tests/test_mqtt_input.py` e este guia. Nenhuma alteração de
gerenciador de configurações, schema P03, store, migração, broker ou VM.

A decisão foi lida na worktree `frontend-backend-autonomia/docs`, ainda não
versionada naquela base. SHA256 do documento consultado:
`233da21a2d55d81e6f5524e5f0bf73a661b163dc8407371a4acdc815fe6e14dc`.
O arquiteto deve versionar esse documento na integração; esta entrega não inclui
os demais arquivos locais daquela worktree.

## Referências e dependência P06

Precedência aplicada: `referencias/versão_v2` (Versao_v2), seguida de
`referencias/Versões corretas` para componentes sem atualização. Foram consultados
P03 `CONTRATOS_OFICIAIS.md`, P05 `CONTRATO_TELEMETRIA_E_COMPATIBILIDADE.md`, P06
core/schema/política de tempo, P07 README e P11 `CONTRATOS_API_E_COMPATIBILIDADE.md`.
O README do Backend Operacional v1 em Versões corretas também foi consultado:
o componente continua disponível, mas não substitui a entrada de telemetria.
P03 permanece fonte única dos cinco registros de segurança, com proveniência
em `backend/domain/ORIGINS.json`; telemetria não vira sexto registro canônico.

Dependência externa identificada, sem cópia de schema ou do loop/SQLite P07:

`referencias/versão_v2/06_Telemetria_MQTT/HarpiSense_Etapa06_Telemetria_MQTT_v2/06_Telemetria_MQTT`

| Arquivo P06 | SHA256 |
| --- | --- |
| telemetry_contract/core.py | 17b9f07cb0eb80e1a2ca0fa945099b21571aea33ac1f711ae12dc4412d6264c2 |
| schema/telemetry.candidate.v2.schema.json | 4766cedcd8d0f0329e4fc85d5f450f8be073fbd1cec1a9bf878812dbf767a077 |

O pacote é fornecido pelo conjunto aprovado de referências, não está no Git
desta branch. Disponibilizar a pasta inteira no PYTHONPATH, incluindo `schema/`;
instalar seu requirements.txt (jsonschema 4.25.1, paho-mqtt 2.1.0). Ausência da
dependência impede inicialização com Poste 1 habilitado. Com flag fechada, não
importa P06. O perfil local complementa o core sem alterar seus arquivos.

## Integração aos callbacks existentes (revisão do arquiteto)

O consumidor operacional observado está no documento sanitizado
`docs/continuity/2026-10-31/mqtt-consumer-current.sanitized.txt` da worktree do
arquiteto. Esse serviço não está versionado como executável nesta linha. Por
isso o adaptador fornece callbacks para ligação explícita, sem iniciar outro
cliente MQTT, abrir conexão ou descobrir credenciais.

Na inicialização do consumidor existente, reutilizar seu `store`, sua função de
auditoria segura e seu `Record` P11:

```python
from delivery.mqtt_input import TelemetryInput

# Valor booleano explícito; permanece False nesta entrega.
# Não usar bool(os.getenv(...)), pois bool('false') é True.
input_adapter = TelemetryInput(
    store, emit_audit_safely, poste1_enabled=False, record_factory=Record,
)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print('Falha MQTT', flush=True)
        return
    input_adapter.subscribe(client)

def on_message(client, userdata, message):
    try:
        outcome = input_adapter.on_message(client, userdata, message)
        print(f'Ingestão MQTT: {outcome}', flush=True)
    except Exception as exc:
        # Erros de persistência/auditoria não são duplicatas. Não imprimir DSN,
        # payload, str(exc) ou credenciais no log operacional.
        print(f'Erro operacional MQTT: {type(exc).__name__}', flush=True)

client.on_connect = on_connect
client.on_message = on_message
```

Preservar configuração/conexão/TLS e tratamento de auditoria do consumidor.
O exemplo não autoriza iniciar o serviço nem habilitar o tópico novo. A função
`subscribe` conserva Poste 2 em QoS 1; só adiciona o tópico exato do Poste 1 se
habilitado. Isso não eleva o QoS 0 do publicador nem confirma entrega física.

Antes de futura ativação, conferir que o store real corresponde ao mecanismo
testado: `backend/delivery/postgres_store.py` nesta base. Comparado estaticamente
com `70ab079:backend/p11_postgresql/postgres_store.py`, difere apenas pelo timeout
de conexão. Ambos usam lock advisory transacional, comparação canônica do JSON
e origem e erro `immutable revision conflict`. Não houve leitura da VM nesta
rodada: a equivalência da instalação alvo continua gate do arquiteto.

## Comportamento

- Dispatch exato: Poste 1 apenas no tópico completo decidido; Poste 2 apenas
  `harpisense/poste2/telemetry`, com `device_id=poste2`. Tópico desconhecido ou
  identidade divergente gera `validation_failure`, sem gravação.
- Poste 1: UTF-8 estrito, limite recebido e canônico de 1024 bytes, JSON objeto,
  sem duplicatas/chaves extras/NaN/Infinity; validação core P06 seguida do perfil
  físico. `sequence` obrigatório inteiro real 0..9007199254740991; ID de firmware
  com identidade, boot 16 hex e sequência correspondente, até 64 caracteres.
  ADC inteiro real 0..4095 ou null coerente com qualidade; comando LED booleano;
  calibração omitida. LED comandado não confirma acendimento físico, ADC não é lux.
- `observed_at` é instante UTC com Z, conservado literalmente. Atraso e fora de
  ordem são aceitos; não há filtro de frescor nem rejeição por sequência menor
  recebida depois. Não há relógio de recepção inserido no payload. Validade NTP
  da coleta e sequência crescente por boot são responsabilidades do firmware;
  o adaptador não consegue atestar essas propriedades remotamente.
- `Record.id = poste1- + SHA256(device_id UTF-8 + NUL + message_id UTF-8)`,
  revisão 1, origem trusted-service, envelope sem campos acrescentados.
- `store.insert('telemetry', record)` decide duplicata por conteúdo e origem.
  False gera `duplicate_message`; somente o erro imutável conhecido gera
  `identifier_conflict`. Não sobrescreve, não tenta revisão 2; demais erros
  propagam ao tratamento operacional. Auditoria recebe códigos, sem payload.
- Poste 2 conserva parser JSON anterior, conteúdo e ID sobre tópico + NUL +
  bytes originais. Whitespace diferente continua gerando IDs distintos.
  Não recebe tradução ao envelope físico.
- `created_at` continua horário de persistência, não de coleta; retry e conflito
  não alteram esse horário nem conteúdo. Nenhuma nova coluna/tabela/índice.

Checagem tópico/payload não identifica o principal do publisher. TLS com CA e
hostname, identidade do broker, credencial externa e ACL exata precisam de prova
separada antes de habilitar o Poste 1. Fila RAM, NTP, perda de energia, hardware
e QoS não foram ensaiados por estes testes. Telemetria não autoriza defesa.

## Testes reproduzíveis

Python 3.12 em `.venv`, sem instalação global. Da raiz desta worktree, definir
`$p06` para a pasta aprovada acima (absoluta):

```powershell
& C:/Users/amara/.local/bin/python3.12.exe -m venv .venv
.venv/Scripts/python.exe -m pip install -r "$p06/requirements.txt" -r backend/delivery/requirements.txt
$env:PYTHONPATH = "backend;$p06"
# Segredo abaixo pertence exclusivamente à fixture descartável local.
docker run -d --name harpisense-poste1-input-test -p 127.0.0.1:55442:5432 -e POSTGRES_USER=poste1_fixture -e POSTGRES_DB=poste1_fixture -e POSTGRES_PASSWORD=isolated-poste1-fixture postgres:18.6
$env:HARPISENSE_POSTE1_TEST_DSN = 'postgresql://poste1_fixture:isolated-poste1-fixture@127.0.0.1:55442/poste1_fixture'
.venv/Scripts/python.exe -m unittest discover -s backend/delivery_tests -p test_mqtt_input.py -v
.venv/Scripts/python.exe -m unittest discover -s "$p06/tests" -v
docker rm -fv harpisense-poste1-input-test
```

O teste recusa banco diferente de `poste1_fixture`; bootstrap usa o SQL local
existente, apenas na fixture descartável. Sem DSN, os testes PostgreSQL são
explicitamente pulados, o que não comprova persistência.

Resultado desta entrega: 10 testes do adaptador aprovados, dos quais 4 em
PostgreSQL 18.6 real; mais 21 testes P06 aprovados. Incluem limites/tipos/bytes,
identidade/tópico, campos obrigatórios/extras/duplicados, horário inválido,
qualidade, flag fechada, duplicata e conflito persistentes e concorrentes,
preservação de created_at/observed_at e regressão do Poste 2 com whitespace.
Nenhuma VM, broker, cliente físico ou gerenciador de configurações foi alterado.
