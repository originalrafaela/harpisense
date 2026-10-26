# Paginação do PostgresStore P11 real

Entrega sem implantação, 2026-10-26; validação complementar PostgreSQL 18.6 do
commit `45603a9`. Branch `fix/p11-postgres-pagination`, baseada
em `main` 9d58e69; nenhuma substituição pela implementação de `backend-data`.
O único arquivo destinado à operação é `postgres_store.py`. `tests/fixtures`
contém cópias de código para comparação e integração, nunca configuração da VM.

## Base conferida

Inspeção SSH somente leitura em `/opt/harpisense/staging/p11-postgresql`:

| Código ativo | SHA256 |
|---|---|
| postgres_store.py | cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c |
| app.py | 52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2 |
| harpia_deterministic/p11.py | 2eecc6ffc53a1ddc236e16202ddc2f62d4a8c8371e6386f1fd1df705a62e8297 |
| harpia_deterministic/deterministic.py | 372660d795c0cd27c6cf43e2afde0085f57113e292a46209e3312ae5f7f13e57 |

`tests/fixtures/previous_store.py` é cópia byte a byte do Store ativo, obtida
individualmente por SCP. As fixtures HarpIA locais têm os mesmos hashes acima.
O `app.py` ativo injeta esse Store no `create_app` aprovado e instala a explicação
determinística. Seu código foi lido, mas não precisa ser alterado ou distribuído.

Referência mais recente: `referencias/versão_v2`, P11 e componentes P11 do pacote
P13. A API realmente importada fica em
`/opt/harpisense/integration-v2/HarpiSense_Pacote13_Integracao_Testes_v2/componentes/p11/backend11/service.py`;
hash `8cb67932cc2f7ef22ed357b0c94f7a8cb416cde164db60866dd6df5cf7fb8698`,
igual à fixture proveniente desse pacote local aprovado. As três fontes Python
de `backend11` são fixtures desse pacote. Não foi necessário recorrer a versões
anteriores: nenhum componente foi considerado ausente por não estar na V2.

Metadados consultados em transação somente leitura, sem ler linhas operacionais:
PostgreSQL 18.6; timezone `America/Sao_Paulo`; `projections` tem `kind`, `id`,
`source` text, `revision` integer, `data` jsonb, `created_at` timestamptz, todos
NOT NULL. Índices presentes: `projections_pkey(kind,id,revision)` único e
`audit_pkey(seq)` único. A conexão foi usada apenas dentro da VM: nenhuma
credencial, `.env`, senha ou dado operacional foi copiado.

## Semântica identificada antes da edição

- `list(kind, limit=50, offset=0)` retorna uma lista de dicionários com `id`,
  `revision`, `source`, `data` (JSON decodificado) e `created_at` (isoformat).
- Único filtro aceito: `kind` pertencente ao conjunto KINDS. Não há filtros por
  payload, status, origem, ID ou intervalo nesta assinatura/API.
- Última revisão significa maior número de revisão por `(kind,id)`, mesmo se
  seu timestamp for anterior ao de uma revisão menor. O filtro de tipo é anterior
  a essa seleção; não há filtro de payload no Store.
- Ordem antiga: string `created_at.isoformat()` DESC, ID DESC (ordem Unicode do
  Python). Não usar a ordem ID ASC do Store SQLite de referência como contrato
  do PostgresStore real.
- Paginação antiga: slice Python depois de selecionar e ordenar todas as últimas
  revisões do tipo. Nova consulta: mesma seleção em subconsulta, seguida de ORDER
  BY, LIMIT e OFFSET parametrizados. Somente a página atravessa o driver.
- Para preservar a ordem textual antiga inclusive em sobreposição de horário de
  verão, o SQL ordena por horário local da sessão, offset textual e ID com
  `COLLATE "C"`. Isso preserva o comportamento existente; não o converte para
  ordenação por instante UTC. Resolução de microsegundos e timezone da conexão
  permanecem as mesmas. A data retornada continua usando `isoformat()`.
- `history(kind,id)` não muda: todas as revisões em ordem crescente, retornando
  apenas `revision`, `source`, `data`; tipo inválido gera ValueError.
- A API mantém autenticação, limite HTTP 1..200, offset >=0, 404 para tipo
  desconhecido, ingestão e formatos. Não houve alteração nas rotas.
