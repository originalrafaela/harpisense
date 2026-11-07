# Consolidação funcional — candidata 5

**Integração aprovada nos testes descritos; produto completo e sistemas limpos
ainda não homologados.** Não transferir aceite da candidata 3 para esta versão.

Origem funcional `e103510`; build `8b9c9efe9eb5cd01b0be6812777da7ed08f0df4a`.
Metadados em [runtime-build-info.json](runtime-build-info.json).
Código da aceitação: `packaging/native/acceptance_product.py`.

[Relatório final](product-native-result.json): **68 verificações aprovadas**
usando o runtime Windows congelado, Chromium, API HTTP, PostgreSQL e Mosquitto
nativos reais. Processos exclusivos em 25432/28080/28883, cluster/dados privados
em `.native-test/<uuid>`; não registrados serviços no host, não usados bancos
operacionais nem fixtures de login. Credenciais e material MFA gerados pelo
próprio produto; segredos não constam nos relatórios ou capturas.

Cobertura: bootstrap/conta, TOTP inválido/válido, login após reinício; códigos
de senha distintos dos de MFA, consumo único, propósitos não intercambiáveis,
revogação de sessão no reset sem alterar TOTP; MFA perdido exige nova confirmação;
regeneração de códigos exige senha+TOTP. Cadastro e leitura real de ativo,
revisão concorrente recusada, persistência após reinício de API/consumidor/banco.
Apresentação nome/fuso proposta, validada, aplicada com reautenticação, consumida
e preservada. API realmente encerrada gera erro visível, sem sucesso fictício.
MQTT TLS/QoS1 passa ao PostgreSQL e API autenticada com message_id identificável.

Autonomia: seleção local não altera estado efetivo. Falta de autoridade impede
troca. Relatórios completos de fontes confiáveis foram emitidos **apenas pelo
hook de Backend no ambiente isolado**, sem endpoint para o navegador atestar
fila vazia. Cada categoria ativa bloqueou; estados encerrados não bloquearam;
fonte vencida voltou a bloquear. Parada de emergência persistida desabilitou
executor e preservou consulta. Nenhuma contenção real foi executada.

Relatórios intermediários [41](product-source-initial41.json),
[59](product-source-59.json) e [64](product-source-64.json) preservam as
etapas de ampliação da cobertura; não somar contagens como testes distintos.
Frontend: [51 aprovados](frontend-tests.txt).
Controles: [14 aprovados, quatro pulados](controls-regression.txt).
Payload Ubuntu: [proveniência e checksum](ubuntu-payload-check.json), leitura
do próprio `.run`, sem alegar execução desse artefato em Ubuntu nesta rodada.

## Artefatos

Release `native-installers-20261106-candidate.5`;
[recibo com URLs e hashes](../native-installers/published-assets-candidate5.json).

- Ubuntu SHA-256: `9c01092be0c3246fb90e0c6916af5b22c1cc789487eec8935409c8e9b711a3d8`.
- Windows SHA-256: `102ad86dd89d578237451cbe1e457e529510812b2d070b7815e946041b8069ff`.

## Bloqueios concretos e preservação

O ensaio Windows limpo permanece pendente, separado deste teste de processos.
Nova instalação/reboot Ubuntu da candidata 5 também pendente. VM do usuário
continua na candidata 4; nenhum patch, migração ou reset aplicado nela.
Aceite Ubuntu da candidata 3 e seu reteste com falha permanecem intactos.
Releases e snapshots anteriores preservados.

Ainda faltam produtores autoritativos operacionais integrados; por padrão a
instalação não atesta que a fila está vazia. Aprovação/execução/verificação
operacionais permanecem sem comandos disponíveis. Cadastro não configura
credenciais, ACL, broker ou firmware. Captura/backup externos não ganham
aplicação fictícia. Hash final XAI e reconciliação de contratos das branches
externas são necessários antes de incorporar essas entregas.

O estado detalhado e encaminhamentos manuais estão em
[PRODUCT_CONSOLIDATION_20261106.md](../../PRODUCT_CONSOLIDATION_20261106.md).
