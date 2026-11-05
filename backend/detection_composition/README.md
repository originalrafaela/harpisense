# Composição de detecção, sem executor

Base `9d35906`; novos módulos em `backend/detection_composition/`. RF, IF, dados e
XAI são cópias byte a byte do P09 aprovado em `referencias/versão_v2`; origem em
`ORIGINS.json`. Contratos, catálogo, Risk/Policy e `PostgresStore` existentes são
reutilizados. A correção vigente M2 (Medium manual) é preservada, apesar da matriz
anterior ainda presente no ZIP P09. Não se reinstala apresentação nem MFA.

O comando abaixo ajusta e calibra estimadores sklearn reais usando os geradores
**sintéticos** entregues, salva/carrega bundles com SHA256 fixado, executa inferência,
Risk/Policy, transação PostgreSQL e consultas P11 autenticadas. Não usa estimador
mock. Esses modelos não são modelos operacionais nem evidência estatística.

Executar na raiz desta worktree:

```powershell
docker build -t harpisense-detection:integration -f backend/detection_composition/Dockerfile .
docker compose -p harpisense-detection-test -f backend/detection_composition/compose.test.yml run --rm test
docker compose -p harpisense-detection-test -f backend/detection_composition/compose.test.yml down
```

O banco é descartável, sem porta publicada, numa rede Docker interna. Dados reais
não são usados. CSVs e bundles permanecem localmente em
`local-evidence/detection-composition/<execução>/`, ignorados pelo Git; hashes,
versões, registros e respostas P11 ficam em
`docs/evidence/detection-composition-20261104/`. Cada execução gera modelos novos;
seus identificadores, bytes e hashes podem variar. O teste comprova contratos e
funcionamento do código, sem medir eficácia. A API é exercitada por TestClient com
o store PostgreSQL real, não por navegador nem conexão HTTP remota.

O escritor offline também é invocável por `python -m detection_composition --help`,
com `PYTHONPATH=backend/domain:backend:backend/p08_p09/adaptador_logs_p08_p09` em Linux.
Recebe caminhos confiáveis dos dois bundles, hashes fixados pelo instalador, JSON
de entrada, origem explícita e horário com fuso. A entrada sintética contém
`{"window": {...}, "asset": ...}`; os campos opcionais de contexto são os do motor
existente. Apenas o banco `detection_composition_test` aceita esse escritor
sintético, inclusive por chamada direta ao store. Nenhuma rota HTTP nova foi
aberta e nenhum executor foi importado.

Cada composição grava atomicamente `window`, duas `detection`, `incident`, `risk`
e `decision`. Detecção, incidente e decisão seguem os contratos canônicos. A
projeção `risk` é uma consulta derivada de `incident.risk`, com `incident_id`, revisão
e auditoria do motor; não constitui outro contrato de decisão. Não cria migração,
tabela paralela, mecanismo de aprovação ou caminho de execução.

O identificador da composição vincula sessão/janela/sensor e versões RF/IF. Uma
repetição idêntica devolve o snapshot original, mesmo com novo horário de consulta;
alterar dados/contexto/perfil sob esse identificador é conflito explícito. Gravações
concorrentes são serializadas; qualquer falha aborta o conjunto inteiro. Atualizar
um incidente com outra versão de modelo ainda exige coordenação de revisão pelo
serviço de domínio; esta entrega não sobrescreve revisão existente.

## Limite operacional explícito

`process_p08` chama o pipeline entregue da Edge, incluindo a entrada exclusiva de
lote quando informada, e retorna `DependencyBlocked` com seu diagnóstico. O gate
atual não autoriza inferência nem contagens, mesmo com cobertura assinada verificada.
A composição não aceita `authorized_for_inference=true` fornecido pelo cliente,
não converte UNKNOWN, não fabrica características e não libera o gate.

Não há bundles treinados nas referências verificadas, incluindo ZIPs dos pacotes
anteriores. No staging P09 legível da VM também não foi encontrado bundle; houve
acesso negado a um backup, portanto não se afirma inexistência global na VM.
O caminho P08 de laboratório continua pendente, conforme a matriz de entrega.

As nove características usadas no ensaio sintético mantêm a ordem de
`harpisense_data.windows.FEATURES`: `packet_count` (contagem), `bytes_total`
(bytes), `packets_per_second` (pacotes/s), `connections_per_second` (conexões/s),
`syn_count`, `rst_count`, `unique_dst_ports` (contagens), `avg_packet_size` (bytes)
e `mean_interarrival_ms` (ms). Schema `harpisense.if.window.v1`, perfil
`demo_tcp_ingress`, janela 10 s. A transformação oficial valida consistência,
seleciona por nome na ordem do bundle e converte para float32. RF preserva
probabilidades calibradas por sigmoid em sessões separadas; IF preserva
`-score_samples`, limiar e percentil de referência. Risco é calculado separadamente
pelo motor. Nenhuma feature auxiliar ausente é preenchida.
