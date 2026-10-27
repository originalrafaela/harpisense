# P08: evidências de cobertura por fonte

Esta branch acrescenta proveniência verificável à captura/orquestração P08 existente. A captura mantém o esquema `harpisense.capture.session.v1`; a integração mantém `harpisense.p08.integration.v1` e as janelas `harpisense.if.window.v1`. A identidade de janela continua sendo produzida pelo integrador existente. O perfil descreve fontes obrigatórias por sessão, sem criar catálogo alternativo.

As referências normativas usadas foram as entregas aprovadas de `referencias/versão_v2/08_Coleta_Evidencias` (mapa de fontes, identidade/janelas e limitações de visibilidade) e os contratos P08/P09 já usados em `backend/p08_p09`. Onde a V2 ainda não atualiza o coletor experimental, foram preservados os arquivos e interfaces da cópia correspondente ao staging. Não foram alterados P11, PostgresStore, frontend, serviços ou arquivos da VM.

## O que a implementação registra

- `capture_session_v4.py` aceita um identificador explícito e perfil, registra o início da sessão, início efetivo da captura, fim, PID, observações do processo, erros de sondagem, interrupção/razão de término, estatísticas de `tcpdump` disponíveis, hash e tamanho do PCAP. Aguarda processo ativo e cabeçalho PCAP antes de iniciar os 120 segundos efetivos. Uma falha ou timeout não é convertido em cobertura.
- O filtro efetivo captura TCP entre os IPs de origem e destino configurados. O timestamp de término efetivo é separado do fim da limpeza do processo; pacotes de inicialização e de encerramento ficam contabilizados à parte e não entram nas janelas efetivas.
- Cada relatório de sessão é assinado por Ed25519. O fingerprint configurado é SHA-256 da chave pública DER. A captura permanece limitada à interface, IPs e perfil explícitos.
- `coverage_evidence.py` valida identidade, assinatura, hashes, timestamps, fontes obrigatórias e intervalos. Fonte externa precisa entregar manifesto e registros assinados, vinculados ao hash do relatório de sessão e do PCAP. Assinatura prova integridade/origem da chave configurada, não a veracidade operacional nem a completude por si só.
- `OBSERVED_NO_EVENTS` é usado apenas se todas as fontes obrigatórias comprovarem cobertura daquele intervalo e houver zero eventos. Intervalos sem registros ou fonte sem prova ficam `UNKNOWN`/`INCOMPLETE`; os limites parciais da sessão não são promovidos.
- Evidência MQTT auxiliar só é vinculada quando cursor, boot ID e instante batem com evento da fonte assinada dentro do período. Lote antigo não é automaticamente associado à nova sessão.
- A integração chama o pipeline P09 existente e os gates de artefato/cobertura. `collection_complete`, prontidão, inferência e IPS permanecem falsos; `log_counts` permanece `{}`. O relatório pode dizer que as fontes tiveram cobertura comprovada sem declarar a sessão apta para inferência.
- O orquestrador não chama persistência P11/PostgreSQL. Cada saída é criada exclusivamente; arquivos históricos e checkpoints não são sobrescritos.

## Perfil e chaves

`examples/tcp-observacao.profile.example.json` é deliberadamente inutilizável antes de substituir todos os placeholders. Ele exemplifica `gateway_capture`, `mqtt_broker`, `mqtt_consumer` e `api_fastapi`. A lista final precisa ser confirmada com o perfil/validador oficial e o inventário real. Em particular, o host do broker ainda não foi confirmado; não se deve afirmar cobertura do broker até importar registros daquele host.

Cada host assina com sua chave privada Ed25519, mantida somente naquele host e legível apenas pelo usuário do serviço (modo `0600`). A chave pública e seu fingerprint são distribuídos por canal administrativo confiável, com leitura restrita; nunca se coloca uma chave privada no repositório ou na VM de outro host. Exemplo para gerar par e fingerprint DER:

