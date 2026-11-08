# Implantação controlada de autonomia — pré-inspeção

## Autorização e limites

O complemento do usuário autoriza implantar os componentes desta entrega após implementação e testes locais. Preservar PostgreSQL, dados e integrações P08/P09. Não alterar IPs, rotas, VPN ou nftables; não iniciar ataques, coletores, inferência operacional ou contenção real.

## Evidências na VM

Inspeção somente de leitura em 2026-10-27, aproximadamente 19:57–20:01 -03:00, por SSH autorizado para `harpiserver@100.66.89.7`; hostname retornado: `gateway`.

- `harpisense-p11.service`, `harpisense-mqtt.service` e `postgresql@18-main.service` ativos.
- API: `/opt/harpisense/staging/p11-postgresql`, Python `/opt/harpisense/venv/bin/python`, Uvicorn em `127.0.0.1:8000`, módulo `app:app`.
- MQTT usa o mesmo diretório e executa `mqtt_consumer.py`.
- `/api/v1/p11/health` sem credenciais retorna HTTP 401. Isso comprova apenas a exigência de autenticação; não comprova saúde autenticada.
- `/api/v1/health` retorna HTTP 404; não é a rota de saúde desta instalação.
- `sudo -n -l` retorna `interactive authentication is required`.
- Há arquivos e backups específicos da VM, inclusive `auditoria_p08.py` e variantes do consumidor MQTT. Não substituir o diretório com uma cópia local.
- SHA-256 de `app.py`: `52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2`.
- SHA-256 de `postgres_store.py`: `cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c`.

Não houve escrita remota, migração, backup, implantação ou reinício nesta inspeção.

## Candidata local e impedimento atual

Worktree: `harpisense-worktrees/frontend-backend-autonomia`, branch `feat/frontend-backend-autonomia`, HEAD observado `c2eaed6`. Há alterações não commitadas no frontend e módulos novos em `backend/delivery` e `backend/domain`. O conjunto de arquivos alterados mudou entre inspeções, incluindo `frontend/scripts/p11-proxy.mjs`; ainda não existe um artefato estável identificado e validado por esta sessão.

`backend/delivery/app.py` compõe PostgreSQL, HarpIA determinística e controles; seu conteúdo não equivale ao pequeno `app.py` ativo na VM. A comparação completa dos módulos e das alterações remotas permanece pendente. Não foi executada suíte local nesta inspeção.

## Procedimento antes da aplicação

1. Finalizar e testar a candidata; registrar commit, arquivos e hashes do pacote fechado.
2. Ler a composição ativa e dependências reais; comparar arquivo a arquivo, preservando adaptações remotas e consumidores P08/P09.
3. Identificar hospedagem do frontend e seu proxy; ainda não determinada nesta inspeção.
4. Preparar backup restrito dos arquivos substituídos e unidades afetadas, manifesto de hashes e rollback exato. Se houver migração, revisar SQL e preparar backup e restauração sem remover dados existentes.
5. Preparar aplicação com verificação dos hashes de origem para recusar alterações concorrentes. Não copiar `.env`, credenciais ou módulos de integração antigos.
6. Se necessário após aplicação, o comando de reinício da API será `sudo systemctl restart harpisense-p11.service`: interrompe brevemente e inicia apenas a API P11 com os arquivos então instalados. Não executar esse comando antecipadamente. O usuário deverá executá-lo no terminal caso continue necessária autenticação sudo interativa; nunca solicitar senha no chat.
7. Reiniciar frontend somente se seu modo de hospedagem exigir; não reiniciar MQTT ou PostgreSQL sem necessidade comprovada.

## Matriz de validação pendente

| Critério | Evidência nesta sessão |
| --- | --- |
| SSH | Acesso confirmado |
| Autenticação | Rota de saúde recusa acesso sem credenciais (401); login autorizado pendente |
| Saúde autenticada da API | Pendente |
| Consulta de telemetria existente | Pendente |
| Frontend conectado ao backend real | Pendente |
| Perfil de autonomia persistido e consultado | Pendente |
| Recusa de troca com pendências | Pendente |
| Recusa de troca com estado desconhecido | Pendente |
| Bloqueio de execução real | Pendente de teste; implementação local declara bloqueio |
| Testes locais da candidata | Não executados nesta sessão |

O relatório deve ser atualizado após fechar e testar a entrega e aplicar a candidata. Nenhuma validação local deve ser apresentada como validação na VM.
