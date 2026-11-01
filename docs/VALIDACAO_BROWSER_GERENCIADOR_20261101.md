# Navegador → HTTP → PostgreSQL — candidata integrada

Executado em 01/11/2026, aproximadamente 22:22–22:28 UTC. Base limpa conferida:
feat/frontend-backend-autonomia em 4adf234. Entrega frontend 40908b3 incorporada
uma única vez por cherry-pick de3fefe. Outras worktrees e main preservadas.
Prioridade de fontes: referencias/versão_v2 (Versao_v2), complementada por
referencias/Versões corretas quando o componente ainda não foi atualizado.

## Ambiente real local

Portal Maestri: HarpiSense Local Gerenciador. Browser Chromium do portal acessou
http://127.0.0.1:5174. Vite usou /p11-api com allowlist existente, destino
http://127.0.0.1:18001. Uvicorn serviu delivery.app.build_candidate_app com
autenticação administrativa existente. PostgreSQL 18.6 exclusivo:
harpisense-browser-20261101, loopback 55444, banco config_fixture.
Nenhum TestClient, route.fulfill, interceptação de resposta ou mock HTTP foi usado
no ensaio descrito abaixo. Cliques DOM via evaluate foram usados quando o portal
informou janela sem renderização; não substituíram as requisições reais.

Fixture explícita em backend/config_manager_tests/browser_fixture.py: --prepare
executa as migrações aprovadas e provisiona somente a conta/instalação descartáveis;
execução sem esse argumento apenas inicia o servidor. Guard recusa outro banco,
host ou porta. Instalação browser-local-20261101; conta browser-admin, sem usar
credenciais da VM. Python 3.12 no venv local existente, sem instalação global.
Servidor não adicionou CORS. Vite continua cors=false, bind loopback e validação
de origem. Proxy preserva Bearer/no-store e não permite ingestão técnica pelo browser.

Capabilities explícitas e exclusivamente sintéticas: revision=browser-fixture-only-1,
host broker.browser.invalid, CA browser-ca, segredo por referência
secret://fixture/mqtt, tópico fixture/telemetry. Demais conjuntos vazios.
Não comprovam capacidade/conectividade/autorização da VM ou broker. A proposta
ensaiada usa apenas display_name/timezone; não testa MQTT real ou essas referências.

## Resultados observados

| Ação no portal | HTTP real e confirmação |
| --- | --- |
| Login pelo formulário | POST admin-auth/login 200; sessão e dashboard P11 200; LOGIN na auditoria SQL |
| Abrir Configurações | GET setup/current/catalog/history 200, instalação inicialmente sem progresso |
| Nome/fuso e Salvar e continuar | PUT setup 200; versão 1, step=deployment, SETUP_SAVED no SQL |
| Recarregar página | retornou ao formulário, pois token só existe em memória; novo login 200 |
| Reabrir Configurações | retomou versão 1 e etapa 2. Perfil com os dados salvos; consultas setup/current 200 |
| Revisão e Criar proposta | POST proposals 200; revisão 1, evento PROPOSED |
| Validar proposta | POST proposals/{uuid}/validate 200; VALIDATED, effective_revision=null |
| Histórico | GET history 200; eventos PROPOSED/VALIDATED renderizados e conferidos no SQL |
| Fuso inválido Invalid/Browser | progresso parcial aceito; POST proposals 422 sem criar revisão nem mudar efetiva; campos preservados e aviso visível |
| Segundo escritor do progresso | segunda sessão criada no mesmo browser por fetch real; PUT setup 200 versão 5; formulário antigo recebeu PUT setup 409 e preservou valores |
| Segundo escritor da configuração | segunda sessão fez POST proposals com expected_revision=1, criou revisão 2; formulário antigo recebeu POST proposals 409, revisão atual 2 |
| Reconciliação | Consultar versão atual, Criar proposta, Validar: revisão 3 VALIDATED, sem aplicação |
| Logout | botão Sair fez POST logout 204; formulário reapareceu; fetch sem sessão a setup e P11 health retornou 401 |

As chamadas auxiliares dos segundos escritores ocorreram dentro do portal usando
fetch nativo para o mesmo proxy. Criaram concorrência real no servidor; não foram
mocks nem mudanças diretas de revisão no SQL. Tokens ficaram em variáveis locais
e nunca foram retornados ou gravados nas evidências.

Encontrado e corrigido nesta integração: histórico usa coluna API `at`, enquanto
frontend só procurava created_at/observed_at. Agora o horário do evento SQL aparece
na tela. A alteração de fonte pelo Vite recarregou a sessão; novo login e leitura
do histórico confirmaram a correção. Não foi considerado logout aquele reload.
Os logouts aceitos são os POST 204 e eventos LOGOUT posteriores.

## Evidência verificável

Diretório docs/evidence/browser-config-20261101:

- http-access-part1/2/3.log: saída real de acesso Uvicorn, somente métodos,
  caminhos/status e conexões loopback; segmentos capturados ao longo do ensaio.
  Não contêm bodies, Authorization, senhas ou tokens. Não são trace completo de
  cada polling desde o startup; o primeiro trecho consumido no terminal não foi
  recuperado artificialmente. LOGIN também está comprovado na auditoria SQL.
- validated-ui.json e final-validated-ui.json: textos reais da interface, revisões
  1 e 3 validadas, operational=false e efetiva ausente.
- resumed-ui.json: nova sessão retomou versão 5, etapa Revisão e nome/fuso
  persistidos. A primeira retomada da versão 1/Perfil foi observada no terminal.
