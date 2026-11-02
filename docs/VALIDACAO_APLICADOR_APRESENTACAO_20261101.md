# Aplicador real de apresentação — entrega local

Partida real conferida: feat/frontend-backend-autonomia limpa em
bcba816c8d4e73728c2888304f218d680f4440ea. Main, worktrees e entregas de outros
agentes preservadas. Referências: Versao_v2 (referencias/versão_v2) e pacotes
anteriores em Versões corretas onde ainda não substituídos. O pacote legado
Adaptadores_Aplicacao_v1 foi consultado: é de contenção/Defense Executor e não
foi confundido com apresentação; suas ações/SQLite não foram ativadas ou copiadas.
Contratos e ConfigStore aprovados continuam a base; não há migração SQL nova.

## Implementado

- Consumidor materializado de nome/fuso no diretório persistente fornecido pelo
  instalador; não basta atualizar a proposta no banco. Backend realmente carrega
  os parâmetros e formata instantes; frontend adota somente consumo verificado.
- Aplicação com sessão administrativa, senha atual reautenticada pelo módulo
  existente, idempotência por operação/revisão, lock/fencing e recibo interno.
- Journal antes dos efeitos, restauração do snapshot anterior, read-back e auditoria.
  Falha de recuperação fica desconhecida/bloqueada, sem sucesso fictício.
- Interface mostra desejado, efetivo, consumo atual e resultado. Nome aparece no
  cabeçalho; horários de atualização, auditoria, controles, HarpIA e telemetria usam
  o fuso de apresentação. Payloads originais continuam acessíveis sem conversão.
- Operational=false não muda. Não há mudança de OS timezone, timestamps originais,
  MQTT, configuração do PostgreSQL, rede, firewall, firmware ou autonomia.

Contrato, endpoints, composição e recuperação completos em
backend/config_manager/PRESENTATION.md. Nenhuma rota aceita recibo do navegador,
comando ou seleção de caminho. Sem diretório explícito, candidata antiga continua
sem aplicador. Não houve instalação na VM.

## Navegador com HTTP real

Execução: noite local de 01/11/2026, UTC 02/11 aproximadamente 00:56–01:11.
Portal Maestri HarpiSense Aplicador Local, frontend compilado em loopback 4175,
proxy restrito /p11-api → backend Uvicorn loopback 18002. PostgreSQL 18.6 exclusivo
harpisense-presentation-20261101, config_fixture, loopback 55445. A fixture anterior
e seu portal foram preservados. Porta dev 5174 não estava disponível para nova
instância; adotado preview isolado, sem encerrar processo não identificado.

Capabilities explícitas: presentation-test-only-1, conjuntos operacionais vazios.
Não representam capacidades da VM. Conta administrativa exclusiva da fixture,
bootstrap/autenticação existentes; senha somente no formulário/variável da fixture,
nunca nos artefatos de evidência. Sem TestClient ou resposta HTTP mockada nos
ensaios da tabela. Chamadas auxiliares usaram fetch nativo no mesmo portal.

| Ensaio | Resultado confirmado |
| --- | --- |
| Proposta/validação no assistente | revisão 1; nome HarpiSense Apresentacao Local e America/Sao_Paulo |
| Autorizar e aplicar pelo formulário | APPLIED; consumidor e cabeçalho mudaram; APPLYING → VERIFIED → APPLIED no SQL |
| Instante e fuso | original 2026-11-01T12:00:00Z permaneceu; exibido 09:00:00 GMT-3 |
| Repetir com senha atual | idempotent=true; sem novos efeitos ou eventos de aplicação |
| Reiniciar backend e reautenticar na página | nome/fuso/revisão 1 persistiram no novo processo |
| Proposta concorrente por segunda sessão do portal | revisão 2 validada; tentativa do formulário ainda na revisão 1 recebeu 409 |
| Falha após escrever alvo da revisão 2 | FAILED/rolled_back; consumidor voltou à revisão 1, nome/fuso anteriores, verificado=true |
| Falha de aplicação e de rollback na revisão 3 | RECOVERY_REQUIRED; target não confirmado, verified=false, estado unknown, aplicação bloqueada |
| Corrigir causa de teste e reiniciar | restaurou/verificou snapshot da revisão 1; revisão 3 FAILED, rollback auditado, sem reexecutar alvo |
| Sem sessão / sem senha / senha incorreta | HTTP 401 / 422 / 403, sem efeito |
| Nova proposta limitada após recuperação | revisão 4 APPLIED; HarpiSense Apresentacao Confirmada, Asia/Tokyo; original 12Z exibido 21:00:00 GMT+9 |
| Reiniciar novamente e retry da revisão 4 | consumidor verificado persistiu; estado/revisões/auditoria/recibos/artefatos e instantes originais idênticos |
| Logout final | formulário presente; presentation e P11 health sem sessão retornaram 401 |

Revisões 2–4 foram preparadas/validadas por uma sessão auxiliar via fetch real
no portal; aplicação foi acionada pelos botões e senha do formulário principal.
As falhas foram exceções controladas no backend da fixture, **depois de escrita
real**, sem substituir HTTP, filesystem, consumidor ou SQL. O arquivo local
test-fault.json é lido apenas por presentation_fixture.py; não há parâmetro ou
endpoint de injeção em produção. Ele terminou com stages vazio.

