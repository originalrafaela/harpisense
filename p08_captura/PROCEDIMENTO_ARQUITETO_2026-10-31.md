# Candidata P08 → P09 para coordenação do laboratório

Entrega para publicação em `feat/p08-evidence-coverage`, base `c314ca5`. Nenhuma coleta, aplicação em VM, checkpoint, ataque, inferência ou IPS executado nesta rodada. Autenticação P11, PostgreSQL, frontend, rotas e nftables preservados. Validação Linux isolada concluída; publicação Git não significa implantação no HarpiServer.

## Referências e estado de implantação

Prioridade: `referencias/versão_v2` P02, P05, P06, P08 e P09; P08 `MAPA_FONTES_E_FLUXO.md`, `FEATURES_JANELAS_E_IDENTIFICADORES.md` e componentes preservados; P09 `schemas/feature_schema.json`. RF anterior: `referencias/Versões corretas/Random Forest/HarpiSense_Random_Forest_Completo/feature_schema.json`. O RF anterior e o P09 V2 compartilham as mesmas nove features de rede, opcionais e versão `harpisense.if.window.v1`. Ausência de revisão V2 não significa ausência de componente. Usar os componentes preservados e os pacotes anteriores, sem substituir contratos por propostas P05/P06 ainda não homologadas.

Histórico auditado no Git local: somente a branch `feat/p08-evidence-coverage` e seu tracking remoto contêm `c314ca5`; nenhum commit posterior de P08 foi localizado nos refs disponíveis. Não foi feito fetch: isto não certifica ausência de alterações remotas mais recentes. `c314ca5` é candidata publicada, não implantação comprovada. A documentação posterior `docs/continuidade-p08-p09` (`3e72720` e seus arquivos de triagem/decisão) preserva a distinção. `IDENTIFICACAO_SESSAO_P08_APOS_APLICACAO.md` comprova aplicação de `2de050e` em dois arquivos do adaptador, com backup e recibo; não comprova aplicação da captura assinada. Nenhum hash remoto foi revalidado nesta rodada.

A captura existente foi reutilizada como implementação. Não foram reconstruídos PCAPs, reatribuídos lotes históricos nem promovida a sessão `p08-v4-persistencia-auto02`. Ela continua útil para integridade e análise offline, com cobertura insuficiente. Lotes de 25/10 não pertencem automaticamente à sessão de 23/10.

## Percursos e perfis separados

| Fluxo | Evidência disponível | Consequência para P08 |
|---|---|---|
| Poste 2 → broker | Relatório V2 `HarpiSense_V2_Relatorio_Fluxo_Poste2_MQTT_PostgreSQL_API.pdf`, 18/10, pp. 2–4: Poste 2 com NIC NAT `192.168.155.142`, broker Windows `192.168.155.1:1883`, tópico `harpisense/poste2/telemetry`, QoS 1 e PUBACK | Conexão MQTT e destino NAT registrados no relatório; IP efetivo de origem de cada conexão, próximo salto e interface escolhida não foram demonstrados por rota/PCAP nesta revisão. Não prova passagem por `10.20.30.1/ens37`. |
| Broker → consumidor | Mesmo relatório; consumidor no HarpiServer `192.168.155.144`/`ens33` | Outra conexão TCP. Pacotes desse trecho não são contagem do publisher Poste 2. |
| Poste 2 → HarpiServer isolado | Relatório 23/10: `10.20.30.2 → 10.20.30.1`, `ens37`, sessão histórica | Observação TCP separada do MQTT NAT; não prova tráfego broker. O relatório 23/10 registra publicação pelo próprio HarpiServer e deixa publicação autenticada no Poste 2 pendente, apesar do marco de 18/10. Revalidar o cenário atual. |
| ESP32 → intermediário/VPN/proxy → broker | P02 descreve alternativas; P05 contém `REPLACE_BROKER_HOST`, rota e hardware pendentes | Percurso real NÃO COMPROVADO. Registrar Wi-Fi, destino configurado, intermediário, modo proxy/subnet e origem vista pelo broker. IP de proxy não identifica ESP32. |

