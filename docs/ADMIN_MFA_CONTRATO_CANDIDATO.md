# Primeiro acesso e MFA administrativo — candidata

Status: **proposta implementada e testável, ainda não é contrato de integração aprovado**.
Base: `9d35906`; branch `feat/admin-bootstrap-mfa`. Não altera bootstrap compartilhado,
P11, gerenciador, PostgreSQL operacional, ingestão técnica ou RF/IF/Risk/Policy.

Referência mais recente: `referencias/versão_v2/11_Backend_Dashboard_BitNet/`
`HarpiSense_Pacote11_Backend_Dashboard_BitNet_v2/AUTENTICACAO_E_OPERACOES_ADMINISTRATIVAS.md`.
Esse pacote mantém Basic como referência local e exige sessão/TLS antes da implantação.
A candidata reutiliza a entrega posterior de autenticação/sessões de `9d35906`.
Componentes de `Versões corretas` continuam válidos quando não substituídos na v2;
nenhum motor é considerado ausente nem recomposto nesta entrega.

## Regras comuns

Prefixo: `/api/v1/admin-auth`. JSON, HTTPS, origem frontend exata aprovada pelo
instalador; HTTP permitido só no loopback pelo instalador de rotas existente.
Todas as respostas de autenticação têm `Cache-Control: no-store`.
Não registrar corpos, cabeçalhos Authorization, respostas, QR ou chaves em proxy,
APM, analytics ou console. Nunca incluir bootstrap, desafios ou tokens em URLs.
Não persistir segredo/challenge/QR/códigos no localStorage, histórico ou telemetria.
O `provisioning_uri` é exclusivamente um URI **otpauth** para o autenticador,
entregue no corpo autorizado; não é URL da API ou link de bootstrap.

Erros: `{"error":{"code":"..."}}`; sem eco do valor submetido. 401 credencial,
fator, grant ou desafio inválido; 403 reautenticação/origem; 409 estado incompatível;
422 contrato inválido; 429 `TRY_LATER` e `Retry-After`; 503 indisponibilidade.
Limite do corpo: 4096 bytes. Campos desconhecidos são rejeitados.

Há dois tipos de resposta. O frontend deve distinguir pelas propriedades,
sem tratar HTTP 200 ou um desafio como autenticação administrativa:

* Desafio: `{challenge_token, next_step: "login"|"enroll", expires_at}`.
  Aleatório, hash no banco, validade de 5 minutos, vinculado à revisão da senha.
  Não funciona como Bearer administrativo. Até 5 operações de validação por desafio
  (inclusive início do cadastro); depois precisa obter novo desafio autenticado.
* Sessão: `{access_token, token_type: "Bearer", expires_at,
  idle_timeout_seconds: 1800, username}`. Reutiliza a tabela e o formato existentes,
  validade absoluta de 8 horas. Apenas esse token vai em `Authorization: Bearer`.

## Endpoints candidatos

| Método e caminho | Corpo / autorização | Resultado |
| --- | --- | --- |
| POST `/bootstrap` | `{bootstrap_secret, username, password}` | Desafio `enroll`. Cria a única conta pendente, consome grant local. Nenhuma sessão. |
| POST `/login` | `{username, password}` (existente) | MFA ativo: desafio `login`; nova conta pendente: `enroll`; conta legada ainda não aderida: sessão existente. |
| POST `/mfa/enrollment/authorize` | Bearer de sessão + `{current_password, code?}` | Desafio `enroll`. Conta legada: senha; substituição com MFA ativo: senha **e TOTP atual ainda não usado**. |
| POST `/mfa/enrollment/begin` | `{challenge_token}` com propósito `enroll` | `{manual_key, provisioning_uri, qr_svg, expires_at}`; apenas uma exibição por desafio. Ainda não ativa MFA. |
| POST `/mfa/enrollment/confirm` | `{challenge_token, code}` TOTP | Ativa/substitui MFA, consome todos os desafios, revoga todas as sessões anteriores e devolve sessão MFA + `recovery_codes: string[10]`. |
| POST `/mfa/verify` | `{challenge_token, code}` com propósito `login` | TOTP válido e não usado: sessão MFA; consome desafio. |
| POST `/mfa/recover` | `{challenge_token, code}` com propósito `login` | Consome código de recuperação, revoga sessões/desafios e devolve **somente** novo desafio `enroll`. |
| POST `/mfa/cancel` | `{challenge_token}` | 204; invalida desafio, sem afetar um MFA já ativo. |
| POST `/local-recovery` | `{bootstrap_secret, username, password}` | Grant local com propósito `recover` + senha válida: revoga sessões e devolve somente `enroll`. Não cria conta nem altera senha. |
| GET `/session` | Bearer (existente) | Acrescenta `mfa_available: true`, `mfa_enabled`, `mfa_enrollment_available: true`; sem segredo. |
| POST `/logout` | Bearer (existente) | 204; revoga sessão atual. Limpar também estado temporário no frontend. |
| PUT `/password`, PUT `/username` | Contrato existente, sessão completa + senha atual | Mantém revogação de todas as sessões e incremento de revisão; desafios antigos tornam-se inválidos. |

