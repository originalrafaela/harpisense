# Ponto de continuidade — pausa por limite de créditos

Pausa solicitada pelo usuário em 04/11/2026. Não iniciar novas verificações nem publicar novamente.

Branch: feat/p08-evidence-coverage. Worktree: harpisense-worktrees/p08-evidence-coverage. Base anterior: a2e7a2f259992021f02dd545ca1b3406d4b5c0a8.

Mensagem simulada única aceita pelo broker:
- ID: poste2-2aaecdebdf958fb477df944622d7aede8926a3effe2beaa831a8395129f67e9b
- sent_at: 2026-11-04T18:43:25Z
- luminosity: 351; led_state: ON; device_id: poste2
- tópico: harpisense/poste2/telemetry; broker: 192.168.155.1:1883; QoS1; PUBACK RC0

Estado de aceite determinado pelo usuário: mesma mensagem confirmada até o PostgreSQL, incluindo log do consumidor. API e frontend permanecem PENDENTES. O relato anterior de interface não encerra essas etapas. Não repetir a publicação para verificá-las. PostgreSQL: revision1, source trusted-service, created_at 2026-11-04T15:43:25.799580-03:00. Recibo e cursor: ACEITE_POSTE2_2026-11-04.json. Consulta anterior à API com Basic antigo retornou401; autenticação atual requer sessão administrativa Bearer. Não armazenar ou pedir segredos em mensagens.

Na retomada autorizada: consultar pela sessão administrativa existente a mesma mensagem na API e frontend e registrar evidência sanitizada; depois continuar percurso e cursores P08. A rota informada pelo operador ao broker é direta por ens33/src192.168.155.142, sem via10.20.30.1. Entrega MQTT não prova passagem pelo gateway, cobertura de captura, perdas ou vínculos com janelas. Faltam intervalos/cursores de fontes obrigatórias e limite de erro entre relógios; gates permanecem desconhecidos, sem aprovação forçada.

Antes de editar backend/p08_p09, combinar com o arquiteto a propriedade dos arquivos Edge/composição. Nenhum arquivo desse diretório foi alterado nesta rodada. Referências: referencias/versão_v2 primeiro; Versões corretas para componentes não substituídos. Executor existente localizado no Pacote10 e RF/IF/Risk/Policy no Pacote09; não implementados ou homologados nesta rodada.

Nenhuma configuração, credencial, tópico, rota, firewall ou contenção remota foi alterada. Não habilitar contenção. Frontend local em127.0.0.1:4174 e túnel local18000 foram iniciados a pedido do usuário; sem promessa de persistência após a pausa. Não realizar novas ações operacionais durante a pausa.

Maestri: tentativas de reporte por ask para HarpiSense Arquiteto falharam com No connection; list identifica o próprio terminal como destinatário. Corrigir o vínculo na retomada antes de coordenar novas ações. IoT MQTT havia informado nenhuma publicação própria iniciada/agendada. Não republicar.