Inspeção local de 31/10: serviço Windows `mosquitto` Running; consulta `Get-NetTCPConnection -LocalPort 1883` não retornou conexões. Isso não prova listener, continuidade ou caminho ESP32/Poste 2. Sem inspeção do firmware/intermediário não é legítimo declarar o percurso ESP32 conhecido.

### Precisão da evidência Poste 2 e capacidade de bloqueio

O marco de 18/10 é comprovação documental de teste funcional reportado (publicação, PUBACK, persistência e consulta), não uma nova observação independente do percurso. O relatório de 23/10 comprova documentalmente outra publicação, originada no HarpiServer, e deixa nova publicação autenticada do Poste 2 pendente. Não atribuir essa publicação ao Poste 2 nem declarar continuidade entre os dois marcos. A captura isolada histórica `10.20.30.2 → 10.20.30.1` prova somente os pacotes retidos daquele par/contexto; não demonstra o trajeto até o Mosquitto Windows.

Hipótese compatível com os endereços: Poste 2 e broker se comunicam diretamente pela rede VMware NAT/VMnet8, contornando o HarpiServer. Estar no mesmo prefixo torna esse caminho plausível, mas não comprova a rota efetivamente selecionada, ausência de policy routing/proxy, bridge ou túnel. Topologia inline via Gateway, espelhamento para captura e passagem por `ens37` também não estão comprovados. As propostas P02 V2 explicitamente não são implantação validada. Nenhuma dessas hipóteses foi testada nesta rodada.

Visibilidade e controle são propriedades distintas:

- Um sensor no broker, no segmento ou numa porta espelhada pode observar pacotes sem que o Gateway os encaminhe. Capturar com tcpdump não torna esse host um ponto de bloqueio.
- Para afirmar que o Gateway pode bloquear Poste 2 → broker, é necessário demonstrar que o fluxo real atravessa o caminho de dados controlado pelo Gateway e o ponto de aplicação correspondente. Em tráfego roteado seria o encaminhamento; tráfego destinado ao próprio Gateway e tráfego originado nele têm outros pontos de aplicação. Uma bridge ou túnel exige análise própria. Nenhum desses caminhos foi homologado para bloqueio aqui.
- Se o fluxo direto VMnet8 for confirmado, regras no Gateway não bloqueiam esse trecho que o contorna. Bloquear a conexão broker → consumidor no Gateway interromperia a ingestão local; isso não comprova bloqueio da publicação Poste 2 → broker e não deve ser apresentado como eficácia IPS desse fluxo.

Prova futura mínima, a ser coordenada pelo arquiteto: rota efetiva no produtor e retorno no broker, interface/origem e identidade vistas pelo broker, correlação de mensagem legítima com observação no sensor do trecho correto e identificação do ponto de aplicação. Isso pode confirmar visibilidade; capacidade e eficácia de bloqueio exigem homologação separada e não foram executadas. Nesta rodada não se alteram nem consultam regras para tentar demonstrar eficácia.

Referências documentais preservadas (SHA-256): relatório do fluxo 18/10 `a9d4fac6f649e171c4ab0ffb2cbd08bbe67e929284975f5dc8f11744d8930523`; relatório 23/10 `dd6c00cd89800ee841853037b706e18ba10c75488df897fd4b87679d24d74bf4`. P08 V2 `LIMITACOES_DE_VISIBILIDADE.md` exige verificar interfaces/rotas/túneis e desvios in loco. Nada aqui converte essa exigência em resultado já obtido.

Os exemplos `poste2-mqtt-nat.profile.example.json` e `esp32-mqtt-percurso.profile.example.json` são bloqueados por placeholders. Para cada fluxo, o arquiteto preenche perfil próprio após inventário. `gateway_capture` é o identificador legado da fonte PCAP: configurar `host_id`, sensor e interface do host que realmente observa o trecho; não atribuir a captura ao Gateway por causa desse nome. Se só houver observação no Windows e o coletor Linux atual não alcançar esse trecho, a rodada fica bloqueada até disponibilizar sensor compatível ou importação PCAP homologada. Não remapear a rede nesta entrega.

