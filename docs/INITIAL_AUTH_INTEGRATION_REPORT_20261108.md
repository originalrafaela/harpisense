# Autenticação inicial — integração e cobertura

Registro de trabalho em 08/11/2026. Este documento distingue implementação, ensaios de desenvolvimento e homologação do artefato instalado. Não houve implantação no gateway operacional nem alteração de VPN/MQTT/firewall de produção.

## Branch e preservação

- Integração: `integration/initial-auth-20261108`, worktree `harpisense-worktrees/initial-auth-integration`, base `234580888466cf82c458ae8ec678dc5f3fa1b447`.
- Contrato publicado: `fadebd9bb487390f1b058b446b852c53fbbc9f31`, `docs/INITIAL_AUTH_CONTRACT_V1.md`. Define produtores/consumidores, endpoints, conteúdo assinado, TTL, erros, retomada, sessão local e migração.
- Frontend anterior incorporado de `d2d53b5` em `f0f3e39`; implementação nova em `c349fb5` e ajustes subsequentes desta branch.
- Ativador: `feat/local-activation`, fonte `5d87e6f`, integrado como `9f1c5d4`.
- Backend humano: `feat/issuer-local-auth`, fonte `cb6545b`, integrado como `18e8a3f`.
- Emissor, migração repetível, fechamento da composição antiga e testes: fonte `ff2d43f`, integrado como `1598ed4`.
- Lifecycle IPC/navegador: fonte `9464d4f`, integrado como `610c32d`.
- Dependências nativas: `feat/native-initial-auth`, fonte `bf23098`, integrado como `d13a8ee`, preservando módulos científicos/action_review na resolução dos conflitos.
- `integration/primeira-entrega` histórica contém alterações locais e não foi sobrescrita. Fontes backend/frontend/native anteriores preservadas. A worktree `frontend-auth-label` e suas seis alterações locais do usuário não foram editadas ou commitadas.

## Arquivos e comportamento

| Área | Principais caminhos | Comportamento |
|---|---|---|
| Contratos/inspeção | docs/INITIAL_AUTH_CONTRACT_V1.md, INITIAL_AUTH_INSPECTION_20261108.md | Responsabilidades e protocolo publicado antes das integrações |
| Ativação | backend/local_activation/{client,envelopes,identity,protection,initial_access,ipc,transport}.py | HTTPS, Ed25519, identidade protegida, recibo offline, primeiro uso por IPC e cookie |
| Autenticação | backend/admin_auth/{candidate,mfa,first_access,passwords,api,http_contract}.py | Argon2id, senha+TOTP, cadastro pendente, três verificadores e recuperação transacional |
| Interface | frontend/src/{account-mfa,initial-access,first-access-welcome,password-recovery,main}.tsx e api.ts | Sem campo grant, abertura inicial autorizada, QR seguro, pop-up dentro do dashboard, cópia e confirmação |
| Transporte frontend | frontend/scripts/p11-proxy.mjs | Rotas v2 permitidas, Basic/ingestão técnica fora do transporte administrativo, cookie somente nas chamadas iniciais de mesma origem |
| Dependências | backend/admin_auth/requirements-passwords.txt; packaging/native/requirements-activation.txt, requirements.txt e locks | Argon2id e bindings incluídos no caminho de empacotamento Windows/Ubuntu |

Os originais dos códigos existem somente na resposta de emissão e na memória da interface. A primeira emissão é POST com corpo vazio; reload/segunda aba não releem os originais nem provocam reemissão automática. Reemissão exige senha e TOTP; confirmação envia a geração corrente. Códigos não autorizam recadastro do MFA. Perda do autenticador: política ainda não aprovada, rotas correspondentes recusadas.

## Migrações e atualização

- Administrador: `backend/admin_auth/005_initial_auth_v2.sql`, após 001–004. Acrescenta vínculo instalação/licença, segredo de adesão pendente cifrado e tabelas `hs_admin_recovery_set_v2`/`hs_admin_recovery_v2`.
- Registro emissor e sua migração pertencem à implantação do distribuidor, separados do banco local e do instalador do usuário.
- Migração do emissor: `backend/license_issuer/001_issuer.sql`, com UNIQUE global do hash e registro retido depois da ativação. Executável de serviço HTTPS em `backend/license_issuer/__main__.py`; configuração privada externa ao pacote.
- Conta existente conserva senha e segredo MFA. Hash scrypt é verificável para transição para Argon2id. Ausência de recibo em uma conta anterior não autoriza novo cadastro e não deve impedir seu login: estado `migration_required`.
- Listas antigas 10+10 não são aceitas para desativar MFA; emissão v2 revoga os conjuntos antigos, preservando trilha histórica. O novo conjunto exige sessão humana com MFA.