```sh
umask 077
openssl genpkey -algorithm ED25519 -out gateway-capture-ed25519.pem
openssl pkey -in gateway-capture-ed25519.pem -pubout -out gateway-capture-ed25519.pub
openssl pkey -pubin -in gateway-capture-ed25519.pub -outform DER | sha256sum
```

A chave privada de captura deve pertencer ao usuário que executa o coletor; a chave pública correspondente é instalada no diretório de confiança. Para importar uma fonte remota, a máquina exportadora primeiro valida a assinatura do relatório da sessão e o hash do PCAP, então usa `integracao/build_source_manifest.py` com os eventos/cursor/boot daquela fonte e assina o manifesto com a chave privada local. Só declare `COMPLETE` e `--continuity-verified` quando os próprios registros sustentarem continuidade para todo o intervalo. Para `INCOMPLETE` ou `UNKNOWN`, forneça `--reason`; lacunas continuam explícitas.

O importador espera JSONL UTF-8 em `--input-records`, com um objeto por evento contendo `event_id`, `observed_at` em UTC com fuso, `journal_cursor` e `journal_boot_id` quando disponíveis. O utilitário grava `records.jsonl` e `<source>.manifest.json` sob a pasta da fonte, com schema `harpisense.p08.source-evidence.v1`. O manifesto vincula sessão, hash do relatório e PCAP, perfil, fonte, host, sensor, alvo, intervalo UTC, boot/cursor inicial e final, encadeamento opcional por `previous_cursor`, estado/motivo de cobertura, quantidade e hash dos registros e assinatura Ed25519. A verificação rejeita assinatura/fingerprint inválido, divergência de identidade/hash, evento duplicado ou fora do período, intervalo insuficiente e continuidade não declarada. Para logs Windows, uma etapa de exportação local ainda precisa mapear os registros reais do broker para esse JSONL; o exportador deve ser executado no host dono dos logs e não existe neste pacote.

O adaptador sanitiza o arquivo de entrada para campos necessários de rastreio. A validade criptográfica do bundle não comprova que o coletor remoto leu todos os logs existentes. O dono da fonte deve documentar origem, retenção e método de exportação.

## Máquinas e dependências para coleta real

O diagnóstico local disponível identifica o HarpiServer `gateway` em `100.66.89.7`, com captura na interface `ens37`; estes valores ainda precisam ser conferidos imediatamente antes da coleta. Ele precisa estar ligado e acessível. No gateway são necessários:

- Python do ambiente P08 e os scripts instalados correspondentes à branch;
- `tcpdump`, `openssl` com Ed25519 e acesso de leitura a `/proc` para monitoramento;
- privilégio root ou capacidades equivalentes `CAP_NET_RAW` e `CAP_NET_ADMIN` para captura; permissão de escrita apenas no diretório novo de capturas/importação;
- leitura do perfil e chave privada de captura pelo usuário executor; chaves públicas dos hosts importados somente para leitura;
- caminho de leitura do adaptador P09 existente. Não é necessária permissão de banco, MQTT administrativo, inferência ou IPS.

Também devem estar ligados e acessíveis os hosts que realmente executam o broker MQTT, o consumidor MQTT e a API FastAPI. O broker pode estar em Windows ou outro host: sua localização/serviço ainda exige inventário. Nesses hosts, habilite somente exportação/leitura dos logs do intervalo e execução do exportador assinado; não conceda acesso remoto de escrita aos logs nem copie chaves privadas. O produtor de tráfego deve ser a máquina/serviço declarado no perfil, previamente autorizado, e gerar somente tráfego controlado. O `target_ref`, IPs, interface e identidade dos hosts no exemplo são placeholders, não valores presumidos. Nenhuma máquina de ataque ou defesa é necessária.

Serviços reportados anteriormente no gateway incluem `harpisense-mqtt.service` e `harpisense-p11.service`, mas o nome do serviço que publica logs, a implantação atual da API e o host do broker precisam ser confirmados no inventário. Esta implementação não reinicia nem altera serviços.