## Lacunas fechadas na candidata

- Perfil valida IPv4, fingerprint hexadecimal e nome simples de fonte; impede saída do diretório de importação por identificador de fonte.
- Verificação assinada inclui destino. Integrador rejeita argumentos de sessão/sensor/destino/perfil divergentes antes de chamar o integrador existente.
- Cobertura rejeita janela de outra sessão/sensor/par IP/perfil, ID repetido, intervalo parcial, desalinhado ou fora do período efetivo. Nenhum ID oficial é recalculado.
- Evento com boot explícito divergente do manifesto é rejeitado. Cada fonte completa mantém seu próprio coverage_record mesmo se outra faltar; gate global continua fechado.
- `LC_ALL=C` torna o parsing das estatísticas tcpdump previsível. Flags exclusivas usam constantes `os`; fsync de diretório permanece no Linux. Não se retiram permissões Linux.
- `audit_feature_contract.py` verifica estrutura RF/IF e metadados opcionais de artefato, sem carregar modelos nem executar inferência. Ausência opcional não vira zero. PASS estrutural não prova cálculo numérico, autoria ou cobertura.

## Pré-condições e inventário somente leitura

O arquiteto registra operador, UTC, versões/hash de código aplicado e perfil, sensor, alvo e escopo autenticados, MAC/NIC/IP/rotas de ida e retorno, DNS/destino MQTT real, identidade MQTT/tópico e retenção de cada log. Anexar configuração sanitizada do ESP32 e intermediário; nunca exportar senhas ou Environment completo de serviços. Comandos a executar futuramente por host:

```sh
hostname
ip -br addr
ip route get <BROKER_IPV4>
ss -nt
timedatectl show -p NTPSynchronized
cat /proc/sys/kernel/random/boot_id
systemctl show harpisense-mqtt -p ActiveState -p MainPID -p NRestarts
journalctl -u harpisense-mqtt --no-pager -n 1 -o json
```

No Windows: `Get-NetIPConfiguration`, `Get-NetRoute -AddressFamily IPv4`, `Get-NetTCPConnection -LocalPort 1883`, `Get-Service mosquitto`, `w32tm /query /status`. Consultar somente configuração de listener/log e limites de retenção sanitizados. Não testar publicação nem iniciar captura nesta rodada. Rota/ss isolados não provam que todos os pacotes percorreram um trecho: correlacionar futuramente PCAP do sensor correto, origem vista no broker e ID da mensagem legítima.

Fontes do perfil: PCAP, broker Windows, consumidor MQTT, API se exigida pelo cenário. Não remover fonte apenas para passar um gate. Para fonte não aplicável, obter decisão de escopo e perfil revisado antes da coleta; não fazer promoção retroativa. Cada dono da fonte fornece chave pública autenticada, boot/geração do serviço, cursores/offsets de fronteira, relógio, retenção/rotação e método de exportação. Uma assinatura e `--continuity-verified` são atestação, não leitura automática dos logs. Exportador Windows de Mosquitto ainda depende do formato real: sem prova de leitura integral, lacunas/rotação e fronteiras, assinar UNKNOWN/INCOMPLETE e manter aceite bloqueado.

## Comandos para uma rodada futura autorizada

Aplicar somente arquivos revisados P08 e os dois adaptadores P09 de `c314ca5`, em staging separado; comparar hashes atuais com base esperada e backup. O `backend/p08_p09/apply_staging.py` anterior instala apenas os dois arquivos da candidata antiga: não usá-lo para instalar este pacote inteiro. Não sobrescrever diretórios de serviços ou reiniciar P11.

