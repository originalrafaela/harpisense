# Correções para receber características P08 reais

Ao Arquiteto — análise estática de 06/11/2026. Reutiliza o inventário de
`9ad9e0d`, `LAB_INVENTORY_20261105.json`, sem nova enumeração de bundles, hashes
ou ambientes. Escopo: oito bundles sintéticos já inventariados e fontes da linha
`7fe8294`/`4c30d59`, consultadas em leitura na worktree da composição. Nenhum
modelo carregado, ajustado ou alterado; nenhuma composição, VM ou captura executada.

## Resultado por dimensão

| Dimensão | Constatação | Correção/decisão necessária |
|---|---|---|
|Nomes e ordem|As nove features e sua ordem coincidem nos oito metadados e no default P08.|Nenhuma renomeação. Selecionar por nome na ordem de cada bundle pelo validador oficial; não usar ordem incidental do JSON.|
|Tipos|P08 produz contagens int e razões/médias float; RF/IF recebem float32 após validação numérica.|Preservar inteireza das contagens antes da conversão, rejeitar bool/NaN/infinito/negativos. Não criar scaler ou arredondamento adicional.|
|Janela|Duração nominal coincide: 10 s. P08 agrupa por sensor+origem+destino em buckets UTC [início,fim) alinhados à época. Geradores criam linhas de 10 s, sem timestamps de pacotes que demonstrem essa janela.|Para dados reais, exigir intervalo integral dentro da sessão/cobertura. Não dividir pelas frações efetivamente capturadas nem promover bordas parciais.|
|Perfil/população|P08 usa tcp-observacao; todos os bundles inventariados usam demo_tcp_ingress. O validador exige igualdade de perfil.|Definir perfil operacional com sensor, direção, filtro e procedência; disponibilizar futuramente bundles treinados/calibrados para essa população. Renomear perfil não resolve.|
|Pré-processamento|RF e IF usam windows.validate: colunas por nome, coerência, seleção na ordem do bundle e float32. Não há normalização/imputação no caminho lido.|Reutilizar essa transformação no ingresso real. Nenhuma mudança de escala dos dados P08 é indicada pela análise.|

Ordem preservada: `packet_count`, `bytes_total`, `packets_per_second`,
`connections_per_second`, `syn_count`, `rst_count`, `unique_dst_ports`,
`avg_packet_size`, `mean_interarrival_ms`.

## Divergências de significado que nomes iguais escondem

1. **Interarrival — divergência demonstrável no gerador.** P08 calcula
   `(último_timestamp − primeiro_timestamp) × 1000 / (n−1)`, com zero apenas para
   n≤1 observado. Ambos os geradores usam `10000/n`, uma aproximação baseada na
   duração nominal, sem timestamps. Exemplo analítico, não medição: quatro pacotes
   em 1, 1,5, 2 e 3 s dão 666,67 ms no P08; o gerador dá 2500 ms. Ambos podem
   passar o validador, que não recompõe timestamps. **Ação futura:** gerar treino,
   calibração e avaliação a partir do mesmo agregador de eventos reais; não alterar
   a fórmula P08 para imitar o sintético nem corrigir o bundle já ajustado.

2. **Conexões — estimativa por tentativa, não conexão estabelecida.** P08 conta
   pares distintos (porta origem,destino) com SYN sem ACK por bucket, dividido
   por 10. syn_count inclui retransmissões. Geradores usam syn_count/10, sem
   representar portas/retransmissões. Exemplo: dois SYN do mesmo par dão 0,1/s
   no P08 e 0,2/s pela fórmula do gerador. **Ação futura:** registrar esse significado
   no contrato de treino e produzir ambos os campos pelo agregador; não substituir
   tentativas distintas por número de pacotes SYN. SYN repetido ainda é pacote em
   packet_count/bytes_total: a deduplicação de tentativas não deduplica tráfego TCP.

3. **Bytes — unidade do caminho real é IP.** Conversor preservado usa
   IPv4.total_length, incluindo cabeçalhos IP/TCP e payload, excluindo Ethernet.
   bytes_total soma esses valores; avg_packet_size divide por n. Geradores usam
   n×size e size, sem pacote bruto que comprove a camada de origem. Não há prova
   de que esses bundles tenham treinado em bytes Ethernet: há ausência de
   procedência física da variável sintética. **Ação futura:** fixar bytes IP no
   manifesto de aquisição/treino e usar o conversor preservado. Saída L2 de outro
   exportador não é substituta; não subtrair 14 bytes indiscriminadamente.

