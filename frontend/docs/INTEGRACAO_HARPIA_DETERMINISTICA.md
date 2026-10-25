# Integração local HarpIA determinística

## Estado e limites

Esta branch parte da interface publicada `integration/harpia-ui` (`2fbb15c`) e importa o adaptador/serviço BitNet da entrega `origin/bitnet` (`650d1cd`). A comparação Qwen permanece em sua branch histórica; nenhum modelo Qwen, pacote, configuração ou dependência entrou nesta integração. BitNet é o único modelo previsto, mas sua geração continua **desabilitada operacionalmente**. Health e testes de transporte não liberam geração.

O endpoint P11 existente `GET /api/v1/p11/explain/{incident_id}` e o `GET /api/v1/p11/health` são mantidos. O complemento `genai/harpia/p11.py` substitui, em memória, o handler autenticado da explicação e acrescenta metadados de capacidade ao health. Ele exige as rotas P11 existentes com dependências de autenticação e o mesmo `Store` injetado pelo HarpiServer; falha fechado se não os encontra. Não cria rotas anônimas, tabela, banco, catálogo, gravações ou chamada ao BitNet. A consulta retorna `persisted:false`: calcula a explicação para a revisão atual, sem criar projeção de texto.

Não foi feito deploy nem consulta a serviços/VMs nesta rodada. O acesso real confirmado anteriormente cobriu health e telemetria; não há evidência aqui de incidente real disponível, nem da instalação deste handler no HarpiServer. A integração vista no navegador é validada com fixtures sintéticas de teste, nunca como incidente de laboratório.

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
2. No bootstrap atual do P11, após criar `app` com `create_app(store, ...)`, instale o complemento com `from genai.harpia.p11 import install_deterministic_harpia` e `install_deterministic_harpia(app, store)`. Mantenha o processo local protegido pelo mesmo Basic e o serviço BitNet em loopback.
3. Reinicie somente durante uma implantação aprovada, valide health autenticado e confirme exatamente `harpia.mode=deterministic_only`, `generation_enabled=false`, GET de incidente autenticado e explicação com ID/revisão/origem esperados. Confira que nenhuma escrita ou chamada ao runtime ocorre. Valide com incidente sintético isolado antes de consultar dados reais.
4. Para reverter, remova a chamada `install_deterministic_harpia` do bootstrap e reinicie segundo o procedimento do operador. Não remova modelos nem arquivos locais. Sem o complemento, o health não declara a capacidade e o frontend não chama a rota de explicação que poderia invocar inferência na API antiga.

Essas instruções são um roteiro; não foram aplicadas à VM e a substituição de `APIRoute.dependant.call` precisa ser repetida contra a versão FastAPI/P11 efetivamente implantada durante homologação. O pacote local usa FastAPI 0.115.0, conforme o ambiente P11 aprovado. Primeiro confirme a versão e teste o complemento em staging.

## Verificações e pendências

- Testes Python do complemento: app fixture com o mesmo protocolo de Store/rotas protegidas P11; cobrem campos completos/ausentes, RF/IF/risco, decisão e execução pendente/confirmada, texto malicioso excluído, 401, 404, revisão e origem. São fixtures, não integração com Postgres/HarpiServer real.
- Testes automáticos do frontend: autenticação, capability gating, vínculo, resposta antiga, indisponibilidade, texto escapado e fallback sem confusão de origem. Playwright também usa fixtures sintéticas. Build e testes unitários passaram.
- Transporte de verdade, banco, consulta de incidentes reais, instalação de rota no HarpiServer, modo com incidentes reais e recuperação ainda precisam de homologação em staging com o operador. Não houve deploy nesta entrega.
- A fidelidade textual do BitNet segue reprovada na validação anterior. A comparação histórica apontou resposta falsa sobre M3. Antes de qualquer ativação, reproduzir inferência com casos A/B, revisar entradas/saídas e controles de execução e obter aprovação de fidelidade específica. Nenhuma validação automatizada deste commit substitui essa etapa.
