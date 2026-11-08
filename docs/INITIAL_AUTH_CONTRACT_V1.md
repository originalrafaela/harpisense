# Autenticação inicial — contrato v1 (08/11/2026)

Referência de integração: `integration/initial-auth-20261108`, criada de `2345808` (backend). Frontend fonte: `d2d53b5`; instaladores/ativador fonte: `9cd930c`. Não modificar as worktrees fonte. Contrato normativo entre as quatro frentes; qualquer mudança deve ser coordenada aqui antes da integração.

## Responsáveis

| Produtor | Entrega | Consumidor |
|---|---|---|
| Backend Data | Emissor HTTPS, registro PostgreSQL, assinaturas, auth humana, migrações e auditoria | Ativador, frontend |
| Edge Security | Ativador local, identidade protegida, validação offline, ponte de primeiro uso e revisão | Instalador, backend |
| Gerenciador de configurações | Pacotes Windows/Ubuntu, dependências offline, execução e atualização | Usuário/ativador/backend |
| Arquiteto | Este contrato, frontend real, composição e relatório integrado | Todas as frentes |

Gateway Basic, ingestão, tokens de serviço e MQTT não mudam para MFA. Nenhuma dessas identidades pode alcançar APIs administrativas. MFA obrigatório em toda nova sessão humana; sessão pré-MFA não é Bearer administrativo.

## Criptografia de ativação

Todos os bytes aleatórios: CSPRNG. Chave de ativação: 32 bytes, base64url sem padding (43 caracteres). Banco emissor: SHA256 da string ASCII, UNIQUE entre plataformas, registro nunca apagado após consumo. Colisão de emissão tenta outra chave antes de entregá-la. `license_id` e `installation_id`: UUID, distintos da chave. Emissor compartilha um registro transacional PostgreSQL para as duas plataformas.

Ed25519 para emissor e instalação. Chave pública raw32 em base64url sem padding; `key_id` = SHA256(raw32) hexadecimal minúsculo. Algoritmo fixo Ed25519, rejeitar outros, key_id desconhecido e payload malformado. Anel de chaves públicas do emissor embarcado/atualizado por pacote assinado; chave privada do emissor nunca distribuída.

Envelope assinado: `{version:1,key_id:string,payload:string,signature:string}`. `payload` é base64url sem padding dos bytes UTF-8 JSON do documento. Assinatura de `ASCII("HarpiSense/" + purpose + "/v1\n") || ASCII(payload)`, purpose `challenge`, `activation-proof`, `receipt` ou `first-use`. Verificar os bytes exatos recebidos antes de interpretar; nunca reserializar para verificar. Rejeitar chaves JSON duplicadas, campos desconhecidos, tipo incorreto, floats para épocas e tamanho >16 KiB. Assim não depende de canonicalização entre linguagens. Documentos do produtor usam JSON compacto com chaves ordenadas e ASCII, sem NaN.

Emissor público exclusivamente HTTPS com validação normal de certificado/hostname; URL confiável vem do pacote, nunca de campo livre do navegador. Não redirecionar nem desabilitar TLS.

`POST /api/v1/licenses/challenges`: `{activation_key,installation_id,installation_public_key,platform:"windows"|"ubuntu"}`. Resposta 200 envelope challenge assinado pelo emissor, payload `{version:1,challenge_id,nonce,license_id,installation_id,installation_key_id,platform,issued_at,expires_at}`. nonce=32 bytes base64url; épocas UTC inteiras; TTL=120s. Registro persistente com tentativa/consumo e vínculo exato ao hash da licença, chave e instalação. Limitar tentativas, erros sem eco de segredos.

`POST /api/v1/licenses/activate`: `{challenge:<envelope>,proof:<envelope>}`. proof assinado pela chave da instalação, payload `{version:1,challenge_id,nonce,license_id,installation_id,installation_key_id,platform}`. Emissor verifica desafio, TTL, assinatura e vínculo; lock da licença e consumo do desafio na mesma transação que grava vínculo. Uma licença não pode mudar de instalação/chave. Desafio já consumido não pode ser reutilizado; após resposta perdida obter novo desafio e provar a MESMA chave. Retornar o mesmo comprovante persistido para a mesma instalação/chave; diferente retorna 409 LICENSE_ALREADY_ACTIVATED, mensagem exata `Esta licença já foi ativada em outra instalação.`

