# Poste 1 — matriz e proposta para decisão do arquiteto

Data: 2026-10-31. Status: recomendação, sem homologação ou habilitação operacional.
Base Git exata: `9e4467ea6d57726a9fc65ab88e5f414f9a69c7cb`.
Branch documental: `docs/poste1-compatibility-20261031`.

## Decisão recomendada

Adotar para o Poste 1 o envelope LDR de P06/P07, ainda candidato, mantendo
`device_id=harpisense.poste.poste-1`. Propor o tópico explícito
`harpisense/v1/telemetry/harpisense.poste.poste-1/ldr`. A mudança do sufixo histórico
`environment` para `ldr` precisa de aprovação e provisionamento coordenado;
não é uma renomeação silenciosa. Não usar `poste1`, `poste2` ou `poste2-sim`
como substitutos da identidade existente.

Implementar futuramente um adaptador adicional e estrito para esse tópico,
sem relaxar o parser do Poste 2. Reutilizar ideias de fila/tempo do P05 e
validação do P06; não substituir árvores pelo pacote inteiro. P07 fornece
referência SQLite de desenvolvimento, não integração PostgreSQL pronta.

Hardware informado pelo operador: ESP-WROOM-32, placa de 30 pinos, LED e LDR.
Isso resolve o tipo de sensor, mas não confirma GPIOs, circuito divisor,
resistores, polaridade do LED, sentido do ADC, limiares ou calibração.
Não há temperatura/umidade medidas nem lux demonstrados.

## Fontes e precedência

Os caminhos abaixo são relativos à raiz `D:\Projetos\tcc - harpisense`.
Pacotes aprovados de `referencias/versão_v2` têm precedência; propostas internas
continuam propostas. Componentes sem atualização permanecem em
`referencias/Versões corretas`, sem presunção de ausência.

| Ref. | Fonte lida |
| --- | --- |
| A | `harpisense-worktrees/frontend-backend-autonomia/docs/ENCAMINHAMENTOS_CONSOLIDADOS_20261031.md`, trecho IoT/MQTT |
| F | Na base Git: `iot/esp32/poste1/src/main.cpp`, `include/config.example.h`, `platformio.ini`; `lab/legitimate-traffic/mqtt_contract.py`; `mqtt/config/aclfile` |
| P05 | `referencias/versão_v2/05_Firmware_ESP32/HarpiSense_Etapa05_Firmware_ESP32_v2/05_Firmware_ESP32/`: `firmware/src/main.cpp`, `firmware/include/config.example.h`, `CONTRATO_TELEMETRIA_E_COMPATIBILIDADE.md` |
| P06 | `referencias/versão_v2/06_Telemetria_MQTT/HarpiSense_Etapa06_Telemetria_MQTT_v2/06_Telemetria_MQTT/`: `schema/telemetry.candidate.v2.schema.json`, `telemetry_contract/core.py`, `POLITICA_ENTREGA_TEMPO_E_IDEMPOTENCIA.md`, `MAPA_TOPICOS_E_PERMISSOES.md` |
| P07 | `referencias/versão_v2/07_MQTT_Ingestao/HarpiSense_Pacote07_MQTT_Ingestao_v2/`: `ingest/consumer.py`, `ingest/store.py`, `telemetry_contract/core.py`, `IDENTIDADES_E_PERMISSOES.md`, `FLUXO_INGESTAO_E_GARANTIAS.md` |
| C | `harpisense-worktrees/frontend-backend-autonomia/docs/continuity/2026-10-31/mqtt-consumer-current.sanitized.txt`; snapshot fornecido pelo arquiteto, não executado |
| Legado | `referencias/Versões corretas/HarpiSense_Contratos_Unificados/HarpiSense_Contratos_Unificados/docs/CONTRATOS.md`: contratos de segurança continuam referências; não definem o envelope LDR |

SHA-256 dos bytes locais de C:
`69ff44febd7b6834f26cf7362794a032fd9dfc15257519b0c59aa629548d8f9f`.
`telemetry_contract/core.py` de P06 e P07 têm hash idêntico:
`17b9f07cb0eb80e1a2ca0fa945099b21571aea33ac1f711ae12dc4412d6264c2`.
O hash de C identifica a cópia sanitizada, não os bytes originais da VM.
Nenhuma consulta à VM nesta rodada; C representa a observação anterior do arquiteto.

## Matriz de compatibilidade

