# Entrada e retomada da configuração

Entrega do **Gerenciador de Configurações**, branch `feat/installer-orchestration`,
base `d172a38`. Não altera `main.tsx`, `account-mfa.tsx`, `api.ts`, composição do
backend, autenticação, MFA, catálogo ou registry. Não foi implantada no HarpiServer.

## Interface final para o Frontend

```tsx
import {InstallationEntry} from './installation-entry';
import {ConfigManager} from './config-manager';

// No shell autenticado, após instalação/composição aprovada:
<InstallationEntry
  client={client.current}
  onOpenSettings={() => navigate('settings')}
/>

// Manter a montagem existente em Configurações:
<ConfigManager client={client.current} request={configRequest} logout={logout}/>
```

`InstallationEntryProps` é exportado de `installation-entry.tsx`:

```ts
type InstallationEntryProps = {
  client: InstallationClient;
  onOpenSettings?: () => void;
};
```

`InstallationClient`, exportado de `installation-state.ts`, é `Pick<Client, 'get'>`.
Usa a assinatura real `get(path: string, method?: string, body?: unknown): Promise<unknown>`
do cliente compartilhado. O `Client` existente é diretamente compatível; não criar
outro cliente, copiar tokens ou passar senha/grant ao componente. `ConfigManagerProps`
também é exportado; seus três argumentos permanecem compatíveis com a montagem atual.

O responsável pelo Frontend aplica o import e a montagem em `main.tsx`. Montar somente
no modo autenticado da composição aprovada; desmontar ao sair/trocar de sessão, inclusive
quando a mesma instância de `Client` é reutilizada. A aprovação da composição é uma
pré-condição da montagem, não um estado inventado a partir de `/setup`. Os endpoints
atuais não expõem um recibo próprio de aprovação da composição.

`onOpenSettings` apenas abre Configurações por ação do usuário. Sua ausência é aceita:
o componente informa que o assistente continua disponível em Configurações. Nenhum hash,
URL, redirect, timer de redirecionamento ou bloqueio do dashboard é introduzido. O shell
continua responsável pelo logout e pela expiração da sessão do cliente compartilhado.
O callback não precisa ser memoizado; sua troca não repete as consultas.

## Leitura e estados

A entrada executa somente dois GETs autenticados, `/api/v1/config/setup` e
`/api/v1/config/current`, ao montar, trocar o cliente ou solicitar atualização.
Não escreve, não cria propostas e não chama endpoints de conta, MFA ou bootstrap.
Respostas tardias de uma montagem/cliente anterior são descartadas. Falha de consulta
apresenta estado desconhecido e botão de repetição, sem exibir texto bruto do servidor.

| Estado | Evidência exigida | Ação |
|---|---|---|
| Instalação nova | `version=0`, `document=null`, revisão desejada zero e efetiva nula | Iniciar assistente |
| Existente com configuração pendente | Progresso ou revisão existente sem confirmação completa abaixo | Retomar assistente |
| Configuração concluída no escopo aplicado | Desejada e efetiva iguais e positivas, `APPLIED`, `applied_verified`, documento efetivo presente e observação de apresentação verificada quando retornada | Abrir Configurações |
| Falha de consulta | HTTP/rede/sessão ou resposta incompatível | Repetir consulta; demais funções continuam acessíveis |

Se houver rascunho, seus parâmetros também precisam coincidir com os efetivos para
declarar a configuração concluída. Edição salva após aplicação continua pendente.
Os campos preparatórios de perfil/dispositivos/backup e as sugestões de `/setup.pending`
não são comprovantes de aplicação. A conclusão exibida se limita à revisão aplicada;
nunca significa que firmware, MQTT, captura, backup e defesa foram instalados/verificados.
`operational` é apresentado separadamente e vem exclusivamente do backend. Na entrega
atual ele continua `false`; nem salvar, validar ou aplicar apresentação o torna `true`.

