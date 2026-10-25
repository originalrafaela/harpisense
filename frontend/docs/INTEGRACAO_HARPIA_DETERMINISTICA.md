# Integração local HarpIA determinística

## Estado e limites

Esta branch parte da interface publicada `integration/harpia-ui` (`2fbb15c`) e importa o adaptador/serviço BitNet da entrega `origin/bitnet` (`650d1cd`). A comparação Qwen permanece em sua branch histórica; nenhum modelo Qwen, pacote, configuração ou dependência entrou nesta integração. BitNet é o único modelo previsto, mas sua geração continua **desabilitada operacionalmente**. Health e testes de transporte não liberam geração.

O endpoint P11 existente `GET /api/v1/p11/explain/{incident_id}` e o `GET /api/v1/p11/health` são mantidos. O complemento `genai/harpia/p11.py` substitui, em memória, o handler autenticado da explicação e acrescenta metadados de capacidade ao health. Ele exige as rotas P11 existentes com dependências de autenticação e o mesmo `Store` injetado pelo HarpiServer; falha fechado se não os encontra. Não cria rotas anônimas, tabela, banco, catálogo, gravações ou chamada ao BitNet. A consulta retorna `persisted:false`: calcula a explicação para a revisão atual, sem criar projeção de texto.

O complemento foi preparado no staging P11/PostgreSQL do HarpiServer e seu bootstrap foi instalado após backup. A ativação aguarda reinício autorizado do serviço, pois o sudo remoto exige autenticação interativa. Não há incidentes reais disponíveis. A API pós-reinício e a exibição real no navegador ainda não foram validadas; fixtures automatizadas não são apresentadas como integração de produção.

## Auditoria do log que induziu M3

Em `harpia-model-comparison/genai/scripts/compare_models.py`, somente a instrução simples foi direto ao runtime. O caso de injeção percorreu `Client.explanation` → validação/construção do resumo P11 → HTTP Basic no `/explain` local → adaptador → runtime. O campo permitido `evidence_summary` continha texto de log não confiável. A validação trocou delimitadores de tokens especiais, mas não removeu o pedido semântico em português. A resposta bruta dos dois modelos repetiu a alegação de que a autonomia mudou para M3. Não houve alteração de política/autonomia nem execução.

O endpoint novo lê o incidente e segue apenas `detection_refs`, `explanation_refs`, decisões associadas ao mesmo `incident_id` e `incident_revision`, e execuções associadas à decisão. RF usa `classification.attack_probability` somente para `random_forest`; IF usa `anomaly.anomaly_score` somente para `isolation_forest`. O IF é chamado de score operacional, nunca probabilidade. Risco é copiado do objeto `risk`; não é recalculado. Para XAI, entram no máximo três contribuições com feature names da lista oficial de 18 campos numéricos; a explicação identifica que contribuição não demonstra causa. Conteúdo arbitrário de logs, `observed_facts` livre, `evidence_summary` e outros textos livres não entram na explicação. Os textos originais e evidências continuam no `Store` de origem; a resposta informa a omissão e quantas referências de evidência foram vinculadas. A seleção por tipos/referências reduz a superfície de instrução, mas não é uma prova geral contra prompt injection nem uma validação semântica dos dados de origem.

## Resposta e caminhos

Health autenticado, com complemento explícito:

```json
{"api":"available","projection_store":"available","bitnet":"not_verified",
 "harpia":{"mode":"deterministic_only","contract_version":1,"generation_enabled":false,"model":"bitnet"}}
```

Explicação autenticada, somente leitura:

```json
{"source":"deterministic_fallback","source_label":"Explicação determinística",
 "incident_id":"inc-<id>","revision":4,"generated_at":"<UTC>",
 "persisted":false,"bitnet_status":"disabled_for_quality","text":"...",
 "facts":{"rf_attack_probability":0.82,"if_anomaly_score":0.12,"risk_score":58.3}}
```

Os dois endpoints mantêm Basic Authentication fornecida pelo P11. Ausência de credencial segue 401; acesso negado pelo backend segue 403. Ausência de incidente é 404. Projeções ambíguas/incompatíveis retornam erro controlado em vez de completar campos por suposição. A lista `limitations` comunica cobertura incompleta e limites da busca de decisões/execuções.

