# Teste funcional do software — 08/11/2026

**Resultado: aprovado no ambiente isolado de desenvolvimento.** Foram executadas 61 verificações reais de integração e 76 testes unitários da interface, sem falhas na rodada final. Build e typecheck passaram (55 módulos).

Branch: `integration/initial-auth-20261108`. Base desta rodada: `2c9b249`; código funcional da integração `385b363`. Alterações desta rodada limitadas ao runner de aceitação e às evidências: saída separada, espera pelo carregamento assíncrono dos códigos, compatibilidade com abertura automática da Autenticação inicial e erros sanitizados. Não houve alteração de regras de autenticação ou do software para fazer o teste passar.

## Ambiente efetivamente usado

Windows existente, Python fonte da integração, PostgreSQL nativo, Mosquitto TLS, API HTTP e Chromium reais. Portas exclusivas de teste: 25432, 28080 e 28883. Dados privados e credenciais gerados exclusivamente para essa execução em diretório ignorado pelo Git.

O recibo de ativação foi emitido por fixture explícita para isolar o teste do software local. A API de autenticação, o PostgreSQL, a proteção DPAPI e o IPC Windows utilizados no fluxo são reais. Esta rodada não comprova a emissão comercial ou a ativação por um emissor de produção.

Nenhum Docker foi usado; não houve instalação ou alteração de serviços do host, modificação/reboot de VM ou tráfego contra os serviços do laboratório. O publicador MQTT é um processo controlado de teste, não um sensor físico. Os processos próprios foram encerrados; as três portas estavam fechadas na checagem final.

## O que passou

| Área | Evidência funcional |
|---|---|
| Autenticação | Cadastro por IPC, recusa de TOTP inválido, confirmação válida, dashboard e exatamente três códigos distintos |
| Controle de acesso | Consultas e alterações sem sessão recusadas; Host/origem indevidos recusados no transporte isolado |
| Gerenciador | Salvar rascunho pela interface, consultar o mesmo estado no PostgreSQL, proposta/validação e aplicação real de nome/fuso com reautenticação |
| Inventário | Cadastro de ativo pelo navegador, leitura no banco, recusa de revisão antiga e preservação após reload/restart |
| Persistência | Reinício dos processos de API/consumidor/PostgreSQL; conta, apresentação, rascunho e inventário preservados; novo login com TOTP |
| MQTT | Conexão TLS, autenticação e SUBACK reais; inicialmente sem dispositivo publicando; mensagem legítima identificável consumida, persistida e lida pela API/interface |
| Estado observado | Heartbeat vencido deixa de afirmar conexão atual; salvar modo MQTT como rascunho não altera o broker ativo |
| Recuperação | Troca de senha pelo navegador com código e TOTP, revogação de sessões, uso único do código, MFA preservado, novo login e reemissão explícita de três códigos |
| Operação | Estado desconhecido bloqueia mudança; pendências de aprovação/anomalia/incidente/verificação/execução recusam transições; fontes stale bloqueiam alteração; emergência persiste e mantém consultas disponíveis |

Os testes de autoridade operacional usam fatos controlados em banco descartável e modo de simulação; não executam contenção, captura de ataque ou comandos de firewall. A seleção de M2/M3 não foi tratada como defesa real.

## Evidências

- [Resultado completo: 61 verificações](evidence/software-functional-20261108/product-native-result.json).
- [Broker ativo sem mensagem publicada](evidence/software-functional-20261108/windows-broker-no-message.png).
- [Mensagem recebida e visível na interface](evidence/software-functional-20261108/windows-mqtt-received.png).
- [Primeira tentativa do runner](evidence/software-functional-20261108/attempt-01.json).

A primeira tentativa contou os códigos antes de a requisição assíncrona terminar. Foi corrigida a sincronização do runner para esperar os três itens na interface; o software não foi modificado. A segunda rodada terminou com 61 verificações aprovadas. Não há screenshots de senha, QR, segredo TOTP ou códigos de recuperação; os erros do runner não imprimem conteúdos de formulários.

## Comandos executados

```text
frontend: npm.cmd test
frontend: npm.cmd run build
../native-initial-auth/.venv/Scripts/python.exe packaging/native/acceptance_product.py --postgres-bin D:/Programas/PostgreSQL/bin --mosquitto D:/Programas/Mosquitto/mosquitto.exe --evidence-dir docs/evidence/software-functional-20261108
```

## Limites e passagem para ataques

O núcleo funcional exercitado passou. Isso não é homologação dos instaladores finais Windows/Ubuntu, reboot do SO ou comprovação de sensores/captura/modelos/defesa reais. Aplicação de infraestrutura pelo gerenciador continua limitada ao contrato implementado; o teste de nome/fuso não comprova reconfiguração de MQTT/VPN/firewall. Backup em nuvem e geração BitNet não foram ensaiados nesta rodada.

**Nenhum cenário de ataque C01–C09 foi executado.** Antes dessa próxima etapa, é necessário confirmar no laboratório real o percurso legítimo, a captura/evidência e o alvo isolado de cada cenário. Os resultados de fixtures e de simulação não substituem essa confirmação. A política de perda do autenticador permanece pendente; licença e código de recuperação não removeram MFA.
