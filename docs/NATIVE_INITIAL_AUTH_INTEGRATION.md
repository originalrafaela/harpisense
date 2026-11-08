# Integração nativa de autenticação inicial

Worktree `native-initial-auth`, branch `feat/native-initial-auth`: origem 9cd930c,
composta com 2345808, preservando domínio científico, migrações e fontes originais.
Ativador Edge 5d87e6f incorporado como 66454d6. Nenhum frontend é alterado aqui.

## Composição

`packaging/native/entry.py api` abre `NativeActivationRuntime`, injeta `adapter`
e os bytes da chave MFA em `build_native_app(initial_access=..., protection_key=...)`.
`backend/native_server/runtime.py` repassa ao instalador HTTP do Backend.
O selo `NativeTransport` existe somente no listener exclusivo 127.0.0.1, com
porta derivada de panel_url, `proxy_headers=False` e access log desabilitado.
Não montar esse wrapper em listener de rede ou atrás de proxy.

A primeira tentativa de ativação ocorre sob a identidade API, antes do IPC.
Somente connection_required/ISSUER_UNAVAILABLE permitem continuar com identidade
pendente. IPC autoriza retry; cadastro exige recibo validado e posse da chave.
Named pipe verifica SID nas duas pontas. Ubuntu verifica SO_PEERCRED, socket0600
e diretório0700 em `/run/harpisense-api`, gerido por RuntimeDirectory systemd,
sem preservar endpoint no estado persistente após restart.

Windows usa conta virtual NT SERVICE/HarpiSenseApi, diretório privado API/SYSTEM
e DPAPI CurrentUser criado pelo próprio serviço. PostgreSQL/MQTT permanecem fora
desse ACL. Ubuntu usa harpisense-api separado da conta harpisense do PostgreSQL;
somente API recebe LoadCredentialEncrypted, chave32 via stdin a systemd-creds.
Launcher Ubuntu adquire handoff como root, faz fork, initgroups/setgid/setuid
para usuário gráfico e só então lança Chromium. Cookie permanece em memória.
Nenhum token em argv, URL, stdout ou campo grant. Playwright e Chromium são offline.

## Atualização e MFA existente

Sem configuração de ativação/diretório novo, conta existente usa a chave original
e status migration_required; login não passa a exigir licença. A proteção de chave
legada usa os MESMOS bytes Fernet, verifica correspondência e preserva secret_cipher.
Não substituir chave por geração nova quando já existe conta. O arquivo legado
não é apagado automaticamente na migração: proteção fora do banco permanece
limitada pelo ACL/plaintext legado até política explícita de migração/remoção.
Instaladores de instalação nova removem somente a chave provisória sem conta/cifra
persistida e deixam o serviço gerar sua primeira chave protegida.

## Distribuição personalizada e assinatura

1. Emissor registra licença transacionalmente e entrega a chave de ativação ao
   pipeline autorizado. Chave privada Ed25519 do emissor permanece SOMENTE no
   emissor; não é entrada do build nem conteúdo de qualquer pacote.
2. Distribuidor fornece URL HTTPS REAL, anel de chaves PÚBLICAS Ed25519 e licença
   de entrega em arquivo privado. Nenhum domínio/trust fixture é fallback do produto.
3. Montar cada cópia Windows/Ubuntu com configuração pública, chave de ativação
   dessa entrega, Chromium correspondente ao Playwright fixado e dependências
   completas. Assinar o artefato FINAL personalizado de cada plataforma.
4. Verificar assinatura e publicar hash do artefato já assinado. Nunca personalizar
   arquivo previamente assinado nem usar áreas excluídas de Authenticode.

Certificado/chave de code signing são separados das chaves do protocolo emissor.
O instalador move a chave de ativação da entrega para estado privado; não a copia
para a árvore pública do aplicativo. O pacote não contém identidade de instalação,
receipt, banco ou chave MFA de outra máquina. Cópias personalizadas diferentes
exigem assinatura final própria. O build ainda não assina automaticamente: o
pipeline de assinatura/verificação do distribuidor é dependência de implantação.

Ambos builders exigem `--activation-config`, `--activation-key-file`,
`--chromium-dir`. Ubuntu também exige `--ubuntu-debs-dir` com fechamento completo
das dependências Ubuntu24.04 e bibliotecas Chromium; instalação usa dpkg e wheels
locais, sem download em runtime. URL real, trust bundle real, certificado de
distribuição e repositório de .deb ainda precisam ser fornecidos pelo distribuidor.

## Verificação e limites

Cinco testes `test_native_activation.py` passam em Windows existente com DPAPI real: restart de conta existente sem
configuração do emissor, porta28081 e reproteção DPAPI preservando chave/cifra MFA.
Também cobrem reabertura ready/migration_required sem IPC/cookie e aquisição IPC
somente para absent/mfa_pending. Onze testes Edge passaram antes do complemento
de lifecycle. Emissor e presença de conta nesses testes são
fixtures explícitas; não representam aceite de servidor PostgreSQL em produção.

Os scripts acceptance_product, acceptance_windows e check_model_mount usam
`acceptance_first_use.py`: receipt Ed25519 de emissor fixture, DPAPI real, listener
real e cookie obtido por named pipe autenticado. Não há callback permissivo nem
grant manual. O helper de fixture NÃO é copiado para os pacotes de produto.
O modo frozen desses scripts antigos é recusado explicitamente: aceite frozen
precisa do launcher/IPC da instalação real e não pode ser confundido com fixture.

Aceite completo HTTP/browser com Backend/frontend integrados, serviço Windows
virtual/ACL em máquina limpa, launcher gráfico Ubuntu/polkit, systemd credentials,
crash/reboot e fechamento offline dos .deb/Chromium permanecem pendentes. Não houve
alteração de serviços existentes ou execução de instalador nesta estação.

Ensaio dirigido `acceptance_initial_auth.py` iniciado na estação Windows existente
com PostgreSQL nativo, frontend dist da integração e receipt fixture assinado.
Confirmou migrações idempotentes/ausência de grant e bootstrap403 sem cookie IPC.
Terminou com `failure_type=error` antes de concluir handoff/browser; nenhum aceite
fim a fim foi obtido. Evidência sanitizada em
`docs/evidence/native-initial-auth/result.json`. Reexecutar pelo terminal principal
na branch integrada; não tratar os cinco testes unitários como aceite de máquina limpa.

Startup mantém API disponível em LICENSE_ALREADY_ACTIVATED e falhas transitórias.
Retry traduz ActivationError para AuthError: conflito409 e rede/emissor503, com
código estável e sem imprimir exceção bruta. A UI consome o código de conflito e
apresenta `Esta licença já foi ativada em outra instalação.`

## Fechamento pela integração principal

A branch integration/initial-auth-20261108 corrigiu a chamada de impersonação para win32security.ImpersonateNamedPipeClient e o shutdown do pipe. O novo ensaio acceptance_initial_auth.py passou com PG/HTTP/Chromium/IPC reais, cadastro/TOTP/três códigos e login após restart dos processos nos estados ready e migration_required. O recibo desse ensaio é fixture explícita; a ativação HTTPS real está coberta separadamente pela suíte22. Não foi feito reboot do SO ou instalação limpa. A evidência result.json agora registra a execução aprovada.

A integração repetiu17 testes Windows de ativação/IPC (5 Linux ignorados),5 de compatibilidade e o autocheck de criação/verificação Argon2id. Relatório consolidado: docs/INITIAL_AUTH_INTEGRATION_REPORT_20261108.md.