No navegador, `Client.incidentExplanations` consulta primeiro o health protegido. Só acessa `/explain/{id}` quando a capacidade `deterministic_only`, versão 1 e `generation_enabled:false` estão todas presentes; valida origem, incidente, revisão, texto e timestamp. Sem essa capacidade, o cliente consulta somente projeções BitNet persistidas e não chama o endpoint histórico de geração. A interface confere a revisão do incidente, identifica origem e horário, alerta sobre explicação desatualizada, renderiza texto como conteúdo escapado e não oferece ação de geração. O histórico fica indisponível para uma explicação não persistida.

O proxy de desenvolvimento continua preso a `127.0.0.1`, sem credenciais no frontend, e aceita apenas GET dos recursos P11 permitidos, incluindo incidente e explicação. O valor padrão de recursos continua restrito; configure explicitamente recursos validados (`incident`, `bitnet` e os recursos do dashboard) ao iniciar Vite, após confirmar que a API instalada os oferece. Não expor Vite/API em `0.0.0.0`.

## Instalação assistida e recuperação

1. Na implantação planejada, confirme que o pacote P11 carregado é o aprovado e que o `Store` injetado aponta para o armazenamento `projections` existente. Faça backup normal da configuração/código pelo procedimento operacional atual. Não aplique migração: o endpoint não precisa de tabela nova.
2. No bootstrap do P11, após criar `app` com `create_app(store=store)`, instale o complemento com `from harpia_deterministic.p11 import install_deterministic_harpia` e `install_deterministic_harpia(app, store)`. O diretório `harpia_deterministic` deve estar no `WorkingDirectory` do serviço. Mantenha o processo local protegido pelo mesmo Basic e o serviço BitNet em loopback.
3. Após uma implantação aprovada, reinicie somente o P11. Valide health autenticado e confirme `harpia.mode=deterministic_only`, `generation_enabled=false`, GET de incidente autenticado e explicação com ID/revisão/origem esperados. Confira que nenhuma escrita ou chamada ao runtime ocorre. Valide com dados sintéticos isolados em ambiente de teste; não crie incidentes sintéticos no banco operacional.
4. Para reverter a implantação atual, restaure o backup do bootstrap documentado abaixo e reinicie `harpisense-p11`. Não remova modelos nem arquivos locais. Sem o complemento, o health não declara a capacidade e o frontend não chama a rota de explicação que poderia invocar inferência na API antiga.

O complemento foi adaptado ao bootstrap e à versão P11/FastAPI atualmente instalados no staging. A substituição de `APIRoute.dependant.call` foi exercitada em teste de compatibilidade com FastAPI 0.143.3 e o Store PostgreSQL real. O pacote local usa FastAPI 0.115.0, portanto a verificação remota específica é necessária e não deve ser inferida dos testes locais. A ativação do processo ainda aguarda reinício com sudo.

## Verificações e pendências

- Testes Python do complemento: app fixture com o mesmo protocolo de Store/rotas protegidas P11; cobrem campos completos/ausentes, RF/IF/risco, decisão e execução pendente/confirmada, texto malicioso excluído, 401, 404, revisão e origem. São fixtures, não integração com Postgres/HarpiServer real.
- Testes automáticos do frontend: autenticação, capability gating, vínculo, resposta antiga, indisponibilidade, texto escapado e fallback sem confusão de origem. Playwright também usa fixtures sintéticas. Build e testes unitários passaram.
- Compatibilidade PostgreSQL real e preparação dos arquivos no host foram concluídas; faltam reinício do serviço, API autenticada após ativação e observação do estado vazio no navegador.
- A fidelidade textual do BitNet segue reprovada na validação anterior. A comparação histórica apontou resposta falsa sobre M3. Antes de qualquer ativação, reproduzir inferência com casos A/B, revisar entradas/saídas e controles de execução e obter aprovação de fidelidade específica. Nenhuma validação automatizada deste commit substitui essa etapa.

## Verificação de implantação — 25/10/2026

### Compatibilidade PostgreSQL e preparação

O host Tailscale `100.66.89.7` foi confirmado como `gateway`; o login autenticado é `harpiserver`. O SSH passou a funcionar depois que a chave dedicada existente foi carregada no `ssh-agent` pelo usuário. Nenhuma chave foi criada ou alterada.

