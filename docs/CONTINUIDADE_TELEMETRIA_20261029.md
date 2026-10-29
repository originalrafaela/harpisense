# Continuidade HarpiSense V2 — 29/10/2026

Base de integração: `D:\Projetos\tcc - harpisense\harpisense-worktrees\frontend-backend-autonomia`,
branch `feat/frontend-backend-autonomia`. Base publicada conferida diretamente no remoto:
`901053edad08e5f86933a369bfa82878f18b0423`. Não havia commits posteriores nem alterações
locais nessa worktree ao iniciar. Nenhum merge ou alteração da main foi realizado.

## Preservação e precedência

Referências locais reais: `D:\Projetos\tcc - harpisense\referencias\versão_v2` e
`D:\Projetos\tcc - harpisense\referencias\Versões corretas`. Nenhum acesso ao Drive.
O consolidado de 27/10 prevalece nos requisitos novos; os pacotes preservados e a
implantação real continuam sendo a referência de implementação. Não há Poste 3
no ensaio e nenhum terceiro dispositivo foi criado nesta rodada.

`docs/continuity/2026-10-29/` preserva:

- `frontend-v2.patch`: atualização automática e teste que existiam somente localmente
  em `frontend-v2` (`frontend/harpisense-v2`, HEAD `f52d8373d83c724f023a17365423bbe75145fcee`).
- `integration-p11.patch`: ajuste local de contraste de CSS, preservado na origem;
  a base escolhida já contém evolução posterior do contraste, sem necessidade de copiar esse CSS antigo.
- `local-changes.json`: hashes dos arquivos locais anteriores às alterações desta rodada.
- `preexisting-deployment-note.md`: cópia do relatório não rastreado da raiz, sem remover o original.
- `branches.txt`, `worktrees.txt`: inventário inicial; entradas antigas marcadas prunable
  não foram removidas. Documentos e referências não rastreados da raiz foram preservados.
- `reference-frontend-comparison.json`: comparação do snapshot em referências com a candidata;
  a cópia de referência não substitui a worktree Git.

A branch de integração já contém transporte P11, telemetria, HarpIA, controles guardados
e a prévia publicada; `frontend-v2` tem uma base anterior. A correção local foi aplicada
por trecho, sem copiar pastas ou fazer merge das outras branches. Os originais locais
continuam não commitados em suas respectivas worktrees, mas os patches estão preservados
nesta entrega. `frontend-v2` e o snapshot `referencias/versão_v2/frontend-v2` são caminhos diferentes.

## Implantação efetivamente encontrada

SSH confirmado para `harpiserver@192.168.155.144`, hostname `gateway`. Tailscale
`100.66.89.7` apresentou timeout durante esta rodada; nenhuma rede foi reconfigurada.

| Componente | Estado observado |
| --- | --- |
| P11 | `harpisense-p11.service`, ativo, cwd `/opt/harpisense/staging/p11-postgresql` |
| Bootstrap | `app.py`, SHA-256 `52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2` |
| API | Uvicorn `app:app`, `/opt/harpisense/venv/bin/python`, loopback `127.0.0.1:8000` |
| P11 aprovado | `create_app` de `/opt/harpisense/integration-v2/HarpiSense_Pacote13_Integracao_Testes_v2/componentes/p11/backend11/service.py`, SHA `8cb67932cc2f7ef22ed357b0c94f7a8cb416cde164db60866dd6df5cf7fb8698` |
| Autenticação atual | HTTP Basic administrativo; ingestão técnica exige também token de serviço |
| Persistência | `PostgresStore`, banco `harpisense`, role `harpisense_app`, tabela `projections` |
| Store | SHA `cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c`; revisões imutáveis e lock transacional por entidade |
| HarpIA | `harpia_deterministic`, complemento ativo; health `deterministic_only`, `generation_enabled=false` |
| Consumidor | `harpisense-mqtt.service`, ativo, `mqtt_consumer.py` no mesmo cwd; SHA `188490130d89a3eebe6370bd23e645cd5089ef18f80364624b3f3e0ce0da8f30` |
| Broker real | Windows, serviço Mosquitto, binário `D:\Programas\Mosquitto\mosquitto.exe`; configuração `D:\Programas\Mosquitto\mosquitto.conf` |
| Listener | `192.168.155.1:1883`, `allow_anonymous false`, password_file configurado; nenhuma ACL ativa identificada nas diretivas consultadas |
| Consumidor → broker | usuário `harpisense_mqtt`; senha em arquivo protegido `.mqtt_password`, valor não exposto |
| Publicador Poste 2 | VM `harpisense@192.168.155.142` responde; inspeção depende de autenticação SSH autorizada |

O backend local `backend/delivery` compõe controles e outras capacidades e não é o
bootstrap ativo. Não foi implantado sobre o P11. A candidata de paginação PostgreSQL
também não substituiu o Store ativo. Hashes completos e leituras SQL/API estão em
`continuity/2026-10-29/vm-inspection.json`. O health descreve capacidades, mas não
prova sozinho a saúde do banco; a consulta SQL desta rodada foi somente leitura.

## Contrato MQTT confirmado no código ativo

- Broker `192.168.155.1:1883`; tópico `harpisense/poste2/telemetry`, assinatura QoS 1.
- UTF-8 JSON objeto com `device_id` exatamente `poste2`. Não renomear para `poste-2`.
- ID persistido: `poste2-` + SHA-256(`topic UTF-8` + byte nulo + `payload original`).
- Projeção `kind=telemetry`, `revision=1`, `source=trusted-service`, payload preservado.
- `created_at` é horário de persistência; não é inventado como horário da medição.
- Republicação dos mesmos bytes é idempotente. Campos de auditoria P08 não são telemetria.
- O consumidor atual não aplica o schema candidato da Etapa 6 e não deve receber
  uma migração de payload presumida. Esta rodada não afrouxou sua validação.