O `ConfigManager` compartilha essa classificação. Na falha inicial não oferece um
formulário vazio que possa substituir o progresso desconhecido. Atualizar estado mantém
as edições locais; **Retomar assistente** recarrega etapa e valores persistidos, substituindo
explicitamente as edições não salvas, conforme aviso junto ao botão. Mantém controle de
versão, conflitos e chaves de idempotência existentes.

## Bootstrap/MFA e fronteira da entrega

Esta é a entrada **pós-login**, não o bootstrap anterior à criação da conta. O fluxo
`AdminAccess({client,onAuthenticated})` e `AccountSecurityPanel({client})` permanece com
Backend/Frontend. Após autenticação, o shell monta esta entrada para consultar o progresso.
Nenhum cadastro público, credencial default ou novo provedor de autenticação foi criado.

Foram consultados `ADMIN_MFA_CONTRATO_CANDIDATO.md` e
`ADMIN_MFA_INTEGRACAO_RECUPERACAO.md` da branch `feat/admin-bootstrap-mfa`. A provisão
pré-conta de grant local protegido e chave MFA será conectada pelo instalador após
publicação final e validação da transição de conta/recuperação. Esta branch não integra
nem implanta `3b5aa70`, não emite grants e não aplica migrações MFA.

Origens coordenadas: desenvolvimento `http://127.0.0.1:5174` e preview
`http://127.0.0.1:4174`. Nenhuma delas é fixada no componente. Produção usa o build
estático e o proxy/origem aprovado pelo instalador, sem dependência do servidor Vite dev.
O build desta branch valida os módulos; a entrada passa a integrar o bundle da aplicação
quando o Frontend adicionar a montagem combinada em `main.tsx`.

## Referências

Referência mais recente: `referencias/versão_v2/12_Instalacao_Operacao_Backup`, em especial
`INSTALACAO_E_ATUALIZACAO.md` e `RESTAURACAO_E_RECONCILIACAO.md`: versões fixadas,
preservação de identidade/estado, segredos fora do repositório e reconciliação explícita.
O pacote V2 de firmware mantém ESP32-WROOM-32; esta entrega não modifica firmware.
Para a interface anterior, permanece válida a referência
`referencias/Versões corretas/HarpiSense_Interface_Administrativa_v1/README.md`, observando
que sua autenticação antiga foi substituída pelo cliente administrativo atual. A ausência
de um componente em V2 não é tratada como ausência de implementação.

## Verificação reproduzível e integração pelo arquiteto

No diretório `frontend` do worktree, com Node 24 e Chromium do Playwright disponíveis:

```sh
npm ci --ignore-scripts
npm run build
npm test
node node_modules/@playwright/test/cli.js test --config tests/installation.playwright.config.ts
```

Se necessário, provisionar Chromium com `npx playwright install chromium`.
O teste de navegador usa exclusivamente a porta loopback **5186**, recusa porta ocupada
e encerra seu próprio servidor. Não usa nem altera os servidores 5174/4174 dos outros
responsáveis. O harness em `tests/installation-harness.*` não faz parte do build de produção.
O arquivo `.browser.ts` é executado pela configuração isolada, sem interferir na suíte
existente de `.spec.ts` que usa o servidor de desenvolvimento compartilhado.

Verificação local: build de produção aprovado, **46 testes de unidade** (cinco novos)
e **10 cenários de navegador** aprovados. Cobrem nova/existente/concluída/falha,
resposta inválida, sessão recusada, callback ausente, resposta tardia, remontagem,
retomada persistida sem escrita, atualização preservando edição e repetição de gravação
após falha com a mesma versão/chave idempotente. São testes isolados da UI; não representam
uma instalação completa em máquina limpa ou validação de recuperação MFA.

O arquiteto integra o commit desta branch na base do Frontend (ou aplica os mesmos arquivos),
e o responsável pelo Frontend adiciona a montagem acima, após composição aprovada e sessão
autenticada. Não é necessário alterar o núcleo `feat/detection-composition`.
Reexecutar build/testes na base integrada; preservar dashboard como página normal e o
acesso permanente a Configurações. A entrega do instalador completo continua separada
das validações desta UI e depende do mecanismo final de primeiro acesso aprovado.
