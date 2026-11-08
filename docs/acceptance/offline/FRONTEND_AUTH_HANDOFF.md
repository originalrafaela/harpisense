# Repasse frontend: autenticação candidata em desenvolvimento

Recebido do responsável frontend e conferido por leitura de `frontend/docs/REVISAO_OPERACIONAL_20261107.md` na worktree `frontend-operational-review`. Não foi repetido o ensaio por esta revisão de aceite, nem copiado código da equipe. HEAD observado `89d40eedfcbcb0c8200991f310ebaad89248c9da`; alterações locais não commitadas. Esse SHA sozinho **não reproduz** a fonte servida/testada. Documento também não commitado no momento da leitura.

SHA-256 do relatório lido: `f8759a016a6ebbbfcb09b81ff7173b06db828be0f42e31ef33b98cb8add7817f`. Identifica o documento observado, não o build completo, payload ou resultado reproduzido por esta revisão.

## Ambientes distintos

| Ambiente | Resultado reportado | Limite |
|---|---|---|
| Fonte 5176 em demonstração | Revisão visual, sem operação real | Demo não comprova API, banco ou produto instalado; 5174 preservada |
| Unitários/Playwright/build | 66 unitários, 14 Playwright com fixtures; build/typecheck/diff aprovados | Não são testes operacionais do backend ou dos pacotes |
| Browser 5176 → proxy P11 → runner 18082 | Fluxo real HTTP de autenticação candidata `071d052` aprovado pelo frontend | Runner nativo Windows de desenvolvimento, não instalador; estado da fonte inclui alterações locais |
| Backend/PG direto e restart | Não verificados nesse ensaio frontend | Precisam de evidência independente Backend; reload/browser/logout não equivalem a restart do serviço/banco |
| Windows instalado offline | Não executado | Nenhuma etapa da matriz instalada promovida |
| Ubuntu instalado offline | Não executado | Nenhuma etapa da matriz instalada promovida |

## Fatos reportados no browser HTTP real

- Bootstrap, início/confirmação TOTP, sessão administrativa e reload passaram.
- Emissão/reemissão de duas listas de dez itens, com rótulos por finalidade, passaram. Isso não comprova por si só hashes/revogação no banco nem uso único concorrente.
- Confirmação da geração, logout/login e consulta `first_access=completed` passaram; dashboard não reabriu modal no próximo login. Confirmação foi observada pela API/browser, sem consulta SQL independente.
- Código não apareceu na URL/localStorage/sessionStorage no teste reportado. Ausência em IndexedDB, caches, logs, erros e auditoria deve ser demonstrada com cobertura própria; não ampliar a alegação do ensaio.
- TOTP calculado localmente a partir da chave de inscrição: protocolo validado, aplicativo celular/Microsoft Authenticator **não testado**.
- Evidências reportadas somente com rotas/status/contagens, sem screenshots, vídeos, HAR ou traces de autenticação/códigos. Capturas publicadas são de dashboard demonstrativo.

## Provas ainda solicitadas ao Backend

1. Encerrar e reiniciar **apenas** o runner identificado preservando o mesmo banco/estado; novo login e `completed` mantidos. Não reprovisionar, semear ou trocar DSN para produzir resultado.
2. Metadados de conta/geração/ack e hashes por propósito no PostgreSQL, sem originais, senha, token, grant ou TOTP nas evidências. Reemissão autenticada invalida conjuntos anteriores conforme contrato final publicado.
3. Código password_reset guardado consumido uma única vez, inclusive replay concorrente em conexões distintas; MFA continua ativo e senha nova não dá sessão plena sem TOTP. Recuperação de autenticador continua separada.
4. Snapshot de casos com origem/revisão/frescor/cobertura próprio. `first_access.completed` não atesta casos/estado operacional, disponibilidade do executor nem aplicação do ConfigManager.

## Lacunas funcionais mantidas

ConfigManager real não exercitado nesse E2E: navegação/rascunho/reload cobertos por fixtures. Contrato candidato reporta perfil `esp32-lighting`, firmware indisponível e aplicador `presentation`; não comprova ativos genéricos ou aplicação operacional MQTT/captura.

Inventário **reportado** identifica zero artefatos RF/IF aprovados. Não significa zero código de modelos ou ausência de todo artefato no disco: significa que não há aprovação/proveniência demonstrada para o aceite. SHAP com modelos aprovados, suas saídas exatas e geração real BitNet na ficha continuam pendentes. IDs sintéticos não atestam tráfego operacional nem autorizam contenção.

Nenhum reboot, serviço instalado/autostart ou isolamento offline foi executado por este repasse. A candidata 3 Ubuntu conserva seu escopo original. As células Windows/Ubuntu da matriz continuam pendentes; o avanço é exclusivamente no ambiente **dev HTTP/auth**.
