# Integração progressiva e divergências

## Fontes e precedência

Raiz Git confirmada com `git rev-parse --show-toplevel`. Base `integration/primeira-entrega` em `a7cb501`: inclui `main` e merges de backend-data, edge-security e iot-mqtt. A `main` em `9d58e69` não contém essa integração. Não havia branch frontend nem worktree correspondente antes desta tarefa; foram criadas e depois reconferidas para reutilização. Nenhum AGENTS.md ancestral aplicável foi encontrado; arquivos de papéis em `.maestri/roles` são de outros diretórios.

Referências originais consultadas somente para leitura em `referencias/versão_v2/` (o nome real difere de `Versao_v2`). Fontes: escopo oficial DOCX; README e pendências de topologia P02; contratos oficiais, catálogo e dicionário de interface P03; README, autenticação, contratos, estados, `backend11/service.py`, `backend11/bitnet.py`, `.env.example` e pacote legado P11; relatório PDF `HarpiSense_V2_Relatorio_Fluxo_Poste2_MQTT_PostgreSQL_API.pdf`, extraído integralmente. Proposta visual em `versão_v2/proposta_visual`: `dash-proposta-visual.png` substitui o nome não encontrado `dahs-harpi_v1.png`; emblema e logo copiados como assets. Pastas externas `referencias/proposta_visual/` e `referencias/relatorios/` não foram encontradas; os documentos estão dentro da V2.

O escopo/topologia inicialmente prevê núcleo no Windows. O relatório posterior e a instrução atual colocam PostgreSQL, consumidor e API no HarpiServer Ubuntu, com Mosquitto/BitNet no Windows. A interface não configura hospedagem e adota URL externa configurável. Divergência registrada, sem reescrever contratos.

O Git implementa telemetria v1 com `measurements` em `/api/v1/telemetry`. O P11 de referência usa projeções em `/api/v1/p11/{kind}` com armazenamento SQLite de referência. O relatório descreve PostgreSQL e consumidor posterior, com `data.temperatura` e `data.tipo`, que não equivalem a luminosidade. A API de VM não foi acessada; seu `app.py`, `postgres_store.py` e `mqtt_consumer.py` não foram inspecionados diretamente. O P11 de referência não prova disponibilidade de todos os recursos na VM.

## Matriz tela → endpoint → contrato → estado

Todos os endpoints abaixo são **GET**. Nenhuma integração real com VM foi validada nesta entrega. “P11 referência” significa implementado no código local fornecido, não homologado no servidor atual.

| Tela | Endpoint/recurso | Contrato | Estado |
|---|---|---|---|
| Login | `p11/telemetry?limit=1&offset=0` | Basic + lista de projeções | implementado; teste isolado |
| Dashboard | `p11/{asset,telemetry,incident,decision,execution,health}` | projeções P11 e mapa de saúde | leitura preparada; contagens da página, não totais globais |
| Postes/telemetria | `p11/{telemetry,asset}` | projeção e payload preservado | telemetry documentado na VM; asset somente referência |
| Incidentes | `p11/{incident,evidence,decision}` | projeções; canônico P03 ainda requer mapeamento do produtor | consulta e detalhes preparados |
| IA/XAI | `p11/{detection,xai,risk}` | projeções; campos semânticos P03 | consulta preparada; sem inferência no navegador |
| Aprovações | `p11/{approval,decision}` | projeções | consulta; aprovar/rejeitar desabilitados |
| Tráfego | `p11/network_event` | projeção; aggregations originais | consulta preparada |
| Defesas | `p11/{decision,execution,verification}` | estados canônicos P03 dentro da projeção | separação proposta/simulada/demais; sem comando |
| HarpIA | `p11/bitnet` | projeções de explicação; origem precisa ser informada | consulta preparada; sem chat |
| Inventário | `p11/asset` | projeção | consulta; sem cadastro |
| Saúde | `p11/health` | mapa do P11 | API e projection_store não atestam demais serviços |
| Laboratório | catálogo P03 local gerado | C01–C09 oficial + ações | sem API de ensaios; não executado |
| Backup | nenhum | contrato de histórico não fornecido | estados e evidências não informados |
| Auditoria | nenhum | contrato de leitura não fornecido | estrutura própria; sem histórico fictício |
| Configurações | somente preferências locais | URL/perfil | sem controle operacional remoto |

