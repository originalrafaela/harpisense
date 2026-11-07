# XAI — composição, pacote e aceite

Entrega na branch `feat/reusable-software`, após `c44bd6f`. Contrato final da
candidata em [XAI_CONTRATO_FRONTEND.md](XAI_CONTRATO_FRONTEND.md). Aprovação do
Arquiteto pendente: Maestri list/debug confirmaram pipe indisponível. O worktree
native-installers está em outra frente e não foi alterado por esta entrega.

## Núcleo e saídas confirmados

`backend/domain/harpisense_xai/core.py` é idêntico entre `7fe8294` e esta candidata.
Git blob em ambos: `bb5a8c6a9e640455c9a6d6342c12bc7aebfc921a`.
Nenhum segundo explicador foi introduzido. O núcleo existente usa
SHAPLEY_PERMUTATION, versão harpisense.xai.permutation.v1, chamando a função real
predict_proba do CalibratedClassifierCV ou -score_samples do IsolationForest.

RF explica a classe explicitada, após calibração sigmoid em sessões separadas.
O teste confirmou saída diferente da árvore bruta. IF explica o mesmo score da
detecção, com inversão de score_samples. O Risk converte RF para fator percentual
e IF para percentil condicionado ao limiar; os limites são explícitos no contrato.
Risk/Policy e seus gates não foram modificados.

## Persistência e integração

Leitor `backend/xai_api`: reutiliza projections(kind=xai), o registro explanation
canônico, validadores de vínculos e sessão existente. Sem migração nova de dados
para XAI. Nomes vêm do cadastro de instalação ou asset de identificador exato.
Sem resolução por último dispositivo. Consultas usam snapshot READ ONLY.

Produtor `detection_composition.Composition` aceita referências XAI opcionais,
validadas pelo núcleo. Com referência, gera a explicação durante processamento
explícito, vincula o incidente e persiste xai na mesma transação dos demais
registros. Sem referência, nenhuma explicação é fabricada. Referências e parâmetros
entram no fingerprint de idempotência; não existe backfill silencioso ao consultar.
CLI oferece --rf-reference/--if-reference. Mantida a restrição da composição
sintética a detection_composition_test; caminho P08 operacional continua bloqueado.

Factory candidata build_candidate_app instala o leitor após autenticação. Para
o runtime nativo, o ponto único entregue é:

```python
# native_server.runtime.build_native_app, após os mounts e antes de return app:
from xai_api.native import install_on_native
install_on_native(app, state)
```

Ele usa o /p11-api existente e o cadastro nativo device_id. Não executa migração,
inferência, leitura de modelo, consumidor MQTT ou chamada de executor.

## Inclusão no instalador para o Arquiteto

1. Incluir backend/xai_api na cópia de pacotes do build Ubuntu e no collect-all
   do PyInstaller Windows. Acrescentar xai_api/native ao runtime_check, verificando
   importações dentro do pacote, sem PYTHONPATH de checkout. Acrescentar o hook
   acima ao runtime. Não aplicar automaticamente alterações da outra worktree.
2. Para **somente consultar** XAI, bastam Python >=3.12 e as dependências já
   instaladas de FastAPI, psycopg, jsonschema, admin_auth e contratos. Não requer
   shap, sklearn, modelos ou backgrounds no processo HTTP.
3. Para **produzir** explicações, incluir o núcleo original harpisense_xai,
   harpisense_data, harpisense_rf, harpisense_if e detection_composition, além
   dos contratos/engines e versões científicas em detection_composition/requirements.txt:
   scikit-learn 1.8.0, numpy 2.3.5, pandas 2.2.3, joblib 1.5.3, scipy 1.17.0.
   Python e todas as versões devem coincidir com metadata.versions do treinamento.
4. Provisionar artefatos confiáveis fora do checkout: RF model.joblib e metadata.json
   com CalibratedClassifierCV, classes ordenadas, features/dtype/perfil/janela,
   versão, hashes e background de treino; IF model.joblib e metadata com threshold,
   calibration_scores ordenados, features/perfil/janela, versão e hashes. Fixar
   SHA-256 aprovado no manifesto antes de carregar joblib.