Durante o ensaio, a UI foi ajustada para distinguir resposta antiga desta aba
do estado atual recuperado e para não apresentar horário como confirmado quando
o consumo é unknown. Os primeiros snapshots preservam a UI observada antes desse
ajuste; browser-final-restarted.json registra a composição final compilada.

## Evidências e banco

docs/evidence/presentation-20261101 contém:

- browser-success/idempotent/after-restart: primeira aplicação, retry e persistência.
- browser-revision-conflict/rollback/unknown/reconciled: recusas e recuperação real.
- browser-unauthorized/reauth-rejected/logout: autorização, erro de senha no cliente
  sem descartar a sessão válida e recusa após logout.
- browser-final-success/final-restarted: revisão 4 e fuso Asia/Tokyo na composição final.
- http-receipt.jsonl: métodos, caminhos, status e UTC coletados pelo middleware de
  teste, sem bodies/cabeçalhos/segredos. HTTP 200 em FAILED não é contado como sucesso.
- postgresql-unknown.json: revisão 3 RECOVERY_REQUIRED e effective_revision=1;
  journal pendente/artefato incerto preservados para análise.
- postgresql-final.json: desired/effective=4, operações 1 APPLIED / 2 FAILED /
  3 FAILED / 4 APPLIED, recibos das aplicações verificadas e códigos de rollback.
- restart-comparison.json: comparação com postgresql-before-final-restart.json,
  oito grupos inalterados após reinício e retry, incluindo created_at originais,
  auditoria/recibos, timezone da sessão PostgreSQL e ambos os arquivos de runtime.

Recibos SQL são SELECT em transação READ ONLY, filtrados pela instalação da
fixture; reautenticações da conta incluem também os testes automatizados nesse
banco. Não atribuir cada evento de autenticação a um clique; os eventos da
configuração estão vinculados à operação/instalação e cruzados com HTTP.
Não foram exportados token_hash, password_hash, Authorization ou senhas.

## Testes automatizados, separados do ensaio visual

- 45 testes config_manager aprovados, zero pulos, com PostgreSQL real; incluem
  regressões sem/com aplicador, reautenticação, concorrência, fence antigo,
  corrupção do journal, processo interrompido, drift e recuperação não confirmada.
- Após ajuste de pendências preparatórias com aplicador instalado, 8 provas HTTP
  pertinentes reexecutadas e aprovadas; não são contadas como casos novos.
- 18 regressões delivery aprovadas, zero pulos, incluindo P11/PostgreSQL, controles
  e HarpIA. Modos desses testes são sintéticos e não execução operacional.
- 39 testes frontend aprovados; TypeScript/build aprovados. Incluem conversão de
  instante preservado e proxy real com allowlist de presentation/apply.

Total: 102 execuções de casos das três suítes principais, além do ensaio no portal.
As provas TestClient/mocks unitários são complementares; não substituem a tabela
de HTTP real. O consumidor MQTT não recebeu alterações; P11 e HarpIA foram
observados por HTTP com generation_enabled=false e executor não configurado.

## Reprodução e estado ao fechar

Usar backend/config_manager_tests/presentation_fixture.py --prepare explicitamente
contra banco descartável config_fixture no loopback 55445; o guard recusa outro
host/porta/nome. DATABASE_URL e senha inicial ficam em variáveis locais. Definir
HARPISENSE_PRESENTATION_TEST_DIRECTORY para diretório privado persistente da fixture,
PYTHONPATH=backend;backend/domain;genai e as credenciais técnicas de fixture do
bootstrap. Executar o mesmo script sem --prepare para servir em 18002.

Em frontend/: npm run build; HARPI_API_TUNNEL_TARGET=http://127.0.0.1:18002;
npm run preview -- --port 4175. Origem permitida exata é http://127.0.0.1:4175,
sem CORS aberto. Entrar no portal com a conta provisionada da fixture e repetir
a tabela. Novos dados produzem outros UUIDs/revisões.

Regressões: HARPISENSE_CONFIG_TEST_DSN aponta à fixture; unittest discover
-s backend/config_manager_tests -v. Delivery usa TEST_DATABASE_URL para fixture
e discover -s backend/delivery_tests -p test_delivery.py -v. Nunca executar essas
suítes em banco operacional. Frontend: npm test e npm run build.

Ao finalizar, backend PID 25960 (sessão exec 75246), preview sessão 92210 e
container dedicados ficaram disponíveis para inspeção; portal no login após
logout. Não se garante sobrevivência dos processos após fechar o aplicativo.
Antes de nova execução, conferir listeners. Não reutilizar a fixture para operação.

## Limites e próxima etapa

O aplicador de apresentação foi validado localmente, incluindo falha e recuperação.
Isso não valida MQTT, coleta física, TLS/ACL, captura, detecção, defesa ou backup.
ESP32-WROOM-32/LDR/LED continua sem gravação/ativação; nenhum perfil novo de firmware
foi declarado implementado. Não houve SSH, configuração de broker/rede/firewall/VM
nem alteração de timezone do OS. operational=false permanece.

Próxima etapa objetiva: preparar comparação do bootstrap instalado com esta
candidata e ensaio de backup/restauração conjunta do registry e diretório de
apresentação, com proprietário/permissões definidos. Só então propor implantação
controlada desse escopo. Outro aplicador exige contrato próprio, verificador e
rollback; esta entrega não autoriza habilitar grupos adicionais.
