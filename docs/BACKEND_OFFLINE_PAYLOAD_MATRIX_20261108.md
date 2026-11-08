# Payload backend: inventário e bloqueios offline

Esta é uma matriz de implementação e evidência, não homologação de um instalador
completo. Native-installers a8fef1f, candidata 3 e prévias 5174/5175 não foram
alterados por esta entrega. Nenhum EXE/.run novo foi gerado nem publicado.

## Matriz por função e plataforma

| Função / entrada interna | Windows | Ubuntu | Operação/UI/persistência comprovada nesta entrega |
| --- | --- | --- | --- |
| API e PostgreSQL: HarpiSenseApi / HarpiSensePostgres; entry api | composição nativa e SQL integrados; novo pacote pendente | composição e SQL integrados; instalação ainda usa apt/rede | HTTP/PG nativos de desenvolvimento; não prova serviços instalados/autostart |
| Admin, TOTP, recuperação e primeiro acesso: admin_auth.candidate | 071d052 e migração admin_auth/004 incluídos no provisionamento | mesma fonte; execução instalada não testada | 11 testes nativos, E2E browser real reportado pelo Codex, estado completed geração 2 consultado diretamente no PG |
| Persistência após reinício API | processos A/B reais, mesmo cluster do E2E | não executado | ack/geração/MFA/verificadores/setup iguais; original18082 preservado; não é reboot nem reinício do serviço instalado |
| Ficha/XAI/avaliação: incident_dossier, xai_api | fonte e migrations delivery/003/004 integradas | mesma fonte; execução instalada não testada | 6 testes HTTP/PG; somente referências ligadas; dados de modelos são fixtures artificiais; BitNet desligado |
| Atividade/casos/aplicar: ActivityProducer + LinkedOperationalQueue | v2 publicado5608399+fb0f8e9, 12 testes nativos | fonte portátil; execução instalada não testada | casos distintos por ID explícito, stale/UNKNOWN preservados, sem origem sintética na autoridade; cobertura real completa ainda ausente |
| Risk/Policy/aprovação/resultado | engines e hook de aprovação10acba5 integrados | mesma fonte; não instalado | fixtures e ensaios PG do responsável; bridge HTTP completo ainda precisa de aceite integrado próprio; executor real indisponível |
| RF/IF + transformações + referências | código e coleta científica preparados, modelos aprovados não identificados | fonte/copiar pacotes preparados, wheels/artefatos finais não validados | só estimadores reais treinados em amostras sintéticas de desenvolvimento; não substituir por modelos aprovados |
| SHAP TreeExplainer / PermutationExplainer | 7 testes reais; biblioteca0.50.0; coleta PyInstaller preparada | requirements e cópia preparados; wheels Linux não homologados | Tree RF pré-calibração; Permutation RF calibrado/IF operacional; Tree IF incompatível recusado; histórico SHAPLEY_PERMUTATION preservado |
| HarpIA BitNet local | pesos e llama-cli/server encontrados em outra worktree e hash do peso conferido; não estão no payload nativo | binário Linux não encontrado no escopo inventariado | geração real pelo produto não exercitada; API existente ainda declara deterministic_only, sem rotular fallback como BitNet |
| MQTT: HarpiSenseBroker / HarpiSenseMqtt; entry consumer | serviço/binários previstos no builder existente | Mosquitto instalado via apt quando local_managed | ownership IoT; nenhum CONNACK/SUBACK ou heartbeat atesta ausência de casos ou captura completa |
| Captura/preparação → inferência | ponte P08 continua bloqueada sem certificação das contagens/features | mesma limitação | serviço disponível não equivale a inferência operacional nem a autorização de contenção |
| Setup/ativos genéricos/aplicadores | ownership Configurações; base presentation_only/firmware+MQTT | ownership Configurações, sem extrapolar | first_access independente de setup; PG do E2E tem setup versão0/not_started; não prova retomada de draft salvo nem ativos genéricos |

## Arquivos, hashes e redistribuição