Prefixo completo P11: `/api/v1/p11/`. O perfil `legacy`, escolhido explicitamente, consulta `/api/v1/telemetry`, `/api/v1/network-events`, `/api/v1/health`, encontrados no código Git. Outros recursos ficam não configurados. Não há detecção automática de versão ou fallback.

## Adaptações de apresentação

- `adaptRows`: exige array; P11 exige id string, revision inteiro, source string e data objeto. Legacy preserva o registro em data. Resposta inválida é erro, nunca lista vazia.
- Os campos adicionais da projeção continuam acessíveis em Detalhes. A origem `source` da projeção não equivale automaticamente à origem de uma explicação.
- Telemetria: device_id identifica dispositivo; observed_at é observação, sem substituir pelo created_at de ingestão. LDR só usa `measurements.ldr_raw` como valor bruto. `measurements.luminosity_lux` somente seria mostrado como lux se emitido explicitamente pelo produtor, sem conversão no frontend. Esses dois campos e `status.led` são suportes de apresentação provisórios, **não novo contrato oficial**: confirmar payload físico com o Arquiteto. Campo ausente é não informado. Payload provisório `temperatura` permanece no detalhe e não preenche luminosidade.
- Leitura antiga/desconhecida é indicada; recente tampouco confirma estado atual. Janela de 120 segundos é somente indicação visual, sem critério de saúde ou autorização.
- RF: classification.attack_probability; IF: anomaly.anomaly_score, nunca probabilidade. Risco não é derivado de RF/IF na interface.
- SIMULATED fica separado dos demais estados. Os estados oficiais são preservados textualmente. COMMAND_ACCEPTED não é eficácia; verificação e reversão dependem de evidência.
- Autonomia, operação e execution_enabled ficam não informados: não existe endpoint de controles consultado, e uma decisão histórica não informa configuração atual.

## Dependências exatas para o Arquiteto

1. Fornecer código sanitizado atual de `/opt/harpisense/staging/p11-postgresql/app.py`, `postgres_store.py`, `mqtt_consumer.py` e OpenAPI ou amostras das respostas autenticadas de telemetry e health. Confirmar credenciais pelas variáveis efetivas, sem enviar segredos.
2. Definir URL autorizada acessível ao navegador, proxy/túnel e HTTPS/CORS restrito. Não presumir que a API loopback da VM esteja acessível no Windows.
3. Confirmar quais recursos P11 realmente existem e o mapeamento canônico de incident, detection, xai, risk, decision, approval, execution, verification, asset, network_event e bitnet. Precisam incluir vínculos por ID/revisão e proveniência.
4. Telemetria de iluminação: campos/unidades calibradas, LED, timestamps de observação e recepção, identidade físico/simulado e semântica de última comunicação. Não usar temperatura como substituição.
5. Aprovações: operações autorizadas, payload de justificativa, prazo, controle de revisão/concorrência, resposta efetiva e idempotência antes de habilitar botões.
6. Controles: endpoint de valores efetivos e alteração auditada de operation, execution_enabled e autonomy_mode. Frontend não implementa gates de Policy/Risk.
7. Saúde: status por PostgreSQL, MQTT, processamento, RF/IF, BitNet e executor com observação/frescor. Não inferir de api=available.
8. Backup: histórico de geração/envio, integridade e evidência de restauração verificada; somente consulta. Auditoria: endpoint paginado com ator, horário, ação, entidade/revisão e resultado.
9. Ensaios: API de resultados/evidências C01–C09 com ID, execução, horário e conclusão. Não há evidência de ataque nesta entrega.
10. Explicações: confirmar projeções bitnet na VM. O P11 local também possui `/api/v1/p11/explain/{incident_id}` (não utilizado), cuja resposta usa `source`, `text`, `revision`, `bitnet_status`. Não confundir source da projeção com esse source interno; futura adaptação deve preservar origem real, fallback e indisponibilidade.
