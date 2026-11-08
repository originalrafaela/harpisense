# Homologação dos instaladores finais — verificação inicial

Solicitação: homologar Windows e Ubuntu limpos, incluindo criação/verificação Argon2id sem downloads adicionais e login depois de reboot do SO. Fonte exigida: integração `385b363` ou sucessora que preserve o fluxo completo. Política de perda do autenticador permanece pendente e não foi alterada.

## Resultado desta rodada

**Homologação não concedida. Execução dos instaladores finais aguarda os artefatos/configuração de distribuição corretos.** A checagem efetivamente executada reprovou os binários disponíveis para esse escopo; não se trata de uma falha de instalação ou de reboot já ensaiado.

| Verificação | Windows | Ubuntu |
|---|---|---|
| Arquivo encontrado | HarpiSense-Setup-Windows-x64.exe, 166.071.966 bytes | HarpiSense-Setup-Ubuntu-24.04-x86_64.run, 17.225.396 bytes |
| Procedência | Hash coincide com manifesto histórico candidate.5 | Metadata embarcada confirma candidate.5 / 8b9c9ef |
| Integração nova 385b363 | Não é o artefato dessa entrega | Não é o artefato dessa entrega |
| Assinatura | Authenticode NotSigned | Apenas .sha256 ao lado do .run; nenhuma assinatura destacada encontrada |
| Argon2id embarcado | Ainda não ensaiado nesse .exe antigo | Ausente na lista de wheels do arquivo inspecionado |
| Ativador/configuração novos | Não homologados nesse .exe antigo | backend/local_activation e native-activation.json ausentes |
| Instalação limpa, login e reboot | Não executados nesta rodada | Não executados nesta rodada |

A inspeção Ubuntu abriu o arquivo tar em memória, sem executar o instalador e sem extrair segredos. A presença de cffi sozinha não comprova Argon2id: não havia wheel argon2-cffi nem argon2-cffi-bindings. Os hashes SHA256 completos estão no [registro sanitizado](evidence/clean-os-qualification-20261108/preflight.json).

## Alvos disponíveis

VMware informa duas VMs de laboratório em execução. Nenhuma foi parada, reiniciada, clonada ou reconfigurada nesta rodada. As VMs de teste estão separadas.

- Windows: scaffold `.native-test/clean-os/windows11/HarpiSense-Clean.vmx` na worktree native-installers. O relatório histórico informa SO não instalado e o disco sparse segue com 8.454.144 bytes. Não foi declarado um Windows pronto só pela existência do VMX.
- Ubuntu: existe metadata do snapshot `clean-before-candidate2-20261106` na VM descartável Candidate2. A metadata foi lida; a limpeza e a identidade do guest ainda precisam ser verificadas em execução. Não houve revert nem mudança de snapshots. O ensaio deve usar um alvo separado e preservar os estados históricos.

## Insumos de distribuição necessários

Foi solicitada ao usuário a localização dos instaladores finais assinados e da configuração pública do emissor. Alternativamente, o build necessita dos insumos aprovados do distribuidor: URL HTTPS real, anel público do emissor, licença individual emitida para cada cópia, Chromium redistribuível correspondente à versão fixada e fechamento offline das dependências Ubuntu. A assinatura final é aplicada depois da personalização. Chaves privadas e licenças não devem ser enviadas pelo chat.

Não foi criada uma licença fictícia nem substituído o emissor por fixture para declarar um pacote final homologado. Os builders atuais exigem esses insumos; a integração de código, isoladamente, não cria os instaladores finais assinados.

## Percurso a comprovar com o artefato correto

1. Registrar hash, assinatura e identidade do build; preparar/confirmar SO limpo, sem checkout, Docker, Python de desenvolvimento ou bibliotecas do host.
2. Instalar somente o artefato completo. Permitir o acesso HTTPS necessário à primeira ativação, observando que não ocorram downloads de dependências.
3. Criar administrador, validar o primeiro TOTP e conferir no dashboard exatamente três códigos, sem capturar ou registrar os segredos.
4. Executar hash e verificação Argon2id com o runtime instalado, sem internet e sem bibliotecas externas, conferindo os bindings nativos.
5. Registrar boot_id/LastBootUpTime e estado persistido sanitizado; reiniciar o SO guest, comprovar outro boot e iniciar o produto pelos serviços/atalho instalados.
6. Com o emissor indisponível, efetuar login com senha e TOTP, conferir dashboard, primeiro acesso concluído e persistência dos vínculos. Separar esse reboot do simples restart de processo.

Cada plataforma terá evidência própria. Enquanto os insumos corretos não forem localizados, nenhuma etapa pendente é contabilizada como aprovada.