Manifesto gerado por `packaging/native/inventory_backend_payload.py`:
`docs/evidence/backend-integration-20261107/payload-inventory.json`.
Ele inclui caminhos, tamanhos e SHA256 dos modelos de teste encontrados,
metadados com ordem de features/versões/perfil/janela, arquivos fonte/locks,
pesos BitNet e executáveis locais. Não carrega pickle/joblib não aprovado.

RF/IF operacional aprovado: **zero identificado** no inventário. Os modelos
em detection-composition/local-evidence são marcados development_synthetic_test_only,
approved_for_operational_use:false e não foram copiados para o produto.
Referências/transformações aprovadas também precisam de manifesto de aprovação.
A pergunta por caminho/commit dos aprovados foi encaminhada ao usuário.

BitNet: `genai/artifacts.lock.json` fixa runtime0b341e5, submódulo llama.cpp390c307,
patch local e modelo a1f2f1c, arquivo ggml-model-i2_s.gguf de1.187.801.280 bytes.
SHA256 do peso local conferiu com
4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162.
Licença declarada no lock: MIT; notices locais encontrados são inventariados.
Portabilidade/DLLs do binário Windows e runtime Ubuntu continuam pendentes.
Nenhum caminho da máquina de desenvolvimento pode ser dependência do instalado.

Dependências científicas diretas: scikit-learn1.8.0, numpy2.3.5, pandas2.2.3,
joblib1.5.3, scipy1.17.0, shap0.50.0. Transitivas incluem numba/llvmlite/slicer;
versões no requirements-scientific.lock. O lock comum não substitui wheelhouse,
hashes/licenças e validação dos binários por SO/Python. O teste de desenvolvimento
usou a venv científica e dependências da venv nativa existente; não é payload final.

Bloqueio concreto Ubuntu offline: ubuntu_install.py ainda chama apt-get update
e apt-get install para PostgreSQL/Python/Mosquitto. O pip já usa --no-index com
wheels, mas isso não elimina a dependência de pacotes de sistema/rede. É necessário
embutir e validar o conjunto .deb/dependências ou runtime nativo equivalente;
não declarar esse .run autocontido sem esse trabalho e aceite limpo offline.

## Docker/Compose e equivalente nativo

| Arquivo do domínio | Função | Equivalente nativo / situação |
| --- | --- | --- |
| backend/docker-compose.yml | PostgreSQL de desenvolvimento | PostgreSQL nativo provisionado e controlado pelo instalador; não levar volume/credencial de desenvolvimento |
| backend/delivery/compose.local.yml + Dockerfile | API + PG local | entry api, HarpiSenseApi/harpisense-api e PostgreSQL; não exige Docker para operação testada |
| backend/detection_composition/compose.test.yml + Dockerfile | testes RF/IF/composição e banco descartável | excluir somente harness de teste; a inferência de produto ainda precisa de modelos aprovados, fontes e serviço/worker integrados |
| backend/admin_auth_tests/http-browser.compose.yml e Dockerfile.mfa/http | harness de auth/browser | excluir testes; auth real já funciona no runtime nativo de desenvolvimento |
| backend/xai_api/tests/Dockerfile | harness HTTP/PG de leitura XAI | excluir testes; leitor é carregado pela API nativa |
| mqtt/docker-compose.yml | broker MQTT de desenvolvimento | Mosquitto local gerido pelo instalador; implantação offline Ubuntu ainda depende do pacote de sistema |

BitNet não possui container obrigatório neste escopo: usa subprocesso local
llama-server gerido por harpia.runtime. Isso não significa que já esteja integrado
ao instalado. Não usar serviço de nuvem nem exibir determinístico como geração real.

## Gate de release

Faltam modelos/referências aprovados, wheelhouses/binários/notices completos por
SO, BitNet local incluído/geração real/UI, produtores operacionais certificados,
aplicadores/executor/verificação reais e pacote novo. Depois, aceitar SEPARADAMENTE
Windows e Ubuntu limpos com internet desconectada e LAN preservada, antes/depois
reboot, painel/login/MFA/PG/MQTT/autostart e registros consultáveis na interface.
Os componentes disponíveis não liberam defesa: gates e política M1/M2/M3 continuam.
Prévia visual e E2E de desenvolvimento não satisfazem esse gate.