## Verificações já executadas na integração

| Comando / ensaio | Resultado | Limite |
|---|---|---|
| frontend: npm test | 76 aprovados | Unidade/contratos e proxy local com fixtures |
| frontend: npm run build | Passou, 55 módulos | Inclui typecheck; não é pacote instalado |
| Playwright tests/initial-auth.playwright.config.ts | 11 aprovados | Navegador Chromium com HTTP interceptado, sem serviço/banco operacional |
| unittest backend/local_activation_tests | 11 aprovados no Windows | DPAPI real; emissor fixture; sem instalador/VM limpa |
| Backend: run_native_postgres.py --edge-backend backend | **22 aprovados na própria branch integrada**, 26,60 s | PG18 nativo descartável, HTTPS real com CA de teste e DPAPI; não instalação limpa |

Playwright cobre: ativação sem conexão, mensagem exata de licença já ativada, conta existente, cadastro/QR/primeiro TOTP, dashboard com três códigos, clipboard, ausência de códigos em local/sessionStorage, reload real com novo login e conjunto pendente, resposta perdida, conflito de emissão, confirmação e recuperação com TOTP. Não houve screenshots, vídeos ou traces de segredos. Os materiais dos testes são sintéticos.

Os 22 testes integrados incluem disputa de locks observada no PostgreSQL, emissão/colisão, ativação de duas máquinas, TLS real emissor→ativador, prova de posse e DPAPI, perda da resposta, cópia somente do receipt, validação offline, cadastro interrompido, concorrência de códigos/reset, replay TOTP, migração legada repetível e rollback tardio. Houve três avisos de depreciação de dependências; nenhuma falha. O runner encerrou o cluster descartável. Resumo sanitizado: `docs/evidence/initial-auth-integration/summary.json`.

Complemento Edge informado pelo produtor e revisado no código: Windows 14 aprovados/5 Linux ignorados; Debian WSL 5 testes reais de crash/socket stale aprovados. Debian WSL não equivale a Ubuntu instalado nem prova lifecycle systemd ou reboot. Os três testes de fechamento do browser usam driver fixture.

Falhas encontradas e corrigidas na interface: label acessível da senha incluía o botão Mostrar; normalização CRLF do clipboard Windows no teste; fixtures antigas não representavam MFA obrigatório/first_access v2. A primeira rodada falhou nesses pontos, a rodada atual passou.

## Revisões de integração

Foram identificados e encaminhados para correção: preservar a chave que cifra o MFA existente; separar login comum de autorização para primeiro cadastro no launcher; parametrizar porta nativa pelo panel_url; evitar socket Unix stale bloquear a API após crash/reboot; fechar a composição antiga que permitia sessão humana sem MFA. Os commits/testes finais dessas correções devem constar no fechamento.

## Windows versus Ubuntu

| Critério | Windows | Ubuntu |
|---|---|---|
| Interface e protocolo em desenvolvimento | Validado nas suítes acima | Mesmo frontend; não equivale a execução Ubuntu |
| Chave protegida por mecanismo real | DPAPI CurrentUser exercitado em desenvolvimento | Systemd credential implementada; aceite Ubuntu pendente |
| Argon2id em máquina limpa, sem downloads | Não comprovado | Não comprovado |
| Instalador completo sem checkout/Docker | Não comprovado nesta rodada | Não comprovado nesta rodada |
| Instalador → serviço → operação → dashboard | Ainda sem aceite do artefato final | Ainda sem aceite do artefato final |
| Persistência/login offline após reboot do SO instalado | Não comprovado | Não comprovado |

DPAPI/credencial systemd protegem contra acesso fora da identidade autorizada, dentro dos limites documentados. Não há TPM/vTPM; clone integral VMware pode carregar a identidade e seu material de proteção. Cópia somente do recibo não é suficiente.

## Dependências de distribuição

O distribuidor deve provisionar seu emissor HTTPS, registro compartilhado e chave privada fora dos instaladores. A construção de cada cópia recebe licença emitida, URL real e anel público confiável. Personalizar ANTES da assinatura final do artefato; não modificar arquivo já assinado. Certificado de assinatura do instalador e chave Ed25519 do emissor são distintos. Não foram inventados domínio, certificado ou licença de produção.

## Fechamento

Integração dos commits complementares, repetição das suítes finais e cobertura do runtime nativo serão acrescentadas neste documento. Até então, este registro não declara o fluxo homologado em máquina limpa.