- A HarpIA usa history para incidente/referências e list com limite 1001 como
  sentinela. Seus filtros de vínculo/revisão são **posteriores à seleção das
  últimas revisões e à paginação**. Com mais de 1000 candidatos mantém cobertura
  desconhecida. Não mover esses filtros para dentro da subconsulta: isso poderia
  ressuscitar vínculos antigos ou transformar cobertura truncada em aparente
  certeza. A consulta e a explicação permanecem compatíveis, sem editar HarpIA.

Ambiguidade resolvida explicitamente: o Store antigo aceitava negativos e zero
como efeitos do slice Python e até booleans; não havia validação própria. A nova
validação rejeita limit <=0, offset <0, bool, não inteiros e valores fora de bigint
antes de abrir conexão. Limites positivos acima de 200 continuam aceitos pelo
Store (inclusive 1001); a API conserva sua validação independente. Não há um novo
teto arbitrário para chamadas internas. Dependentes de slices inválidos precisam
ser corrigidos; nenhum foi identificado nas chamadas inspecionadas.

## Validação PostgreSQL

`TEST_RESULTS.json` contém a validação atual em **PostgreSQL 18.6**, métricas,
versão exata, hashes do código testado, casos executados, índices e EXPLAIN ANALYZE
BUFFERS das duas consultas reais (capturadas dos métodos, sem SQL de teste
divergente). `TEST_RESULTS_PG16.json` preserva o resultado anterior, do commit
45603a9, em PostgreSQL 16.15; não confundir as duas medições.
`ENVIRONMENT_PG18.json` registra data, imagens e isolamento do contêiner/rede
inspecionados nesta rodada; os recursos sintéticos foram removidos ao concluir.

Instância: contêiner local `p11-pagination-tests`, banco `p11_pagination_test`,
PostgreSQL **18.6 (Debian 18.6-1.pgdg13+2)**, `server_version_num=180006`, rede
interna exclusiva, sem porta publicada e com dados em tmpfs descartável. Nenhum
acesso à VM ou banco operacional foi necessário nesta rodada. Timezone da sessão
`America/Sao_Paulo`, encoding UTF8, locale `en_US.utf8`, `work_mem=4 MiB`,
`shared_buffers=128 MiB`. A suíte recusa outra versão antes de criar tabelas.
Python 3.12.15, psycopg 3.2.1 e FastAPI 0.115.0 da imagem local
`harpisense-backend:integration`. Nenhum teste usa SQLite como Store; o import
sqlite3 da API aprovada não instancia Store SQLite. Fixtures, dados e cenários da
suíte anterior foram reutilizados; nenhum índice ou código operacional mudou.

Imagens utilizadas, identificadores imutáveis:

- PostgreSQL `postgres:18.6`, digest
  `sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6`.
- Cliente `harpisense-backend:integration`, ID
  `sha256:be075ad0fc7764f9367712b7d8ef50ad63828c4cdf4a43c74a86cf6ff06dfa1b`.

Seis testes passaram, zero erros/falhas:

- vazio, tipos desconhecidos, limites inválidos e sentinela 1001;
- múltiplas revisões/tipos, timestamp regressivo, empates e IDs Unicode;
- filtros de tipo, várias páginas, offset além do fim e histórico preservado;
- ordem em UTC, São Paulo, Nova York e Kathmandu, incluindo DST e microsegundos;
- inserção, idempotência e conflito imutável preservados;
- API autenticada, validação HTTP, explicação com vínculo antigo que deixa de
  existir na última revisão, execução e cobertura truncada;
- volume: 60.000 revisões, 20.000 IDs, payload sintético com 2 KiB, página 50,
  offset 100, comparação integral dos resultados por SHA256.

| Métrica no cliente | Anterior | Nova |
|---|---:|---:|
| Linhas retornadas pelo SQL/materializadas pelo driver | 20.000 | 50 |
| Linhas retornadas por list() ao chamador | 50 | 50 |
| Pico de alocações Python, bytes (tracemalloc, amostra separada) | 59.017.409 | 137.797 |
| RSS antes de list(), bytes (mediana) | 57.835.520 | 57.581.568 |
| RSS depois de list(), bytes (mediana) | 140.750.848 | 59.285.504 |
| Pico RSS do processo, bytes (mediana) | 165.302.272 | 59.285.504 |
| execute(), segundos (mediana) | 0,281053 | 0,089759 |
| fetchall()/decodificação, segundos (mediana) | 0,240699 | 0,000440 |
| list() completa, segundos (mediana) | 0,591067 | 0,096878 |