| Aspecto | F: firmware existente | P05 | P06 | P07 | C: consumidor observado |
| --- | --- | --- | --- | --- | --- |
| Tópico | `harpisense/v1/telemetry/harpisense.poste.poste-1/environment` | Configuração obrigatória, sem tópico homologado | Prefixo `harpisense/v1/telemetry/{device_id}/{sensor_type}`; exemplos `poste1/ldr` | Assina `harpisense/v1/telemetry/+/+`; mesmo parser P06 | Assina somente `harpisense/poste2/telemetry` |
| Identidade | `harpisense.poste.poste-1`; client ID `poste-1` | Device/post configuráveis; origem PHYSICAL | Device no tópico deve coincidir com payload; exemplos não são cadastro oficial | Exemplos `poste1` e `poste2-sim`; não obriga esses valores no parser | Exige objeto com `device_id=poste2`; callback não confere tópico explicitamente |
| Esquema | `schema_version=1.0`, `sensor_type=environment` | `harpisense.telemetry.proposal.v2` | `harpisense.telemetry.candidate.v2`, `sensor_type=ldr` | Mesmo candidato P06 | Não exige schema_version, sensor_type ou envelope específico |
| Medidas | `measurements.temperature_c/humidity_pct`, ambos null; `status.battery_pct=null`, RSSI inteiro | `reading_raw`, `reading_unit`, `reading_quality`, `led_commanded_state` na raiz; inclui post_id/origin_type | `measurements.ldr_adc_raw/led_commanded_on`, `status.origin_type/reading_quality/reading_unit` | Valida P06 e persiste JSON canônico | Preserva o objeto recebido; não valida tipos de medidas |
| Hora | `observed_at` UTC; fallback fictício `1970-01-01T00:00:00.000Z` | `timestamp_utc`, NTP, não enfileira sem UTC aceitável | `observed_at` UTC; valida formato/fuso, não garante relógio sincronizado nem frescor | Recepção SQLite tem received_at próprio; atraso/ordem ainda contextuais | Não verifica horário do payload |
| ID e reenvio | Novo message_id por publicação; sequência incrementa mesmo se publish falhar; sem fila | Device + boot aleatório + sequência; mantém ID, JSON e hora na fila RAM | message_id estável; fingerprint canônico; índice de exemplo em memória | PRIMARY KEY global message_id + hash e bytes canônicos: duplicate ou conflict | ID persistido `poste2-` + SHA-256(tópico UTF-8 + NUL + payload bruto); ignora message_id para deduplicar |
| Autenticação | WiFiClient sem TLS; usuário/senha no config.h local; exemplo lab compartilhado | WiFiClient; usuário/senha externos ao Git; TLS habilitado bloqueia conexão, não implementa TLS | Exige credencial/ACL por dispositivo na proposta; parser não autentica publisher | Exige usuário/senha e CA, TLS com verificação, padrão 8883; client ID configurável | Usuário técnico harpisense_mqtt; senha em arquivo externo; porta 1883 sem tls_set |
| QoS e retenção | PubSubClient publica QoS 0, retain=false; keepalive 30 | QoS 0, retain=false; true significa aceitação local; keepalive 30 | Simulador propõe publish QoS 1, retain=false; keepalive 60 | Assinatura QoS 1, MQTT 3.1.1, sessão persistente e client ID estável padrão | Assinatura QoS 1; keepalive 60; QoS do publisher não demonstrado pelo snapshot |
| Persistência/garantia | Sem confirmação de persistência | RAM limitada, expiração e descarte; remove após aceitação local, perde no reboot | Não promete exatamente uma vez | SQLite transacional, fila RAM limitada; ACK MQTT não comprova commit, falha pode perder mensagem | PostgresStore.insert telemetry; snapshot não demonstra garantias internas do store nem ACK após commit |

## Incompatibilidades comprovadas por leitura

1. C não assina nenhum tópico do Poste 1 e rejeita sua identidade se o callback
   receber o objeto. Usar device_id=poste2 para contornar isso corromperia a origem.
2. F não lê LDR/LED e o payload environment não satisfaz P06/P07: versão,
   sensor_type, campos obrigatórios e campos extras divergem. Não converter ADC
   em temperatura para encaixar no envelope antigo.
3. P05 não satisfaz P06/P07 sem transformação: timestamp_utc → observed_at,
   reading_raw → measurements.ldr_adc_raw, led_commanded_state →
   measurements.led_commanded_on; origem/qualidade/unidade migram para status;
   remover post_id da mensagem P06 e usar cadastro externo para vínculo ao poste.
