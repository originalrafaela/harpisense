# Aceite de telemetria — em andamento

Inspeção: 29/10/2026, 14:46–14:48, America/Sao_Paulo.
Worktree preservada: `harpisense-worktrees/frontend-backend-autonomia`.
Branch `feat/frontend-backend-autonomia`, base `460c8a3`.
Candidata de autenticação preservada e não ativada.

## Linha de base desta rodada

- Gateway confirmado via SSH: hostname `gateway`, `ens33=192.168.155.144/24`,
  `ens37=10.20.30.1/24`, Tailscale `100.66.89.7/32`.
- `harpisense-mqtt` e `harpisense-p11`: ativos.
- Hashes de bootstrap, consumidor, Store e complemento HarpIA permanecem iguais
  aos da inspeção anterior. Nenhum arquivo remoto foi alterado.
- Banco consultado em transação somente leitura: 11 registros telemetry e 7 window.
- API autenticada: HTTP 200 para health e lista de telemetria.
- Último registro ainda é o histórico de 28/10:
  `poste2-fc723b0cd9ef53c2f3fbfed76841288cb29c7ab8e2b3bec99fb2e78b9e3983c8`,
  `created_at=2026-10-28T02:39:32.675522-03:00`.
- Evidência local sanitizada: `frontend/local-evidence/telemetry-acceptance-baseline.json`,
  observação `2026-10-29T17:47:53.769943+00:00`.
- Interface local respondeu HTTP 200 em `http://127.0.0.1:4174/`.

## Ponto de continuação

O endereço atual do Poste 2 ainda NÃO está confirmado. Não assumir que o endereço
histórico `192.168.155.142` identifica essa VM hoje. A tabela de vizinhos do gateway
nesta inspeção não identifica o Poste 2. Nenhuma varredura foi realizada.

Passo solicitado ao operador no console da VM Poste 2 do VMware:

```sh
hostname; id -un; ip -br -4 address; ip -4 route
```

Essa leitura não altera rede ou autenticação. Após receber a saída, formular o
comando SSH para o endereço e usuário confirmados, com verificação da chave de host.
Se o acesso existente exigir senha, digitá-la somente no terminal SSH do operador.
Não adicionar chaves ao authorized_keys nem habilitar métodos novos de autenticação.

## Aceite ainda aberto

Nenhuma nova publicação foi executada nesta rodada. Ainda faltam inspeção do
publicador existente, publicação legítima rastreável e correspondência do novo
registro no consumidor, SQL, API e atualização automática da tela já aberta.
O impedimento atual é a confirmação/acesso ao Poste 2; não há falha de telemetria
comprovada por essa ausência de acesso. Não declarar os dados de 28/10 como novos.

Sem ataques, novos coletores P08, inferência, contenção, mudanças de autenticação,
rede ou firewall. A prévia visual e os serviços existentes foram preservados.

## Publicação nova confirmada — 29/10/2026, 14:57 BRT

Operador publicou uma única mensagem no console do Poste 2, usando mosquitto_pub,
QoS 1, tópico harpisense/poste2/telemetry. Resultado informado: 0.
Payload informado:
```json
{"device_id":"poste2","luminosity":350,"led_state":"ON","source":"ubuntu","status":"online","sent_at":"2026-10-29T17:56:25Z"}
```
ID esperado e encontrado em SQL e API:
`poste2-9103e45e7868713b35c0b0392313e804638d39121ffb9cd083ff2882a6fc59b5`.

Inspeção SSH somente leitura executada em 2026-10-29T17:57:01.869798+00:00:
- PostgreSQL: 12 telemetry (antes 11), 7 window; novo registro revision=1,
  source=trusted-service, created_at=2026-10-29T14:56:25.316702-03:00.
- API telemetry?limit=3&offset=0: HTTP 200, mesmo ID, payload e created_at.
- Hashes de bootstrap, Store e consumidor iguais aos registrados anteriormente.
- Dados simulados; sent_at informa envio e não comprova medição física.

O script existente demo_poste2.sh repete três payloads fixos em ciclo infinito;
a idempotência explica por que republicar esses mesmos bytes não gera novos IDs.
Não houve alteração desse script nem de serviços remotos nesta verificação.
Aceite do caminho publicação → persistência → API confirmado para esta mensagem.
Ainda falta observar o mesmo registro na interface e confirmar sua atualização
 automática; não declarar o aceite visual concluído.

## Exibição na interface confirmada pelo operador

Após sair da prévia sintética e entrar na consulta autenticada P11, o operador
copiou da tela o registro exato
`poste2-9103e45e7868713b35c0b0392313e804638d39121ffb9cd083ff2882a6fc59b5`,
origem trusted-service, revisão 1, created_at 2026-10-29T14:56:25.316702-03:00,
luminosity 350 (unidade não informada) e led_state ON.
Correspondência publicação → PostgreSQL → API → interface confirmada.
A evidência é relato textual do operador; esta etapa não observou diretamente o
navegador nem demonstrou atualização automática sem navegação ou recarregamento.
Última observação e recebido pelo backend não informados na interface são
compatíveis com a ausência desses campos no payload; sent_at é horário de envio.
O registro é simulado, não comprova sensor físico nem estado atual do dispositivo.

## Segunda publicação única — verificação de atualização automática

Operador informou resultado 0 para payload de luminosidade 351,
led_state ON, device_id poste2 e sent_at 2026-10-29T21:02:21Z.
ID: `poste2-dde5ef6e303b55638111792efef458e5c99d1a6128ab09758b76272b93f5d0dc`.
A saída foi colada duplicada na conversa; isso não é evidência de duas publicações.
Inspeção SSH somente leitura em 2026-10-29T21:03:20.750227+00:00 confirmou:
- PostgreSQL: 13 telemetry e 7 window; ID exato presente, revision 1,
  source trusted-service, created_at 2026-10-29T18:02:21.841219-03:00.
- API telemetry HTTP 200: mesmo ID, payload e horário.
- Hashes de bootstrap, Store, consumidor e HarpIA permanecem iguais.
Ainda aguardando confirmação do operador sobre aparecimento automático na tela,
sem navegação, recarga ou botão de atualização. Não declarar polling validado
com base apenas na persistência/API. Nenhuma nova rodada MQTT solicitada.

## Falha de transporte no teste de polling e recuperação local

Operador informou que a tela apresentou erro de rede/configuração durante o
ensaio de luminosidade 351. Portanto, atualização automática NÃO aceita.
Diagnóstico local: portas 4174 e 18000 sem listeners; página previamente carregada
não comprovava frontend/proxy/túnel ativos. O script run-telemetry.ps1 preservou
backup local-evidence/deployment-backups/20261029-181417, executou typecheck/build
e iniciou Vite preview. Logs Vite registraram tentativas telemetry/health a cada
10 segundos, com ECONNREFUSED em 127.0.0.1:18000; isso confirma tentativas periódicas,
mas não entrega ou renderização de dados novos.
Túnel SSH restabelecido com bind 127.0.0.1:18000, destino remoto 127.0.0.1:8000,
ServerAliveInterval=30 e ServerAliveCountMax=3; sem alteração de rede/firewall.
Verificação posterior: frontend HTTP 200; health direto pelo túnel HTTP 401;
health pelo proxy HTTP 401, sem enviar credenciais. Esses 401 são esperados e
comprovam transporte, não login válido ou aceite de atualização automática.
Nenhum serviço remoto reiniciado, migração aplicada ou autenticação alterada.
Integração de conta/sessão continua autorizada, posterior ao aceite deste teste.
