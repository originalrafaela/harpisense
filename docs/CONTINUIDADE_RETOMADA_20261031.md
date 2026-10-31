# Retomada — 31/10/2026, 18:04 UTC

Referências: ENCAMINHAMENTOS_CONSOLIDADOS_20261031.md,
CONTINUIDADE_ENCERRAMENTO_20261031.md,
VALIDACAO_FRONTEND_CONTA_20261031.md e INSPECAO_PERCURSO_POSTE2_20261031.md.
Prioridade mantida: referencias/versão_v2; componentes anteriores continuam
em referencias/Versões corretas. Nenhuma entrega foi refeita.

## Resultados comprovados

- Raiz main 9d58e69, atrás 3; arquivos locais não rastreados preservados.
- Worktree de continuidade feat/frontend-backend-autonomia em 9e4467e;
  registros anteriores não rastreados preservados. Config-manager em edd0cb7,
  worktree limpa. Nenhum reparo de worktree ou alteração IoT/MQTT.
- GitHub consultado nesta retomada: frontend ainda a098343; Edge publicado em
  1cf058e1b1ffbf08a954d56ee082759be2eae49e; nenhuma referência remota para
  feat/config-manager-stage1. Não houve push.
- VM gateway: harpisense-p11 e harpisense-mqtt active; API 127.0.0.1:8000,
  PostgreSQL 127.0.0.1:5432; ens33 192.168.155.144 e ens37 10.20.30.1.
  Rota ao broker 192.168.155.1 pela ens33. Broker local escutando
  192.168.155.1:1883, PID 21748. Isso não comprova a rota do Poste 2.
- Integrador legado /opt/harpisense/staging/p08-captura/integracao/integrar_p08.py
  SHA256 f1537b54ba721153b3daf8a09a09ba1e7aef24aee4a513828302ca237e5f06a5,
  igual ao registro anterior. Não implantado P08 nem alterada defesa/rede.
- Túnel SSH loopback 18000 → API loopback 8000 retomado. Ativação aprovada
  conferiu hashes e handshake 401 Bearer. Preview PID 40800, release
  admin-session-20261030-r1, source a098343. Backup preservado em
  frontend/local-evidence/deployment-backups/auth-20261031-150354-32.
- Mesmo portal Maestri HarpiSense V2 Continuidade, URL
  http://127.0.0.1:4174/, formulário real observado. Login, telemetria,
  atualização automática, logout e expiração no navegador continuam pendentes
  de entrada interativa. Resultado HTTP anterior não foi repetido como aceite.

## Encaminhamento curto preparado ao backend

> A branch feat/config-manager-stage1 não apareceu no ls-remote desta retomada.
> Commit local aprovado: edd0cb7e1d92e14a2518790db61a7b0c0ffef8dd.
> Na worktree config-manager-stage1, conferir HEAD e executar
> `git push -u origin feat/config-manager-stage1`; devolver o SHA obtido por
> `git ls-remote origin refs/heads/feat/config-manager-stage1`.
> Preservar a base a098343 e a política mínima 8 de 9e4467e na futura integração.
> Sem merge, migração ou implantação nesta rodada.

Texto preparado para repasse manual; nenhuma mensagem enviada a outro agente.

## Captura e contenção

Rotas atuais do Poste 2 ainda não recebidas. Mantida a matriz dos encaminhamentos:
se direto ao broker Windows, propor observação no endpoint publisher ou broker;
contenção separada por ACL MQTT e/ou firewall do endpoint, com escopo e reversão.
Se trânsito pelo HarpiServer for comprovado, definir sensores de entrada/saída
e avaliar FORWARD. INPUT vale para serviço local. ens37 não foi presumida.
Não iniciar PCAP, instalar sensor, habilitar forwarding ou ativar defesa.

## Próxima alteração mínima

Nenhuma alteração operacional indicada. Primeiro, operador entra no formulário
do portal observável com sua senha; depois observar telemetria/polling/logout
e expiração, distinguindo expiração real de simulação. Em seguida solicitar,
um passo por vez, o inventário do Poste 2 já definido nos encaminhamentos.

Para abrir o portal já disponível no PowerShell:
`Start-Process 'http://127.0.0.1:4174/'`.
Senha somente no formulário, nunca no chat. Prévia frontend-v2 preservada.

## Retorno do operador e conferência seguinte

Operador relatou entrada administrativa e painel aberto e autorizou continuar
telemetria, atualização automática, logout e expiração. Na conferência seguinte,
o portal conectado HarpiSense V2 Continuidade ainda mostra o formulário de login.
O relato não foi convertido em aceite observado: a sessão pode estar no navegador
externo, que não compartilha a sessão em memória desta aba. Não foi executado
logout ou teste de expiração em uma sessão não observável. Próximo passo:
entrada do operador diretamente no portal conectado, sem recarregá-lo depois.

## Atualização posterior — contrato Poste 1 e publicação backend

Publicações confirmadas por ls-remote: docs/poste1-compatibility-20261031 em
fe88645fee55a9922a3633ff941219f7cb15d176 e feat/config-manager-stage1 em
edd0cb7e1d92e14a2518790db61a7b0c0ffef8dd. Pendência anterior de push do backend
resolvida: disponível para integração, ainda não operacional.

Decisão concreta em DECISAO_CONTRATO_POSTE1_20261031.md. Perfil P06/P07 aprovado
documentalmente para entrada LDR do Poste 1, sem alterar P03/Poste 2. Backend Data
responsável pelo adaptador limitado à entrada e pelo reuso do store PostgreSQL.
21 testes P06 e exemplo exato da matriz passaram em venv isolado; pendência de
jsonschema resolvida sem Python global. Decisão encaminhada ao IoT via Maestri,
somente para recebimento, sem iniciar implementação. Nenhuma alteração de broker,
firmware, consumidor operacional ou implantação. Próximo ajuste mínimo proposto
está no documento e depende de rodada própria; login observável e rotas seguem
pendentes de dados do operador, independentes desta decisão documental.
