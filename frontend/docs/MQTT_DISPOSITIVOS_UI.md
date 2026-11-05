# MQTT e dispositivos: montagem e contrato visual

Base backend: `5898cf6`. A área `MqttDevices` é um editor controlado interno de
`ConfigManager`, renderizado nas etapas existentes `devices` e `mqtt` (uma única
instância visível). O botão permanente **Abrir MQTT e dispositivos** abre essa
mesma área sem salvar, reiniciar ou descartar os demais campos do assistente.
Salvar rascunho, criar proposta e validar parâmetros reutilizam os handlers,
revisões, chaves de idempotência e histórico existentes. Não há novo wizard.

## Montagem combinada com Frontend

O Frontend confirmou compatibilidade com a montagem existente de `611e944`:

```tsx
<InstallationEntry client={client.current}
  onOpenSettings={() => navigate('settings')} />
// Na rota existente de Configurações:
<ConfigManager client={client.current} request={configRequest} logout={logout} />
```

As props públicas de ambos permanecem inalteradas. `client` continua sendo
`Pick<Client,'get'>`, com a sessão administrativa/MFA do shell. `request` em
ConfigManager recebe o caminho completo; o editor interno usa o wrapper
`/api/v1/config` existente. Desmontar a área ao encerrar/trocar de sessão.
Não montar `MqttDevices` separadamente no shell nem duplicar ConfigManager.
Esta entrega não altera `main.tsx`, nem a worktree do Frontend.

## Comportamento

- Modo local gerenciado sugerido para uma configuração nova; só vira rascunho
  salvo após PUT setup. Uma configuração antiga sem modo não é reclassificada
  automaticamente como local por ter um host. O modo deve ser escolhido.
- Modo/destino em edição, rascunho salvo, proposta e documento efetivo são
  mostrados separadamente. O destino efetivo vem exclusivamente de current.
  Validação de parâmetros não comprova conexão e não troca o broker.
- GET `/mqtt/status` é independente do carregamento persistente; falha mantém
  o formulário e permite repetir. 401 usa o logout existente; respostas tardias
  de outra instância são descartadas. O contrato 1.0.0 atual só comprova a
  ausência de observadores: componente, broker, consumidor e mensagens por
  dispositivo aparecem como **Não verificado**. Resposta incompatível também
  não produz sucesso. Um futuro observador exige contrato e parser próprios.
- Testar conexão, aplicar MQTT e cadastrar dispositivo ficam desabilitados:
  `5898cf6` ainda não fornece operações reais. Dispositivos preparatórios são
  somente parte do rascunho; não são cadastro operacional. Perfis selecionáveis
  são os retornados pelo backend; Poste 2 Ubuntu é apresentado como publicador,
  separado de firmware. Nenhum teste físico ou conectividade é inferido.
- O instalador nativo instala componentes/registra serviços. A interface não
  executa comandos ou expõe senhas técnicas. Sem dependência de Wokwi.

## Validação

`npm test`, `npm run build` e
`npx playwright test --config tests/installation.playwright.config.ts`.
Os testes de navegador usam apenas API interceptada no harness isolado:
primeiro uso/retomada, atalho permanente sem escrita, modo padrão e reabertura,
destino efetivo preservado, conflito, erro/repetição e expiração de sessão.
Não são ensaio de MQTT real nem validação de instalação nativa.