4. **População — unidades iguais não garantem distribuição.** P08 seleciona uma
   interface e direção destino=broker; unique_dst_ports é cardinalidade das portas
   TCP nessa população, packet_count inclui pacotes de controle, não mensagens
   MQTT. Geradores sorteiam contagens/portas/bytes por rótulo. **Ação futura:**
   declarar filtro TCP entre os IPs, direção, posição do sensor e tratamento de
   retransmissões no treino. Não adicionar filtro port1883 silenciosamente nem
   somar tráfego inverso para aproximar os dados do treino sintético.

5. **Logs opcionais — origem diferente de rede.** RF demo cria zeros opcionais
   artificiais; os oito bundles inventariados selecionam somente as nove features
   base, portanto isso não é coluna ausente nesses bundles. Para futuros bundles
   que exijam logs, aceitar apenas contagem vinculada à fonte e cobertura da
   janela. O mapeamento existente não produz connection_failures,
   admin_auth_failures ou mqtt_publish_count. **Ação futura:** implementar e validar
   os mapeamentos requeridos antes de escolher tais features; nunca portar o
   preenchimento sintético com zeros para o caminho real. As fontes obrigatórias
   continuam necessárias mesmo com bundle que não seleciona opcionais.

## Lista de ações para o Arquiteto, em ordem de dependência

1. Aprovar um contrato de aquisição/treino único: bytes IP, tentativas SYN distintas,
   interarrival observado, direção/interface/filtro e buckets UTC10s. As fórmulas
   P08 e o preparador P09 já coincidem para os mesmos eventos; não há motivo
   demonstrado para alterar o legado.
2. Preparar futuramente dados reais com esse agregador e perfil, em sessões
   independentes para treino, calibração e avaliação. IF exige normal revisado;
   RF exige classes configuradas e rótulos revisados. Uma sessão benigna de120s
   produz no máximo12 buckets inteiros e não atende sozinha aos mínimos de treino
   existentes, nem comprova classes RF. Não treinar nesta rodada.
3. Disponibilizar bundles operacionais com procedência e pins externos confiáveis;
   preservar os oito bundles atuais como demonstração. A igualdade de hash com
   metadata local já inventariada não substitui confiança externa. Preservar as
   versões exatas exigidas pelo loader (incluindo Python), registradas no inventário;
   compatibilidade do instalador não homologa o modelo.
4. No ingresso real, usar windows.validate e o auditor já existente, conservando
   IDs legados e alias v2 separados. Comprovar sessão/fontes/relógios e janelas
   integrais. O validador tabular sozinho não comprova a fórmula de interarrival,
   a deduplicação de SYN ou o limite temporal entre hosts.
5. Após as evidências e revisão do dono da composição, implementar a passagem real
   pelo gate: process_p08 atualmente sempre termina em DependencyBlocked.
   Não remover essa proteção apenas porque nomes/dtypes coincidem. Esta análise
   não solicita alteração automática do gate ou persistência P11.

## Evidências de código consultadas

Caminhos relativos à worktree detection-composition, sem modificar esses arquivos:

- `backend/p08_p09/compatibility_sources/edge_features.py:51–66`: buckets,
  tentativas distintas, bytes e intervalo observado.
- `backend/p08_p09/compatibility_sources/pcap_to_events.py:74–107,190–201`:
  bytes IP e timestamps convertidos a microssegundos. Essa precisão deve acompanhar
  a procedência do treino; não há demonstração de precisão temporal nos geradores.
- `backend/domain/harpisense_rf/demo_sintetico.py:13–21` e
  `backend/domain/harpisense_if/demo_sintetico.py:12–30`: fórmulas aproximadas.
- `backend/detection_composition/tests/test_composition.py:20–55`: uso dos
  geradores e ajuste dos estimadores da demonstração.
- `backend/domain/harpisense_data/windows.py:60–122`: coerência, duração,
  ausência rejeitada e transformação float32; `preparar_eventos.py:aggregate`
  reproduz as fórmulas observadas do agregador P08.
- `backend/domain/harpisense_rf/random_forest.py:predict_windows/load_bundle` e
  `backend/domain/harpisense_if/isolation_forest.py:predict_windows/load_bundle`:
  mesmo pré-processamento; RF retorna probabilidade calibrada, IF retorna
  -score_samples/limiar/percentil. Esses resultados têm significados diferentes
  e não devem receber conversão única para “probabilidade de ataque”.

Validação desta entrega: leitura estática e exemplos aritméticos explicitamente
declarados, sem execução de testes/modelos ou nova evidência de laboratório.
