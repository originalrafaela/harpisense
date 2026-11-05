# Integração frontend: primeiro acesso e MFA candidato

Branch `feat/frontend-auth-defense-v2`, iniciada sobre a entrega `d172a387`. A implementação foi conferida com `feat/admin-bootstrap-mfa` em `737ae26a098588f2c2bbdb953bee1514b1a1fb95`. SHA-256 do OpenAPI consumido: `8a135dc91ed0f027f3013e666c3e7eae813a82245eef7d6bd67ac00ac9b65c62` (confere com `docs/ADMIN_MFA_HTTP_RESULTADO.json`). O Arquiteto revisou essa candidata; a factory é opt-in e isso não declara ativação operacional.

## Rotas usadas

| Fluxo | Rota | Autorização | Resultado usado pelo frontend |
|---|---|---|---|
| Login administrativo | `POST /api/v1/admin-auth/login` | Corpo de usuário e senha | Sessão direta para conta legada, ou challenge `login`/`enroll`; challenge não é sessão. |
| Primeiro provisionamento | `POST /api/v1/admin-auth/bootstrap` | Grant local, usuário e senha | Somente challenge `enroll`. |
| Recuperação local autorizada | `POST /api/v1/admin-auth/local-recovery` | Grant `recover`, usuário e senha existentes | Somente challenge `enroll`; não redefine senha nem cria sessão. |
| Autorizar adesão/substituição | `POST /api/v1/admin-auth/mfa/enrollment/authorize` | Bearer da sessão existente, senha atual e TOTP quando ativo | Challenge `enroll`; a sessão existente segue ativa até a confirmação. |
| Emitir QR e chave manual | `POST /api/v1/admin-auth/mfa/enrollment/begin` | Challenge `enroll` no corpo | QR SVG, chave manual e validade. SVG é reconstruído em elementos vetoriais permitidos; URI `otpauth` não é navegada nem exibida. |
| Confirmar autenticador | `POST /api/v1/admin-auth/mfa/enrollment/confirm` | Challenge `enroll` e TOTP | Sessão MFA e dez códigos de recuperação, mostrados uma vez. |
| Login de segundo fator | `POST /api/v1/admin-auth/mfa/verify` | Challenge `login` e TOTP | Só após resposta de sessão e validação de `GET /session` libera o painel. |
| Recuperação por código | `POST /api/v1/admin-auth/mfa/recover` | Challenge `login` e código de recuperação | Somente challenge `enroll`; nunca emite sessão administrativa. |
| Cancelar challenge | `POST /api/v1/admin-auth/mfa/cancel` | Challenge no corpo | `204`; os campos temporários são limpos da interface. |
| Consultar/encerrar sessão | `GET` e `POST /session`, `/logout` | Bearer após emissão de sessão | Formato legado e campos MFA do candidato são validados separadamente. |

O cliente mantém challenge, senha, grant, chave TOTP, QR e códigos de recuperação somente em memória. O URI `otpauth`, que contém o segredo TOTP, é validado e descartado pelo cliente; não permanece em estado React. Nenhum desses valores é escrito em `localStorage`, `sessionStorage`, URL ou log. Os códigos de recuperação exigem confirmação visual de que o administrador os guardou fora do navegador. Recuperação por e-mail não é oferecida. A prévia visual não chama essas rotas.

## Propriedade e entrada do instalador

`src/account-mfa.tsx` expõe `AdminAccess({client,onAuthenticated})` para a tela de acesso/primeiro provisionamento e `AccountSecurityPanel({client})` para adesão de uma conta existente em Configurações. O frontend mantém a tela e o cliente; o Gerenciador de Configurações permanece responsável por orquestrar a abertura do assistente depois da instalação. Nenhum arquivo do assistente/orquestrador foi alterado nesta candidata.

Primeiro provisionamento não é inferido de `localStorage`. A tela pede o grant local e a API decide se o singleton ainda pode ser criado. A tela de Configurações só oferece adesão existente quando a sessão consultada informa `mfa_enrollment_available=true`.

## Transporte e teste HTTP

O navegador de desenvolvimento usa `http://127.0.0.1:5174`; `vite.config.ts` fixa `host=127.0.0.1`, `strictPort=true`, sem CORS aberto. O cliente usa `/p11-api`; o proxy de desenvolvimento só permite os métodos e caminhos MFA exatos, encaminha ao loopback configurado em `HARPI_API_TUNNEL_TARGET`, rejeita Basic e remove cookies. O candidato deve permitir a origem exata `http://127.0.0.1:5174`; no preview Vite a origem é `http://127.0.0.1:4174`.

Os testes do frontend com `route.fulfill` e `fetch` stub são fixtures isoladas de UI/contrato. Backend Data registrou 258 verificações aprovadas na composição HTTP isolada via Uvicorn/TCP e `mfa_http_fixture`; esse resultado pertence à validação do backend, não é um teste do navegador frontend. Nesta execução não havia listener loopback ativo nem URL/porta publicada para o frontend, então o fluxo do navegador conectado ainda não foi comprovado. Nenhuma dessas evidências atesta integração com VM ou ativação do candidato no backend operacional.

## Pendências de aprovação/composição

- Factory opt-in de MFA na composição de API de teste e produção; backend compartilhado não foi alterado pelo frontend. A revisão do commit candidato `737ae26` e a correspondência do OpenAPI foram confirmadas pelo Arquiteto.
- Teste de navegador conectado ao servidor TCP isolado com origem `http://127.0.0.1:5174` e grant inserido localmente pelo operador. Nenhum segredo deve entrar em fixture commitada ou relatório. Falta URL/porta loopback ativa e o procedimento privado de obtenção do grant para esta execução.
- Entrada do primeiro assistente coordenada com o Gerenciador de Configurações, sem duplicar sua orquestração.

## Evidências desta entrega

- Frontend: `npm.cmd run typecheck`, `npm.cmd run build`, `npm.cmd test` (46/46) e `npx.cmd playwright test` (54 aprovados, 1 teste de composição local ignorado; todos usam fixtures/mocks isolados). `git diff --check` limpo.
- Navegador: fluxo de primeiro cadastro, TOTP, apresentação dos códigos, login MFA, fator inválido, expiração, recuperação e adesão de conta existente passaram por `route.fulfill`; esses resultados não são HTTP conectado.
- Backend: o recibo em `docs/ADMIN_MFA_HTTP_RESULTADO.json` declara 258 verificações aprovadas, transporte Uvicorn/TCP loopback e banco `mfa_http_fixture`, com `operational_deployment=false`. Hash OpenAPI conferido acima. Não foi possível executar o navegador contra essa composição nesta worktree porque nenhum listener loopback estava ativo e o recibo não publica URL/porta nem procedimento de grant privado.
- Capturas Playwright existentes de login, dashboard e aprovações foram atualizadas em `docs/evidence/`; não contêm credenciais ou códigos de teste.