1. Confirmar inventário e sensores por percurso. Preparar diretórios novos e chaves conforme README. Registrar fronteiras das fontes antes do início; sem coletores incrementais V5 ou escrita de checkpoint.
2. Executar o comando abaixo somente quando o arquiteto autorizar a rodada. Caminhos e perfil devem apontar à candidata conferida. Duração 120 s efetivos após readiness, até 12 janelas inteiras, mais bordas parciais. Para cadência lenta, justificar duração antes, limitada a 300 s pelo controlador.

```sh
SESSION_ID="p08-poste2-$(date -u +%Y%m%dT%H%M%SZ)"
python /CAMINHO_CANDIDATA/p08_captura/integracao/orquestrar_p08_v4_experimental.py \
  --session "$SESSION_ID" --profile-config /PERFIL_CONFERIDO.json \
  --signing-key /CHAVE_PRIVADA_LOCAL.pem \
  --source-evidence-dir "/IMPORT_NOVO/$SESSION_ID" --output-dir /CAPTURAS_NOVAS \
  --duration 120 --startup-timeout 30 --heartbeat-seconds 1 \
  --source-evidence-wait-seconds 180 --python /opt/harpisense/venv/bin/python \
  --controller /CAMINHO_CANDIDATA/p08_captura/capture_session_v4.py \
  --integrator /CAMINHO_CANDIDATA/p08_captura/integracao/integrar_p08_v2.py \
  --p09-adapter-dir /ADAPTADOR_CANDIDATO
```

O wrapper `integrar_p08_v2.py` continua reutilizando `/opt/harpisense/staging/p08-captura/integracao/integrar_p08.py`, componente anterior; confirmar hash/disponibilidade antes. Ele processa o PCAP original inteiro. Pacotes de startup/shutdown podem gerar janelas parciais: a nova verificação bloqueia essas janelas em vez de apará-las ou mudar features silenciosamente. Preservar para diagnóstico; aceite exige tratamento homologado pelo produtor de features ou período integral compatível, sem editar retrospectivamente os dados.

3. Os donos exportam os logs da sessão por leitura limitada, sem checkpoint. `build_source_manifest.py --help` descreve assinatura com `--profile-config`, `--session-report`, `--source`, `--input-records`, `--output-dir`, `--signing-key`, `--boot-id`, `--cursor-start`, `--cursor-end`, `--interval-start`, `--interval-end`, `--coverage-status`. Apenas usar `--continuity-verified --coverage-status COMPLETE` se o método independente comprovar continuidade. Para UNKNOWN/INCOMPLETE, usar `--coverage-reason`. JSONL deve conter event_id/observed_at e cursor/boot reais quando disponíveis; nomes fictícios não suprem a prova. Copiar apenas bundles/chaves públicas, nunca chave privada entre hosts.
4. Opcionalmente fornecer `--audit-batch /LOTE_NOVO.json` ao orquestrador; ele reutiliza a validação de lote existente. Não usar lotes de outra sessão. Evento auxiliar só se vincula com cursor/boot/instante correspondentes à fonte assinada; continua fora das features e das contagens oficiais.
5. Auditar offline as features com schema V2 e, separadamente, metadados RF e IF reais:

```sh
python /CAMINHO_CANDIDATA/p08_captura/integracao/audit_feature_contract.py \
  --integration /CAPTURAS_NOVAS/SESSION.p08.json \
  --session-report /CAPTURAS_NOVAS/SESSION.session.json \
  --feature-schema /PACOTE09_V2/schemas/feature_schema.json \
  --model-metadata /METADADOS_RF_OU_IF.json --output /SAIDA_NOVA.contract.json
```

Sem metadados reais, retirar o argumento e registrar `model_compatibility=NOT_VERIFIED`. Nunca ajustar a ordem de features à mão; usar a lista do artefato. O auditor consome o mesmo contrato compartilhado; os gates existentes do modelo continuam necessários em homologação posterior.

## Aceite e devolução ao arquiteto