4. F fabrica 1970 sem sincronização e não mantém amostra para retransmissão.
   P05 melhora esse comportamento, mas a fila continua volátil e QoS 0.
5. P07 exige TLS/CA e usa SQLite; C usa conexão 1883 sem TLS e PostgresStore.
   P07 não pode substituir C diretamente nem importar seu simulador como Poste 2 real.
6. ACL histórica de laboratório usa usuário compartilhado e `%c` no tópico;
   o client ID aleatório device+boot do P05 não corresponde ao padrão histórico
   `harpisense.poste.%c`. Essa configuração não é prova da ACL ativa do broker.
7. P06 permite ADC inteiro não negativo sem máximo de 4095; sequência é opcional
   no schema. Para o perfil físico confirmado, validar 12 bits explicitamente
   e exigir sequência no adaptador proposto, sem editar o schema compartilhado.

## Contrato concreto recomendado — pendente de aceite

Usar a versão candidata existente, sem promovê-la pelo nome: UTF-8 JSON objeto,
até 1024 bytes, números finitos, chaves conhecidas; rejeitar chaves duplicadas
no adaptador estrito. Manter o tópico histórico environment apenas como referência
de regressão; não duplicar publicação nem interpretá-lo automaticamente como LDR.

| Campo | Tipo/regra proposta para o perfil Poste 1 |
| --- | --- |
| schema_version | String constante `harpisense.telemetry.candidate.v2` até decisão formal de versionamento |
| device_id | Constante `harpisense.poste.poste-1`, deve coincidir com tópico exato aprovado |
| sensor_type | Constante `ldr` |
| message_id | String até 64 caracteres `[A-Za-z0-9_.-]`; device + boot aleatório de 16 hex + sequência; estável por amostra |
| sequence | Inteiro obrigatório no perfil, não negativo; mesma sequência no reenvio; boot diferencia reinícios |
| observed_at | Hora de coleta UTC, serializar com Z; sem NTP válido não publicar amostra com hora inventada |
| measurements.ldr_adc_raw | Inteiro 0..4095 para ADC explicitamente configurado em 12 bits; null para indisponível/fora da faixa |
| measurements.led_commanded_on | Booleano do comando local; não afirma acendimento físico |
| status.origin_type | Constante PHYSICAL para este dispositivo; não misturar simulador |
| status.reading_quality | RAW_UNCALIBRATED com inteiro; UNAVAILABLE ou OUT_OF_RANGE com null; zero e 4095 não provam desconexão |
| status.reading_unit | Constante adc_raw, nunca lux sem calibração aprovada |
| status.calibration_version | Omitido enquanto não houver calibração; opcional no P06 |

Exemplo exclusivamente sintético para revisão (não é evidência de hardware):

```json
{
  "schema_version": "harpisense.telemetry.candidate.v2",
  "message_id": "harpisense.poste.poste-1-0123456789abcdef-1",
  "device_id": "harpisense.poste.poste-1",
  "observed_at": "2026-10-31T12:00:00Z",
  "sensor_type": "ldr",
  "sequence": 1,
  "measurements": {"ldr_adc_raw": 1800, "led_commanded_on": false},
  "status": {"origin_type": "PHYSICAL", "reading_quality": "RAW_UNCALIBRATED", "reading_unit": "adc_raw"}
}
```

## Ajustes mínimos futuros e fronteiras

**Firmware (IoT):** manter o projeto existente e identidade; acrescentar perfil
LDR/LED com GPIOs e circuito aprovados, resolução ADC explícita e histerese
calibrada. Adaptar serialização para a tabela acima; capturar hora, ID, sequência
e bytes uma única vez por amostra. Reaproveitar fila limitada/expiração do P05,
contabilizando perdas e preservando payload em tentativas. Configurar buffer MQTT
para o limite contratado incluindo overhead; verificar retorno da configuração.
Adicionar flags de publicação fechadas por padrão, configurações locais sem
segredos versionados e reconexão sem bloquear aquisição indefinidamente.

Recomendar inicialmente QoS 0/retain=false com a biblioteca existente e declaração
explícita de melhor esforço; não afirmar que assinatura QoS 1 eleva a publicação.
Se o requisito for entrega ao broker QoS 1, a troca/adequação do cliente publicador
é trabalho adicional, com PUBACK e reenvio testados. Nenhuma opção oferece por si
só confirmação PostgreSQL. Fila persistente/ACK de aplicação exigem outra decisão.