5. Provisionar referências JSON por modelo: reference_id bg-<fingerprint>, detector,
   model_version, features, feature_schema_version, traffic_profile, window_seconds,
   seed, provenance e rows. RF pode usar background de treino embutido. IF exige
   treino normal cujo CSV corresponda ao dataset_sha256.train antes de criar a
   referência. Background XAI e distribuição de calibração IF são objetos distintos.
6. Artefatos exercitados aqui são **sintéticos de teste**, identificados no
   model-fixture-manifest.json; não são modelos aprovados para instalação produtiva.
   Não há modelo operacional aprovado novo nesta entrega. Não habilitar inferência,
   defesa ou cobertura P08 pela mera inclusão do leitor.

Wheel offline reproduzível do leitor:

```
python backend/xai_api/build_wheel.py <diretorio-de-saida>
```

Artefato ensaiado: harpisense_xai_reader-1.0.0-py3-none-any.whl.
SHA-256: `9d13872822a8e04572807ea1e53ea229f8e16e747618838cf10a762c127397b2`.
Não contém inferência nem segredos. A dependência declarada de build setuptools
no pyproject é dispensada pelo builder offline em biblioteca padrão.

## Aceite de desenvolvimento

Oito testes passaram, zero falhas, em HTTP TCP real + PostgreSQL 16.15:
RF calibrado versus árvore bruta, IF versus -score_samples, coerência com resíduo,
complemento P(normal), transformação e limites do Risk, dois incidentes/janelas
do mesmo ativo, ausência sem impedir consulta ao incidente, vínculo adulterado,
recusa sem sessão/Basic técnico, schemas OpenAPI, GET sem escrita e rollback total
se a inserção XAI falhar. Modelos foram treinados de verdade sobre dados explicitamente
artificiais; isso não valida acurácia, causalidade ou desempenho em laboratório.

Reprodução: imagem de teste xai_api/tests/Dockerfile reutiliza imagens científicas
e de autenticação já fixadas; DATABASE_URL deve apontar exclusivamente para
detection_composition_test. Executar unittest discover em backend/xai_api/tests;
XAI_EVIDENCE_DIR opcional exporta exemplos e fixture sem credenciais.

## Aceite no runtime instalado

VM identificada harpisense-ubuntu-reteste, Ubuntu, Python da venv instalada em
/opt/harpisense/venv; PostgreSQL instalado 16.15. Instalação do wheel em
/opt/harpisense-xai-trial/site-packages, hook sobre o native_server.runtime
efetivamente instalado, sem caminhos do checkout. Binários PostgreSQL instalados
iniciaram **cluster de ensaio próprio**, sem alterar o cluster do produto.

Passaram sete verificações registradas em installed-runtime.json: 401 sem sessão,
mount e sessão reais, RF/IF persistidos, aditividade com resíduo, nome via asset,
ausência explícita e importações fora do checkout. O processo de ensaio foi
reiniciado e conservou os registros. Hash do runtime nativo encontrado:
`c610b33fecbb56500716f79b1ba54ee6dd408a5bcd40cfc1dfeb5f0f0e6a9675`.
Esse runtime não possui build_info.json; não foi presumido commit de origem.

**Não equivale a aceite de um novo instalador completo.** As contribuições foram
produzidas em desenvolvimento com os modelos reais; o runtime instalado verificou
leitura persistida, coerência, autenticação e compatibilidade do hook. Ele não
possuía numpy/sklearn ou modelos de inferência. Não foram reconstruídos nem
publicados instaladores Windows/Ubuntu nesta frente. Integração e ensaio de uma
nova distribuição completa permanecem com o Arquiteto/empacotamento.

O serviço principal harpisense-api permaneceu ativo. Nenhum broker, firewall,
interface de rede, consumidor MQTT ou contenção foi alterado. Porta 18089 e
cluster 15439 são exclusivos de ensaio, acessíveis pelo loopback; o Frontend
recebe o túnel local descrito no contrato, não uma exposição operacional.