- validation-error-ui.json: erro 422 e valores preservados.
- conflict-ui.json e proposal-conflict-ui.json: conflitos de progresso e revisão.
- concurrent-writer.json: status 200 da proposta concorrente no navegador.
- history-ui.json: horários de PROPOSED/VALIDATED após correção de `at`.
- logout-ui.json e final-logout-ui.json: formulário presente, setup/P11 sem sessão
  401, localStorage sem senha/token (lista de chaves vazia neste ensaio).
- postgresql-receipt.json: SELECTs em transação READ ONLY via browser_receipt.py.
  Confirma instalação desired_revision=3/effective_revision=null, operações
  1 VALIDATED / 2 DRAFT / 3 VALIDATED, progresso versão 5, cinco SETUP_SAVED,
  PROPOSED/VALIDATED e LOGIN/LOGOUT com horários UTC. Não exporta token_hash,
  password_hash ou valores de credenciais. As sessões esquecidas por reload
  continuam sujeitas à expiração no banco descartável; não são declaradas revogadas.

Esses artefatos são evidências desta sessão local, não atestados assinados da VM.
SQL e logs relacionam os UUIDs reais das operações e os eventos renderizados.
Não houve alteração de estado desejado/efetivo por escrita SQL manual.

## Verificação complementar e preservação

Build TypeScript/Vite aprovado; 38 testes frontend aprovados, sem skips. Esses
testes são complementares e continuam separados do ensaio HTTP real acima.
As 29 provas TestClient/PostgreSQL e 18 regressões da rodada anterior não foram
recontadas como testes de navegador. O build é local, não implantação na VM.

P11/telemetry, health e demais consultas do dashboard retornaram 200 no HTTP real.
Fixture tem zero projeções: não é ensaio de telemetria física nem ingestão do
Poste 2 em operação. HarpIA/Record/PostgresStore/callbacks não receberam mudanças;
bootstrap usa a composição aprovada, sem habilitar geração ou inferência.
Poste 1 fechado; sem broker, rede, firewall, VMs, flash ou contenção alterados.
Catálogo mantém available=false e applicators vazio. Perfil/dispositivos/backup
salvos no progresso não configuram serviços; placa ESP32-WROOM-32 com LDR/LED é
somente o perfil atual, sem outros firmwares declarados implementados.

## Reprodução e processos

Criar PostgreSQL descartável em loopback 55444, banco config_fixture. Definir
DATABASE_URL para essa fixture e HARPISENSE_BROWSER_FIXTURE_PASSWORD por variável
local, além das credenciais técnicas de fixture exigidas pelo bootstrap existente.
PYTHONPATH=backend;backend/domain;genai. Executar com o venv:

```powershell
python backend/config_manager_tests/browser_fixture.py --prepare
python backend/config_manager_tests/browser_fixture.py
# Em outro terminal, frontend/:
$env:HARPI_API_TUNNEL_TARGET='http://127.0.0.1:18001'
npm.cmd run dev
```

Não apontar a fixture para ambiente operacional. Conta criada apenas na preparação;
segredo da fixture não está neste documento. No portal, usar /p11-api e conta de
teste provisionada, nunca modo demonstração. Repetir os passos da tabela; IDs e
revisões dependerão do estado da fixture. browser_receipt.py exporta só o recibo
sanitizado, sem autenticar navegador ou mudar estado.

Ao encerrar esta rodada, backend PID 9044/exec session 72329, Vite exec session
14237 e container dedicado foram mantidos para inspeção local. Portal ficou no
formulário após logout. Duração após encerrar o aplicativo não é garantida.
Não houve novo túnel SSH. Antes de iniciar outra instância, conferir listeners.

## Próxima entrega: primeiro aplicador real limitado

Backend/Arquiteto devem entregar um aplicador de **apresentação da instalação**,
somente display_name e timezone de exibição da aplicação; não alterar timezone do
Ubuntu, rede, MQTT, captura, dispositivos ou backups. Reutilizar ConfigStore,
components_for e componente config-registry existente. Recusar plano que inclua
remoção/alteração de qualquer outro grupo sem aplicador correspondente.

Contrato mínimo a implementar e testar primeiro em fixture:

1. Worker interno autorizado recebe operação VALIDATED e manifesto fixado;
   begin_application fornece revision/hash/fence. Reautenticação e autorização
   para iniciar aplicação precisam de contrato antes de oferecer ação no frontend.
2. Consumidor real da apresentação carrega artefato versionado local sob diretório
   da aplicação. Aplicador grava atomicamente somente nome/fuso, preservando
   artefato anterior/hash/permissões. Nenhum comando livre ou caminho do navegador.
3. Verificador independente consulta o backend que efetivamente consumiu o
   artefato e confirma valores, revisão, hash e fence; não basta reler a proposta
   do registry. Só então record_verified + confirm_application com recibo interno.
   GET current pode indicar revisão efetiva desse escopo sem declarar prontidão
   global ou mudar operational=false sem um verificador global homologado.
4. Falha antes de efeitos permite FAILED somente com prova de ausência de efeitos.
   Falha parcial/read-back divergente usa RECOVERY_REQUIRED e invalida worker
   antigo. Rollback restaura atomicamente o artefato anterior e verifica o consumidor;
   registrar recuperação e preservar auditoria, sem apagar versões. Modelo exato
   de reconciliação/fencing do rollback deve ser fechado antes da implementação.
5. Aceite: sucesso visto na interface, reinício mantendo apresentação, timeout,
   concorrência/worker obsoleto, falha entre escrita e recibo, rollback verificado
   e prova de nenhuma mudança em P11, autenticação, consumidores ou outros grupos.

Esta é a próxima entrega proposta, não um aplicador implementado nesta rodada.