| Item | Aceite | Falha |
|---|---|---|
| Início/continuidade | readiness antes do cronômetro efetivo; duração comprovada; heartbeats sem lacunas, monitor legível, encerramento normal | Timeout/interrupção/PID ausente/relógio incoerente mantém INCOMPLETE |
| Perdas | estatísticas tcpdump presentes, zero kernel drops e PCAP íntegro; avaliar NIC e perdas de produtor/broker separadamente | Contador ausente não vira zero. `received-captured` não mede perda fim a fim; zero kernel drops não prova perda zero no percurso |
| Vínculos | sessão assinada, hash/tamanho PCAP, perfil e alvo conferidos, janelas com IDs oficiais únicos e intervalos integrais; logs vinculados por hash/contexto/cursor/boot | Arquivo com nome parecido, IP de proxy ou horário próximo não autentica dispositivo ou sessão |
| Fontes | inventário fechado e cada fonte com intervalo, origem, retenção e continuidade comprovados | Fonte faltante fica UNKNOWN; assinatura inválida/lacuna fica INCOMPLETE |
| Janela vazia | `OBSERVED_NO_EVENTS` somente com todas as fontes cobrindo a janela inteira e zero registros | Janela sem prova fica UNKNOWN/INCOMPLETE; não gerar feature zero nem janela RF fictícia |
| RF/IF | nove features, unidades e duração do schema V2; ordem/perfil do artefato real; revisão numérica independente das fórmulas P08 em amostra do PCAP | PASS estrutural sozinho não homologa semântica nem modelo; opcionais sem procedência ficam ausentes |
| Gates | validador de artefatos e lote existente, assinatura e gate de fontes executados sem bypass | `collection_complete`, `ready_for_inference`, autorizações RF/IF e IPS continuam False e `log_counts={}` nesta candidata |

Guardar PCAP, sessão e assinatura, perfil/hash, integração, coverage/assinatura, gate, manifestos/registros por fonte, inventário e relógios, auditorias RF/IF e hashes da candidata/implantada. Não persistir janelas no P11. Qualquer falha conserva o conjunto para diagnóstico e impede aceite; retorno zero do orquestrador significa verificações básicas de captura, não aceite de cobertura ou contrato.

Validação inicial Windows preservada em `WINDOWS_REGRESSION_RESULTS.json`: 60 testes, 58 aprovados e dois erros de plataforma `os.chown`. Pendência encerrada em Linux: **81/81 testes aprovados**, incluindo 21 P08, 46 adaptadores e 14 testes de lote/aplicação. `test_backup_and_exact_replacement` conferiu backup e substituição por hashes; `test_failure_restores_both_files` injetou falha na segunda substituição e conferiu restauração dos dois originais; o terceiro teste validou dry-run e rejeição de alteração inesperada. Nenhuma falha Linux exigiu correção no instalador. Os testes exercitam o instalador histórico de lote com fixtures fixadas, não demonstram instalação da candidata completa.

Execução em Docker Linux local, imagem `harpisense-backend:integration`, ID `sha256:be075ad0fc7764f9367712b7d8ef50ad63828c4cdf4a43c74a86cf6ff06dfa1b`, Python 3.12.15. Rede desativada, raiz somente leitura, capabilities removidas, `no-new-privileges`, limite de 128 PIDs, repositório montado somente leitura e `/tmp` efêmero. Somente diretórios sintéticos temporários foram alvos do instalador. Resultado, nomes dos testes e hashes do código em `LINUX_VALIDATION_RESULTS.json`. Comando reproduzível, na raiz da candidata (PowerShell):

```powershell
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --tmpfs /tmp:rw,nosuid,nodev,size=128m -e PYTHONDONTWRITEBYTECODE=1 -v "${PWD}:/work:ro" -w /work harpisense-backend:integration python p08_captura/tests/run_linux_validation.py
```

Entrega ao arquiteto: revisar candidata e manifesto de hashes, resolver inventário ESP32 e sensor do trecho Poste 2 → broker, validar exportação Windows e só então coordenar a execução legítima. Testes Linux concluídos; cobertura operacional e implantação da candidata permanecem não verificadas. Nenhuma implantação ou coleta está implicitamente autorizada por esta entrega.