## Execução controlada de 120 segundos (procedimento, não executado)

Antes, substitua placeholders do perfil, instale os arquivos desta branch em staging após revisão/hash e crie diretórios exclusivos para a sessão. O diretório de importação pode receber apenas bundles assinados; não use lote/checkpoint histórico. Um operador no host de cada fonte deve entregar os manifestos durante a espera configurada.

```sh
SESSION_ID="p08-cobertura-$(date -u +%Y%m%dT%H%M%SZ)"
sudo install -d -m 0750 "/opt/harpisense/import/p08/${SESSION_ID}"
sudo /opt/harpisense/venv/bin/python \
  /opt/harpisense/staging/p08-captura/integracao/orquestrar_p08_v4_experimental.py \
  --session "$SESSION_ID" \
  --profile-config /etc/harpisense/p08/profiles/tcp-observacao.json \
  --signing-key /etc/harpisense/p08/keys/gateway-capture-ed25519.pem \
  --source-evidence-dir "/opt/harpisense/import/p08/${SESSION_ID}" \
  --duration 120 --startup-timeout 30 --heartbeat-seconds 1 \
  --source-evidence-wait-seconds 180 \
  --output-dir /opt/harpisense/capturas \
  --p09-adapter-dir /opt/harpisense/staging/p09-deteccao-decisao/adaptador_logs_p08_p09
```

Este comando inicia uma sessão real e **não foi executado nesta entrega**. O período efetivo só começa após o coletor confirmar readiness; o timeout de readiness não consome a duração. O perfil seleciona filtros, portanto confirme tráfego e alvo antes da execução. A janela de espera de 180 s permite a chegada dos bundles assinados após o PCAP. Se algum não chegar, o resultado registra a fonte como desconhecida/incompleta e mantém os gates fechados.

Saídas próprias da sessão: `.pcap`, `.session.json` e `.session.json.sig`, `.p08.json`, `.coverage.json` e assinatura, `.p09-gate.json`. Critérios mínimos de aceite técnico: assinatura e hashes válidos; identidade única e alinhada entre sessão/PCAP/janelas; processo pronto antes dos 120 s efetivos; encerramento normal sem erros/interrupção/perdas de kernel; cada fonte obrigatória com evidência assinada cobrindo intervalos inteiros e cursores/boot quando aplicável; nenhuma evidência fora da sessão; teste do validador real sem bypass. Isso ainda não autoriza inferência/IPS nesta entrega.

## Testes e limites da validação

Os testes adicionados usam processos, relógio, PCAPs, perfis e chaves sintéticos em diretórios temporários. Cobrem início normal/atrasado, interrupção, fonte obrigatória ausente, janela vazia comprovada versus desconhecida, evidência fora do intervalo, hash/manifesto adulterado e ligação P09 fail-closed. Testes de regressão P08/P09 também são executados pelo runner local em container Linux. Nenhum teste foi executado nas VMs; nenhum PCAP real novo foi coletado e nenhum log real de broker foi importado. Não se afirma cobertura operacional.

## Aplicação e recuperação (não executadas)

Aplicar primeiro em staging, copiando apenas os arquivos desta pasta e os dois arquivos P09 explicitamente alterados (`log_coverage_integration.py`, `p08_p09_pipeline.py`). Compare os hashes da candidata, faça backup versionado dos destinos e confirme que os hashes no destino correspondem à base esperada antes de substituir. Não aplique sobre diferenças inesperadas, não copie diretórios inteiros, não toque em capturas/checkpoints/P11/PostgresStore e não reinicie serviços. Faça uma execução controlada somente após confirmação do inventário e autorização operacional. Para recuperar, pare a execução controlada se estiver ativa, restaure apenas os arquivos de código do backup da mesma aplicação, confira hashes antes/depois e preserve todos os artefatos da nova sessão para diagnóstico. Não apague ou altere históricos.