**Consumidor (backend):** adicionar módulo/handler exclusivo, habilitado por flag,
para o tópico exato do Poste 1. Validar tópico + identidade + versão + perfil
físico antes de persistir; não ampliar a condição `device_id=poste2` para aceitar
arbitrariamente outras identidades. Preservar o handler atual, dados, tópico e
algoritmo de ID do Poste 2 byte a byte. Despachar por tópico exato; uma mensagem
com identidade trocada deve falhar, mesmo com envelope estruturalmente válido.

Para Poste 1, propor unicidade persistente por `(device_id,message_id)` e hash de
JSON canônico: idêntico vira duplicate, ID igual com conteúdo distinto vira
identifier_conflict sem sobrescrever. Namespace de record `poste1-` + SHA-256
de device_id UTF-8 + NUL + message_id UTF-8; guardar fingerprint para conferir
conflito. Verificar capacidades reais do PostgresStore antes de implementar:
se só houver insert por ID, é necessário mecanismo transacional adicional para
comparar conteúdo e conflito. Não importar SQLite P07 para o serviço operacional.
received_at é dado de recepção separado, sem trocar observed_at; TTL, desvio de
relógio e fora de ordem precisam de política aprovada, sem rejuvenescimento no retry.

**Autenticação/transporte (proposta separada):** credencial exclusiva do Poste 1,
client ID próprio estável `poste-1` e ACL de escrita somente no tópico LDR exato;
consumidor técnico recebe apenas a leitura adicional necessária. Não reutilizar
credencial de Poste 2 nem depender de client ID controlado pelo cliente como prova
de identidade. Assinante comum não recebe o principal autenticado do publisher:
ACL no broker e validação de tópico/payload são complementares.
Recomendar TLS com CA e verificação de hostname para habilitação final; isso
exige implementação no firmware e proposta coordenada do broker. Não ativar
HS_TLS_ENABLED como se P05 já implementasse TLS. Não migrar broker ou Poste 2
como efeito colateral; qualquer exceção de laboratório sem TLS exige decisão
explícita e não satisfaz mqtt_tls_mode=required do gerenciador.

## Ainda não verificado e aceite necessário

- GPIOs reais da placa de 30 pinos, ligação/resistores, polaridades, limiares,
  estabilidade/ruído do ADC, alimentação, estado físico do LED e calibração.
- Conectividade Poste 1 → broker, NTP disponível, credenciais/ACL efetivas,
  certificados, QoS negociado, retenção e políticas de sessão no broker.
- Capacidade do armazenamento oficial de detectar conflito atomicamente,
  integração com projeções/API e representação de LDR na interface existente.
- Build PlatformIO e execução em hardware; recuperação após queda de Wi-Fi,
  broker, banco, energia, fila cheia e expiração. Nada disso foi executado aqui.

Antes de habilitar, executar em isolamento: fixture do Poste 1 contra parser
estrito; rejeição de tópico/identidade trocados, versão errada, ADC fora da faixa,
booleano como ADC, NaN, chaves extras/duplicadas, tamanho excessivo e hora inválida;
reenvio idêntico/ID conflitante e concorrência no banco. Regressão do Poste 2 deve
demonstrar mesmo tópico, identidade, payload preservado e ID por bytes originais,
incluindo diferença de whitespace que hoje produz hashes distintos. Depois,
validar ACL com identidades separadas e firmware sem publicação por padrão.
Aceite do trajeto de rede e contrato precede qualquer ativação na infraestrutura.

## Registro desta rodada

Inspeção estática, comparação de hashes e documento de recomendação.
Tentativa de validar o exemplo com o parser candidato P06 em Python 3.12
interrompida na importação: `ModuleNotFoundError: No module named 'jsonschema'`.
Portanto o exemplo não tem aprovação executável do validador nesta rodada;
nenhuma dependência foi instalada para esta entrega documental.
O snapshot C não foi importado/executado. Nenhum teste funcional, compilação ou
teste de hardware foi declarado aprovado. Nenhum contrato compartilhado, firmware,
consumidor, VM, broker, credencial ou placa foi alterado. A decisão solicitada ao
arquiteto é aprovar identidade/tópico e perfil P06, política de entrega/tempo,
deduplicação persistente e plano de autenticação antes da implementação isolada.