Resultados idênticos. Redução de 400 vezes nas linhas materializadas no cliente.
No volume, ambas as variantes e as seis medições em processos novos produziram
SHA256 `b8f4efebb62bd6c37adaa9da90cf4043d0abafb94fcc46f937f6f78f5d9d0ec1`.
Esse hash difere do ensaio 16.15 porque agora a sessão usa o timezone da VM;
a equivalência é comparada entre as duas implementações na mesma sessão/fuso.

Método: três processos Linux novos por variante, ordem alternada (anterior/nova,
nova/anterior, anterior/nova), sem tracemalloc nas amostras de tempo/RSS. Cada
processo importa as mesmas dependências, mede `/proc/self/status` (VmRSS e VmHWM)
antes/depois e executa uma chamada. VmHWM é o pico do espaço de endereçamento do
processo, incluindo imports/conexão/libpq/objetos Python; não é só heap Python.
Não se usa ru_maxrss, que pode carregar o pico do processo pai através de
fork/exec. O pico com tracemalloc é outra medição, somente de alocações rastreadas
pelo Python, e seus tempos instrumentados não entram nas medianas acima.

`execute()` mede a chamada síncrona no driver: inclui espera no servidor e
transferência/buffering libpq, sem isolar tempo de rede. `fetchall()` mede
conversão/decodificação em Python. `list()` inclui conexão, ambas as etapas,
conversão dos registros e, no código anterior, ordenação e slice. Nenhum desses
tempos deve ser tratado como tempo puro de execução no PostgreSQL.

| Trabalho no PostgreSQL, EXPLAIN ANALYZE representativo | Anterior | Nova |
|---|---:|---:|
| Index Scan, linhas efetivas x loops | 60.000 x 1 | 60.000 x 1 |
| Unique, últimas revisões emitidas | 20.000 | 20.000 |
| Ordenação global no servidor | ausente | top-N heapsort, 95 KiB |
| Saída da ordenação global para OFFSET/LIMIT | — | 150 |
| Linhas na saída raiz | 20.000 | 50 |
| Shared hit blocks, nó raiz | 60.580 | 60.583 |
| Shared read blocks / temp read-write blocks | 0 / 0 | 0 / 0 |
| Planning Time, ms | 0,377 | 0,589 |
| Execution Time, ms | 80,347 | 97,134 |

O plano novo **continua percorrendo 60.000 revisões**, seleciona 20.000 últimas
e alimenta a ordenação global com essas 20.000 linhas; 150 são emitidas para
consumir offset 100 e devolver 50. As duas variantes usam a PK e incremental
sort de revisão. A execução no servidor ficou mais cara nesta amostra por fazer
a ordenação final; não se alega redução do trabalho no servidor. O ganho total
está na transferência, materialização/decodificação e trabalho evitado no Python.

Os planos foram capturados após os testes de volume, com cache aquecido, sem
limpeza de caches do host. Shared hit blocks são contagens de acessos, não blocos
distintos; não somar pais e filhos. Shared read zero não significa que o banco
leu somente 50 linhas ou que haverá zero I/O na operação. EXPLAIN ANALYZE não
mede o envio/decodificação do resultado normal no cliente. Todos os tempos são
amostras locais, sem garantia de latência na VM.

## Índices e limitações

Nenhuma migração ou índice novo é necessário nesta entrega. O plano usa a PK
existente com filtro de tipo e incremental sort de revisão. Um índice
`(kind,id,revision DESC)` poderia remover esse sort, mas duplicaria grande parte
da PK e não eliminaria a leitura de todas as revisões nem a ordenação global.
Não há evidência de necessidade no ensaio; não é proposto para aplicação.
Não aplicar a migração candidata V2 para `hs11_projections`: ela não corresponde
às tabelas ativas `projections`/`audit` e não faz parte desta correção.