Inspeção inicial: 11 projeções telemetry e 7 window. A mais recente era
`poste2-fc723b0cd9ef53c2f3fbfed76841288cb29c7ab8e2b3bec99fb2e78b9e3983c8`,
registrada em `2026-10-28T02:39:32.675522-03:00`. PostgreSQL e API devolveram
o mesmo envelope. O journal de hoje registra conexão autenticada, sem nova
gravação até a inspeção. Isso não identifica sozinho a causa no publicador.

## Correções e verificações

Atualização automática incorporada: nova consulta dez segundos após a anterior
terminar; sem sobreposição; navegação/logout cancelam requisições e timer. A prévia
permanece sem consultas operacionais. Falhas aparecem explicitamente e não são
substituídas por dados demonstrativos.

Registros reais também contêm `luminosity` e `led_state`. A interface agora apresenta
esses campos sem mudar o payload: `luminosity` sem unidade nem conversão para lux/LDR;
`led_state` ON/OFF como informado. Não é evidência de sensor físico ou estado atual.

Testes: 29 testes Node aprovados, typecheck/build aprovados; 20 testes Chromium
na primeira verificação (dashboard, fluxo P11 e prévia); após o ajuste de campos,
16 testes de dashboard/fluxo P11 aprovados. Não são testes de ataques ou modelos.

Chromium conectado ao P11 real confirmou o registro antigo na interface, consultas
periódicas, erro de conexão induzido somente no navegador, recuperação e zero chamadas
operacionais na prévia. Evidência sanitizada em
`continuity/2026-10-29/live-validation-existing-record.json`; screenshots em
`frontend/local-evidence/`, ignorado. Esta verificação NÃO comprova publicação nova.

## Responsabilidades do backend

Agente conectado `Backend Data`: somente `backend/admin_auth/`,
`backend/admin_auth_tests/`, `docs/AUTENTICACAO_ADMINISTRATIVA_V2.md`.
Conta administrativa e sessão são aditivas, opt-in e não foram ativadas na VM.
Bootstrap, Store existente, frontend, integração e implantação pertencem ao arquiteto.
Nenhum agente deve editar esses mesmos arquivos em paralelo. Autenticação P11,
persistência, contratos e HarpIA ativos foram informados ao agente. Módulo de sessão
não pode ser instalado antes da integração correspondente no frontend/transporte.

## Recuperação e retomada exatas

Nenhum arquivo remoto foi substituído, nenhum serviço da VM foi reiniciado e nenhuma
migração foi aplicada. PostgreSQL, P08/P09, checkpoints e configurações permaneceram
preservados. Não foi necessária ação sudo nesta etapa.

Para retomar esta worktree (consultar o hash final com `git rev-parse HEAD`):

```powershell
Set-Location 'D:\Projetos\tcc - harpisense\harpisense-worktrees\frontend-backend-autonomia'
git status --short --branch
git log -3 --oneline
```

Em um terminal, abrir o transporte; não abrir outro se a porta 18000 já estiver ocupada:

```powershell
ssh -N -T -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 -o ExitOnForwardFailure=yes -o GatewayPorts=no -o ServerAliveInterval=30 -L 127.0.0.1:18000:127.0.0.1:8000 -i C:/Users/amara/.ssh/harpiserver_ed25519 harpiserver@192.168.155.144
```

Em outro terminal:

```powershell
Set-Location 'D:\Projetos\tcc - harpisense\harpisense-worktrees\frontend-backend-autonomia\frontend'
# Somente se node_modules ainda não existir: npm.cmd ci
.\scripts\run-telemetry.ps1
```

Interface `http://127.0.0.1:4174`, perfil `P11`, URL `/p11-api`. O script preserva
o dist anterior em `frontend/local-evidence/deployment-backups/<horário>/dist`,
registra HEAD, compila com `VITE_P11_RESOURCES=telemetry` e serve no loopback.
Ctrl+C encerra somente esse servidor. Não grava `.env` nem altera serviços remotos.
O portal `HarpiSense V2 Continuidade` abre a prévia isolada nesse endereço.

Recuperação do artefato local, se necessária: parar somente esse preview com Ctrl+C,
preservar o dist que falhou e restaurar os arquivos da pasta de backup registrada
pelo script, no mesmo diretório frontend. Também é possível construir a base anterior
em outra worktree, sem reset da atual:

```powershell
git worktree add --detach '..\telemetry-rollback-901053e' 901053edad08e5f86933a369bfa82878f18b0423
```

Repetir inspeção somente leitura da VM:

```powershell
Set-Location 'D:\Projetos\tcc - harpisense\harpisense-worktrees\frontend-backend-autonomia'
Get-Content -Raw .\docs\continuity\2026-10-29\inspect_p11_readonly.py | ssh -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 -i C:/Users/amara/.ssh/harpiserver_ed25519 harpiserver@192.168.155.144 '/opt/harpisense/venv/bin/python -'
```

## Aceite pendente

Ainda é necessário inspecionar o publicador real no Poste 2, executar uma única
publicação legítima identificada conforme seu contrato, registrar horário/bytes/ID
e conferir o MESMO registro em SQL, API e atualização automática da tela.
Não publicar a partir do gateway fingindo origem no Poste 2. A solicitação de acesso
foi enviada sem pedir senha; depende da ação do operador. Até essa etapa, o aceite
ponta a ponta permanece aberto. Não há Poste 3, ataque, novo coletor P08, inferência
operacional ou contenção nesta rodada.