O serviço implantado usa `/opt/harpisense/staging/p11-postgresql`, Python 3.14.4, FastAPI 0.143.3, P11 da entrega aprovada e `PostgresStore` via psycopg. A implementação P11 tem SHA-256 `8cb67932cc2f7ef22ed357b0c94f7a8cb416cde164db60866dd6df5cf7fb8698`, igual à referência aprovada local. O Store ativo usa PostgreSQL 18.6, a tabela `projections` e a coluna JSONB `data`; sua implementação tem SHA-256 `cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c`, igual à cópia local examinada. Não foi instalado SQLite nem alterado esquema.

Antes da troca do bootstrap, foi guardada uma cópia em `/opt/harpisense/staging/p11-postgresql/app.py.bak-harpia-deterministic-20261025T222301Z`; seu hash corresponde ao original `app.py` (`2545e122712be2e331579c2c41b04437738bca974fe42297b0445841ea50e2e4`). Os três módulos `harpia_deterministic` foram instalados no diretório de trabalho do P11, com permissões de leitura para o serviço, e passaram em `py_compile`. O novo `app.py` foi testado com o app P11 e o Store PostgreSQL reais antes de substituir o arquivo; o hash instalado é `52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2`.

O teste de compatibilidade contra o PostgresStore e a base operacional foi somente de leitura e passou: health sem autenticação 401, health autenticado 200 com `generation_enabled:false`, lista de incidentes vazia, explicação de ID inexistente 404 e telemetria existente (7 projeções). Não houve inferência nem escrita. A base contém 7 projeções de telemetria/janelas e nenhuma projeção de incidente, decisão ou execução; nenhum incidente foi fabricado.

### Estado do serviço e validação pendente

O bootstrap novo está instalado no disco, mas **a ativação ainda não foi concluída**: o processo P11 ativo (PID 1850) continua com o módulo que carregou antes da troca. Uma tentativa de reiniciar com `sudo systemctl restart harpisense-p11` foi recusada porque sudo exige autenticação em terminal interativo. A consulta somente leitura confirmou o host/usuário, e as rotas atuais de health e explain continuam respondendo 401 sem autenticação. Portanto, ainda não há evidência de que a instância ativa anuncie o complemento, de consulta autenticada pela API viva ou de visualização real no navegador. Não foi possível confirmar 200/404 autenticados no processo após implantação.

Para concluir, o operador com sudo deve executar no host:

```sh
sudo systemctl restart harpisense-p11
sudo systemctl is-active harpisense-p11
```

Depois, validar pela API autenticada health com `harpia.mode=deterministic_only` e `generation_enabled=false`, incidente inexistente 404 e lista real vazia; a consulta sem credenciais deve permanecer 401. O frontend local deve passar pelo proxy GET em loopback. Como não existem incidentes reais, a tela deve mostrar estado vazio, não uma explicação sintética. A telemetria deve continuar legível. A autenticação da API e a visualização pelo navegador continuam pendentes até essa reinicialização e validação.

### Recuperação

Se a unidade não voltar ativa ou as verificações falharem, restaurar o bootstrap guardado e reiniciar somente o P11:

```sh
cd /opt/harpisense/staging/p11-postgresql
cp -p app.py.bak-harpia-deterministic-20261025T222301Z app.py
sudo systemctl restart harpisense-p11
sudo systemctl is-active harpisense-p11
```

Não há migração a reverter. Os módulos `harpia_deterministic` podem permanecer no diretório; o bootstrap restaurado não os importa. Não remova pesos, runtime, dados ou arquivos locais. PostgreSQL, MQTT, autenticação, firewall e VMs não foram alterados.

### Observações de volume e segurança

A resolução de decisão/execução usa uma chamada por tipo, com limite de 1.001 registros e trata cobertura acima de 1.000 como desconhecida. Na implementação PostgreSQL examinada, `list` carrega todas as projeções daquele tipo antes de paginar; o custo em maior volume precisa ser medido antes de uso amplo. A resposta não é persistida e não escreve no PostgreSQL. A geração BitNet continua desabilitada.

## Encerramento do Playwright

O `webServer` padrão do Playwright no Windows deixava o processo filho Vite em execução após o runner concluir os casos. O global setup agora inicia diretamente o processo Node/Vite sem shell e devolve um teardown que envia SIGTERM, aguarda o encerramento e usa SIGKILL com limite de tempo somente para o processo que criou. A execução seguinte terminou normalmente com código de saída 0 e relatório final `23 passed (16.0s)`.