Offset alto e muitas revisões ainda custam trabalho no servidor. Não há cursor,
snapshot compartilhado entre páginas ou garantia contra deslocamento entre
requisições concorrentes; essas características já existiam. history continua
sem limite por contrato. A ordenação local herdada pode diferir de ordem temporal
absoluta durante DST. Datas fora do intervalo representável por datetime Python
já não eram suportadas. A validação agora usa a mesma versão de engine 18.6 da
VM, porém em Debian/Docker, não Ubuntu no HarpiServer; hardware, concorrência,
volume/distribuição reais e locale da operação não foram reproduzidos integralmente.
O ensaio em tmpfs/cache quente não é um benchmark de disco. Fixtures congeladas
permitem comparar o comportamento aprovado sem editar módulos de outros chats.

## Reprodução isolada

Na raiz desta pasta, PowerShell com Docker iniciado. Os nomes abaixo são
exclusivos de teste; usar um contêiner novo em cada execução (o teste cria tabelas).
Não substituir o DSN fixo por uma URL operacional.

```powershell
docker pull postgres:18.6
docker network create --internal --label purpose=p11-pagination-synthetic-tests p11-pagination-tests
docker run -d --name p11-pagination-tests --network p11-pagination-tests --label purpose=p11-pagination-synthetic-tests --tmpfs /var/lib/postgresql:rw -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=p11_test -e POSTGRES_DB=p11_pagination_test postgres:18.6 -c timezone=America/Sao_Paulo
docker exec p11-pagination-tests pg_isready -U p11_test -d p11_pagination_test
$testSource = (Get-Location).Path
docker run --rm --network p11-pagination-tests --mount "type=bind,source=$testSource,target=/work" --workdir /work --entrypoint python harpisense-backend:integration tests/verify_postgres.py
docker rm -f -v p11-pagination-tests
docker network rm p11-pagination-tests
```

A autenticação trust é exclusiva da rede descartável sem publicação de porta.
A imagem Python precisa das dependências em `requirements-test.txt`; a imagem
local citada já as contém. O relatório atual é sobrescrito a cada execução; o
arquivo PG16 é histórico. Para reprodução da imagem exata, substituir a tag pelo
digest acima. A instrumentação RSS requer Linux com `/proc` (fornecido pelo
contêiner cliente). Aguardar pg_isready confirmar aceitação antes de iniciar.
Os nomes são exclusivos desta validação: se já existirem, conferir finalidade e
isolamento antes de reutilizar/remover. Remover somente recursos sintéticos da
rodada; nunca os contêineres locais `harpisense-postgres`/`harpisense-postgres-test`.

## Roteiro de implantação e recuperação (não executado)

1. Revisar esta branch e as evidências 18.6 (6 testes aprovados), comparando o hash
   do arquivo candidato com `code_sha256` no relatório. A qualificação de versão
   isolada foi concluída; ela não autoriza implantação. Em rodada explicitamente
   autorizada, confirmar novamente hashes do código ativo, API injetada, esquema,
   índices e timezone. Preservar P08/P09 em andamento e verificar eventual mudança
   de dependentes desde a inspeção original; a VM não foi consultada nesta rodada.
   Se a base ativa divergir, comparar e reconciliar antes de substituir qualquer
   arquivo. Não enviar fixtures, relatório ou configurações ao diretório ativo.
2. Em janela autorizada, registrar hash e cópia de recuperação somente do arquivo
   `postgres_store.py` ativo. Preservar propriedade/permissões. Copiar o novo
   arquivo para temporário no mesmo filesystem, conferir hash e sintaxe usando o
   Python do serviço, e substituir atomicamente. Não alterar env, schema, audit,
   consumidores MQTT ou outros módulos. Nenhuma migração é necessária.
3. Reiniciar somente o backend P11 pelo procedimento operacional autorizado.
   Validar autenticação, listagem/paginação, history e explicação por requisições
   de leitura; comparar formas/revisões, empates, limites HTTP e a sentinela 1001
   da HarpIA. Observar erros, latência e RSS. Validar com o timezone efetivo do
   serviço; as medianas locais acima não são limiares de aceitação operacional.
   Não inserir dados sintéticos na operação. Não habilitar geração BitNet.
4. Se houver regressão, restaurar atomicamente o arquivo salvo, conferir o hash
   original acima, reiniciar somente P11 e repetir as verificações de leitura.
   Como não há DDL nem mudança de dados, a recuperação não exige rollback de
   banco. Guardar evidências da falha sem incluir segredos.

Nenhum deploy, restart, merge na main, escrita operacional, alteração em P08/P09,
Risk/Policy/executor, frontend ou geração BitNet foi realizado nesta rodada.
