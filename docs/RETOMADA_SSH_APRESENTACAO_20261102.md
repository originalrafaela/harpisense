# Retomada controlada — diagnóstico SSH de 02/11/2026

## Estado preservado

Worktree `harpisense-worktrees/frontend-backend-autonomia`, branch
`feat/frontend-backend-autonomia`, limpo ao iniciar em `4f82882`.
`1be05034e6e8540e3f3b70db3fe6ad7cf475aba3` é ancestral; os commits
`3a27920` e `4f82882` foram preservados. O delta desde a entrega é documentação.
Main e arquivos não rastreados de outros trabalhos foram preservados.

Referências disponíveis na raiz: `referencias/versão_v2` e
`referencias/Versões corretas`. Vale a precedência solicitada: entregas aprovadas
V2 primeiro, pacotes anteriores para componentes ainda não substituídos.
Ausência em V2 não significa ausência do componente. Não houve nova comparação
de implementação com pacotes nesta etapa bloqueada.

## Evidência nova: chave reconhecida, assinatura não concluída

A primeira leitura de `.ssh` foi negada pelo sandbox e repetida com aprovação.
Somente nomes, tamanhos e fingerprints foram consultados; nenhuma chave privada
foi exportada. Conexão com BatchMode, IdentitiesOnly e StrictHostKeyChecking.

- Host ED25519: `SHA256:Uv4vgbxMChdUGjvlC8Dw+j/xQRZtVDPn5+17OpJPboA`.
  OpenSSH confirmou correspondência ao known_hosts existente.
- Chave Maestri: `SHA256:IG+aHyl7L4KwVf9+XkYcvgNmZaNsgP1CxwfKGznQuQY`.
  O diagnóstico registrou `Server accepts key`, seguido de
  `we did not send a packet, disable method` e falha de autenticação.
- Serviço Windows `ssh-agent`: Stopped; `ssh-add -l`: agente indisponível.
- Chave deploy existente: `SHA256:xsNDn5cDyqtMCDBDSqsXm1nTqcO77VUHaWXagbKGlgM`;
  tentativa Batch também não concluiu autenticação.

Isso corrige a interpretação anterior de chave simplesmente recusada: a chave
pública Maestri é reconhecida; falta concluir a assinatura local. Chave protegida
sem agente é hipótese compatível, ainda não confirmação. Não modificar
authorized_keys, known_hosts ou criar chave substituta.

## Ação mínima do operador no terminal

No PowerShell elevado, iniciar o agente existente (sem mudar seu tipo de início):

```powershell
Start-Service ssh-agent
```

Depois, no terminal da conta Windows usada pelo Maestri:

```powershell
ssh-add "$env:USERPROFILE\.ssh\harpiserver_maestri_ed25519"
ssh-add -l
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes -i "$env:USERPROFILE\.ssh\harpiserver_maestri_ed25519" harpiserver@100.66.89.7 'date -u; hostname; id -un'
```

`ssh-add` pode solicitar a frase secreta local da chave no próprio terminal.
Não enviar frase, senha ou chave ao chat. O serviço guarda a chave para assinatura;
nenhum desses comandos altera arquivos ou serviços da VM. Se a chave não carregar,
preservar o erro sanitizado e investigar antes de qualquer mudança no servidor.

## Implantação e recuperação

Versão implantada: **não verificada**, implantação não iniciada. Sem sessão SSH,
não foi possível comparar bootstrap, módulos, dependências, migrações, unidades,
frontend servido ou mudanças concorrentes da VM. Inventário candidato e plano de
backup continuam em `IMPLANTACAO_GERENCIADOR_HARPISERVER_BLOQUEIO_20261102.md`.

Backup remoto: não executado. Restauração isolada: não ensaiada. Nenhum serviço
remoto foi reiniciado; nenhum banco operacional foi restaurado ou modificado.
Após desbloqueio, comparar antes de escrever, preparar snapshot consistente do
PostgreSQL/registry e diretório de apresentação, ensaiar recuperação isolada e
só então implantar o conjunto mínimo autorizado, preservando adaptações da VM.

Testes locais: mantida a evidência já aprovada em
`VALIDACAO_APLICADOR_APRESENTACAO_20261101.md`; nenhuma suíte repetida.
Testes reais de autenticação, telemetria, assistente, proposta/validação,
nome/fuso, consumo, revisão/auditoria e timestamps: **pendentes**. Correspondência
do frontend aberto com artefato implantado: pendente; portal local em 4174 não
constitui prova de implantação. `operational=false` continua obrigatório.

## Coordenação Edge

Edge consultada via Maestri; leituras atuais já reunidas por ela em
`p08_captura/WINDOWS_NETWORK_READONLY_2026-11-02.json` e
`p08_captura/RETOMADA_ROTAS_2026-11-02.md` no worktree
`harpisense-worktrees/p08-evidence-coverage` (caminhos localizados; entrega da Edge).
Permanecem necessários: leituras Poste 2 e broker efetivo; rota Windows de retorno
após obter IP real; delta HarpiServer e hash/stat do integrador; configuração
sanitizada ESP32/AP/intermediário; fontes, retenção, sincronismo e cursores.

Leitura complementar Windows em 02/11 às 18:43 UTC: VMnet1 ifIndex12
192.168.180.1, VMnet8 ifIndex17 192.168.155.1, Ethernet ifIndex20
192.168.1.5. w32tm reportou não sincronizado, fonte Local CMOS Clock; não tratar
o relógio Windows como referência UTC sincronizada. Mosquitto foi observado
Stopped às 17:17 UTC; consulta 1883 não retornou entradas. Não concluir percurso
fim a fim desses dados. Nenhuma captura, mudança de rede ou ativação foi feita.
Edge permanece responsável pela proposta de captura/contenção.