Resposta 200: `{status:"activated",receipt:<envelope>}`. Receipt payload `{version:1,receipt_id,license_id,installation_id,installation_key_id,installation_public_key,platform,activated_at,issuer_key_id}`. Não expira e não exige consulta online posterior. Verificar issuer_key_id == envelope.key_id e thumbprint/public key. Guardar recibo e identidade protegida atomicamente; nunca marcar ativo só por resposta HTTP. Em cada partida, verificar recibo e assinatura local de nonce aleatório pela chave privada vinculada. Copiar apenas recibo falha por ausência de posse. Não alegar proteção contra clone integral de VM ou administrador/root sem mecanismo específico.

Erros: 400 INVALID_REQUEST; 401 INVALID_ACTIVATION_KEY/INVALID_PROOF; 409 LICENSE_ALREADY_ACTIVATED/CHALLENGE_CONSUMED; 410 CHALLENGE_EXPIRED; 429 RATE_LIMITED (+ Retry-After); 503 ISSUER_UNAVAILABLE. Envelope `{error:{code,message}}`, sem licença/nonce/proof no log. Timeouts/TLS/DNS ficam recuperáveis; preservar identidade para retomar.

## Ativador local e primeiro uso

Estado local persistido: `not_activated`, `activation_pending`, `activated`, `invalid_local_identity`; erro transitório `connection_required` não consome licença nem substitui chave. No estado ativo nenhuma indisponibilidade do emissor afeta login.

Frontend usa `/p11-api` no app nativo. `GET /api/v1/activation/status` retorna `{contract_version:1,status,administrator:"absent"|"mfa_pending"|"ready"|"migration_required",retry_allowed:boolean,first_use_authorized:boolean,loss_of_authenticator_policy:"not_approved"}`. Sem recibo jamais ready para cadastro. `POST /api/v1/activation/retry`, corpo `{}`, dispara ativador local sem receber licença no navegador; retorna status ou erro. Permitido apenas na sessão local iniciada pelo instalador, não via proxy de rede. Atualização do status nunca emite segredo.

Instalador entrega autorização por IPC autenticado local (Windows named pipe com ACL de usuário/serviço, Ubuntu Unix socket 0600 com credenciais de peer). Não há endpoint público para gerar autorização. Ativador faz prova de posse e valida receipt; backend recebe de componente confiável um verificador `initial_access` injetado na composição, nunca atestado enviado pelo browser.

Sessão de primeiro uso: aleatório256 bits, validade15min, hash persistido fora de URLs/logs; vinculada à instalação, ativação, usuário local e boot/service_instance_nonce. Abrir browser por lançamento local controlado que estabelece cookie HostOnly HttpOnly SameSite=Strict, Path=/p11-api/api/v1/ (ou caminho nativo equivalente), Secure sob HTTPS. Não passar segredo em query/fragment/argv. HTTP somente loopback com listener estrito; rejeitar Host/Origin estrangeiros e sem Origin em mutações de browser. Não confiar em X-Forwarded-For, Origin ou IP loopback isoladamente: proxy de rede não pode ganhar autorização. Handoff é implementado pelo ativador/instalador, não por UI digitando grant.

Backend verifica callback confiável em CADA bootstrap/retry/status privilegiado: transporte nativo local autorizado + cookie sessão válido + nonce serviço corrente + ativação verificada + conta ausente/pendente. Em qualquer falha, recusar 403 INITIAL_ACCESS_REQUIRED/ACTIVATION_REQUIRED. HTTP público não pode construir esse callback por header. Ao concluir MFA, invalidar todas sessões de primeiro uso. Restart antes da confirmação requer reabertura pelo instalador, reutiliza instalação/licença e conta pendente. Cadastro pronto nunca reabre.

Interface Python de composição acordada: `initial_access.status(request)->dict`, `initial_access.require(request)->dict` (retorna license_id/installation_id verificados ou lança AuthError), `initial_access.retry(request)->dict`; backend chama require antes de bootstrap. Edge entrega adaptador e Gerenciador injeta no runtime; ausência é fail-closed. Backend pode implementar adapter fixture apenas em testes, explicitamente identificado.

## API humana e interface

Prefixo `/api/v1/admin-auth`; JSON sem campos extras, no-store em tudo, nunca logar corpos/headers, senha, códigos, QR ou tokens. Manter rotas login/session/logout existentes. Cookies só para primeiro uso, Bearer em memória para sessão humana. Frontend fetch usa credentials=same-origin somente nas rotas iniciais, nunca envia autorização técnica.