Para as duas alterações existentes, corpos continuam respectivamente
`{current_password, new_password}` e `{current_password, new_username}`.
A senha mantém scrypt e critérios existentes (8–128 caracteres, máximo 512 bytes).
O nome mantém `[A-Za-z0-9_.@-]{3,64}`. Credenciais técnicas fornecidas ao módulo
(API, MQTT, agentes) e a senha PostgreSQL são rejeitadas para uso humano.

## Fluxo frontend

Instalação nova: formulário protegido pelo segredo local → `/bootstrap` →
`/mfa/enrollment/begin` → exibir QR e chave manual → pedir TOTP →
`/mfa/enrollment/confirm` → mostrar os dez códigos **uma vez**, permitir salvamento
local consciente pelo administrador → concluir acesso administrativo com a sessão
retornada. Não mostrar QR nem chave em tela pública ou quando não autorizado.
Se perder a resposta contendo QR, cancelar e obter novo desafio via `/login`.
Se perder a resposta da confirmação, fazer login por TOTP e substituir o cadastro
com reautenticação para obter novo conjunto; códigos antigos são invalidados.

Login MFA: `/login` → `/mfa/verify` → sessão. Um código de 6 dígitos vale apenas
para o passo atual de 30 segundos; sem tolerância a passos vizinhos. Após usar um
código (inclusive confirmação do cadastro ou autorização de substituição), aguardar
o próximo código para nova validação do mesmo autenticador. Relógio do PostgreSQL
é a autoridade; instalador deve verificar sincronização NTP e UTC.

Autenticador perdido: senha → desafio de login → código de recuperação em
`/mfa/recover` → cadastro e confirmação de novo TOTP. Nenhum código de recuperação
gera acesso administrativo direto. Novo conjunto substitui integralmente o anterior.
Não há endpoint de desativação de MFA: a política candidata permite substituição
autenticada e recuperação controlada, sem retorno permanente a senha apenas.

Conta existente: implantação não modifica conta, hash, revisão ou sessões.
`/session` e a sessão legada de `/login` sinalizam disponibilidade de adesão.
Após senha atual em `/mfa/enrollment/authorize`, segue o cadastro. Até a confirmação,
acesso existente e autenticador anterior continuam válidos. Somente a confirmação
ativa obrigatoriedade de MFA e revoga sessões prévias. Essa transição é atômica e
auditada; não existe flag global que bloqueie o administrador antes da adesão.

## Segurança e auditoria

Migração `002_admin_mfa.sql` acrescenta tabelas independentes e um booleano de
garantia MFA às sessões existentes; não migra dados humanos automaticamente.
O bloqueio singleton `hs_admin_throttle` existente serializa bootstrap, desafios,
confirmações, consumo de códigos e emissão/revogação de sessões. Dois cadastros
concorrentes não podem criar duas contas ou consumir o mesmo segredo duas vezes.
Falhas de autenticação são persistidas mesmo quando a operação é rejeitada.
Após 5 falhas o limitador global aplica espera exponencial (2–60 segundos), comum
a usernames, grants e desafios; até 5 tentativas por desafio. Login de primeiro
fator com MFA não reinicia esse contador: só validação completa o reinicia.

TOTP via PyOTP 2.9.0; segredo cifrado por Fernet/cryptography 50.0.2, QR via qrcode
8.2. A chave Fernet pertence ao instalador, separada do banco. Código confirmado
consome seu passo temporal (`last_step`) sob o mesmo bloqueio; aceitar novamente o
mesmo passo é proibido, inclusive em desafios concorrentes. Códigos de recuperação:
10 valores de 192 bits aleatórios, somente SHA-256 no banco e uso único transacional.
Grants e tokens também só têm hashes persistidos. Recuperação e confirmação de MFA
invalidam grants locais pendentes além das sessões e desafios anteriores.
Auditoria existente registra
evento, resultado fixo e id estável; nunca senha, nome submetido, chave, código ou token.

Documentação oficial consultada em 2026-11-04:
[PyOTP](https://pyauth.github.io/pyotp/) (provisionamento, throttling e rejeição de
replay), [Fernet](https://cryptography.io/en/stable/fernet/) (cifragem autenticada e
custódia da chave), [qrcode](https://pypi.org/project/qrcode/8.2/) (SVG local).

## Aprovação de integração

O arquiteto ainda deve aprovar este contrato, o transporte frontend, o armazenamento
local do grant/chave, o procedimento operacional e a composição real de instalação.
Nenhuma URL local ativa ou implantação na VM é declarada por este documento.
O OpenAPI da candidata registra as rotas e entradas ao chamar
`install_candidate_admin_auth`; este Markdown também especifica as respostas e estados.