| Rota | Entrada | Resposta | Produz → consome |
|---|---|---|---|
| POST /bootstrap | `{username,password}` + sessão local HttpOnly | challenge enroll | Backend → UI; require ativador |
| POST /login | `{username,password}` | challenge login ou enroll para conta pendente/migração | Backend → UI |
| POST /mfa/enrollment/begin | `{challenge_token}` | `{manual_key,provisioning_uri,qr_svg,expires_at}` | Backend → UI |
| POST /mfa/enrollment/confirm | `{challenge_token,code}` TOTP6 | Bearer administrativo, SEM códigos de recuperação | Backend → UI |
| POST /mfa/verify | `{challenge_token,code}` TOTP6 | Bearer administrativo | Backend → UI |
| GET /session | Bearer | sessão + first_access | Backend → UI |
| GET /first-access | Bearer | first_access | Backend → UI |
| POST /first-access/codes | Bearer + `{}` | primeira emissão ou 409 CODES_ALREADY_ISSUED | Backend → pop-up |
| POST /first-access/reissue | Bearer + `{current_password,code}` TOTP6 | novo conjunto3 e nova generation | Backend → pop-up |
| POST /first-access/confirm | Bearer + `{generation:int>=1}` | first_access completed | Backend → pop-up |
| POST /password-reset/confirm | `{username,code,totp_code,new_password}` | `{status:"password_reset",login_required:true,mfa_preserved:true}` sem Bearer | Backend → UI |

challenge = `{challenge_token:<random256 base64url43>,next_step:"enroll"|"login",expires_at:<RFC3339>}`. TTL300s, tentativas limitadas, hash no banco, revogado/consumido em transação. Login não devolve Bearer antes do TOTP. Enrollment begin deve reutilizar segredo pending cifrado em desafio retomável em vez de criar conta adicional; nunca sessão admin antes do primeiro TOTP. SVG tratado como imagem, não HTML executável.

Bearer result mantém `{access_token,token_type:"Bearer",username,expires_at,idle_timeout_seconds:1800}`. `/session` contém authenticated=true, mfa_available=true,mfa_enabled=true,email_recovery_available=false, e `first_access`. Não inferir completed pelo cadastro/MFA ou localStorage.

`first_access={contract_version:2,status:"not_issued"|"pending"|"completed",generation:int>=0,codes_remaining:int0..3,installation_id,account_id}`. Identificadores públicos não geram códigos. Primeira emissão somente ao montar pop-up DENTRO do dashboard. Lock de conta/conjunto + UNIQUE account/installation/generation/slot; exatamente3 códigos de24 bytes aleatórios base64url32, distintos; somente hash/verificador individual no DB, nunca originais cifrados para releitura. Resposta emissão: `{first_access,recovery_codes:[string,string,string]}`. Após commit o status é pending; repetição/duas abas responde409 CODES_ALREADY_ISSUED com first_access atual e SEM originais. Se resposta se perdeu, UI oferece reemissão explícita com senha+novo TOTP. Não repetir automaticamente POST após falha de rede. Reemissão revoga anterior atomicamente e incrementa generation; confirm antiga409 GENERATION_CONFLICT. Confirm exige pending + geração corrente; repetição da mesma confirmação é idempotente. Após completed não abrir boas-vindas em novos logins. Todos códigos servem SOMENTE recuperação de senha com TOTP, nunca recadastro de MFA.

Recuperação: lock conta/código e validação TOTP + Argon2id nova senha + consumir um código + revogar sessões na mesma transação; duas requisições não podem usar o mesmo código. TOTP aceito não pode ser reutilizado em nenhuma rota na mesma janela. Troca comum de senha mantém vínculos e códigos restantes. Auditoria com IDs públicos/resultado, sem segredos.

Senhas novas Argon2id; aceitar hashes scrypt existentes com verificação e rehash oportunista sem perder conta. Instalação existente sem comprovante não bloqueia login já funcional por exigir nova licença: estado migration_required, preservar login com senha e MFA; ativação obrigatória apenas para NOVO cadastro. Conta legada sem MFA: senha concede somente desafio de adesão, não APIs. Antigas listas10+10 não se convertem silenciosamente em3: conservar trilha, revogar somente mediante transição definida, exigir emissão/reemissão v2 com sessão MFA e comunicar migração. Rotas antigas de local-recovery/mfa/recover não permitem bypass/reset de MFA; 403 MFA_RECOVERY_POLICY_UNAVAILABLE até política aprovada.

## Aceite e fontes

Obrigatórios: colisão forçada/emissão concorrente; duas instalações; resposta perdida; challenge replay; cópia só receipt; cadastro interrompido; abas/reload/resposta perdida códigos; reset concorrente; ausência/replay MFA; Basic técnico sem poder admin; restart/login offline. Separar Windows/Ubuntu e fixture/dev de máquina limpa sem checkout/Docker/download.

Ed25519: https://www.rfc-editor.org/rfc/rfc8032.html ; Argon2id: https://argon2-cffi.readthedocs.io/en/stable/api.html . O envelope assina bytes exatos e não declara implementar JCS.
