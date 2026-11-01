# Integração local — 01/11/2026

Base real limpa: feat/frontend-backend-autonomia, 0f45aaab6b561fbded52e1c259578ff1f607685f.
Raiz main 9d58e69, atrás 3, com arquivos não rastreados preservados. Não houve
edição de outras worktrees nem limpeza das entradas antigas prunable.

Adaptador já entregue em f333e2fcb05acfdb6803d90be251b6d7355a4a30 incorporado
por cherry-pick ebb24c0. A pendência de implementar adaptador está encerrada.
Firmware 49d2eac, gerenciador edd0cb7 e captura/cobertura 1cf058e continuam
nas respectivas worktrees; não foram mesclados nem ativados nesta rodada.
Precedência: referencias/versão_v2; componentes não atualizados continuam
disponíveis em referencias/Versões corretas.

## Consumidor composto

backend/delivery/mqtt_consumer.py fornece bind_consumer, que instala on_connect
e on_message no cliente já autenticado. Reconexão refaz as assinaturas; falha
de conexão não assina. Falhas operacionais recebem log sanitizado por tipo.
O bootstrap existente mantém broker, autenticação, transporte, conexão e loop.
Não há cliente paralelo nem banco alternativo. Ligação concreta no bootstrap:

```python
from delivery.mqtt_consumer import bind_consumer
bind_consumer(client, store, emit_audit_safely,
              record_factory=Record)  # Poste 1 fechado por padrão
```

Executar essa ligação antes do connect/loop existentes, substituindo somente
as atribuições dos callbacks. O módulo local é executável por importação;
nenhum arquivo do serviço da VM foi modificado. Usar o Record P11 existente
via record_factory e o mesmo PostgresStore. O padrão local usa delivery.Record.
P06 é dependência externa identificada no guia do adaptador, com pacote/schema
completos no PYTHONPATH. Não foi copiado outro schema.

Poste 2 conserva tópico, identidade, parser, payload e ID baseado em bytes.
O binding não chama username_pw_set, tls_set, connect ou loop_forever.
Autenticação real do broker não foi reensaiada: a configuração fica no cliente
existente, sem mutação. Poste 1 usa o Record/revisão/source e advisory lock do
PostgresStore existente. Nenhuma tabela ou migração adicional.

## Provas executadas

Python 3.12 no venv local frontend/local-evidence/poste1-contract-venv;
dependências delivery e P06 instaladas nesse ambiente, sem Python global.
PostgreSQL 18.6 descartável harpisense-poste1-integration-20261101,
loopback 55442, banco poste1_fixture. DSNs de fixture não apontam para a VM.

- 34 testes delivery aprovados, zero pulos: 18 regressões anteriores,
  10 do adaptador e 6 do binding (4 com PostgreSQL real).
- 21 testes P06 aprovados.
- Os quatro testes PostgreSQL herdados pelo binding percorrem on_message,
  validação P06/perfil, Record e persistência: retry, conflito, concorrência,
  atraso/fora de ordem, imutabilidade temporal e bytes do Poste 2.
- Mock do cliente valida assinatura/reconexão/flag fechada e ausência de
  alterações de credenciais/conexão. Não comprova tráfego MQTT real.

Reprodução: comandos do guia INTEGRACAO_ADAPTADOR_POSTE1_20261031.md, usando
o venv acima e unittest discover -s backend/delivery_tests -v. Definir também
TEST_DATABASE_URL para a mesma fixture descartável, para não pular os quatro
testes PostgreSQL delivery anteriores. Não apontar essa suíte para banco real.

## Responsabilidades e contrato proposto ao Backend

maestri list identificou este terminal como Gerenciador de configurações,
sem agentes/notas/portais conectados. Portanto não houve aceite de outro agente
nem repasse por mensagem. Nenhuma edição concorrente foi observada na worktree
limpa; somente esta worktree recebeu mudanças. Responsabilidades do operador:
Arquiteto cuida de bootstrap/composição/implantação; Backend da API autenticada;
IoT de firmware/ESP32; Edge de visibilidade/contenção verificáveis.

Proposta de interface HTTP para o Backend revisar sobre ConfigStore edd0cb7:

| Operação | Rota proposta | Biblioteca |
| --- | --- | --- |
| Ler estado | GET /api/v1/config/installations/{installation} | current |
| Criar snapshot | POST /api/v1/config/installations/{installation}/proposals | propose |
| Validar proposta | POST /api/v1/config/operations/{operation_id}/validate | validate |
| Ler revisão | GET /api/v1/config/installations/{installation}/revisions/{revision} | revision |
| Auditoria paginada | GET /api/v1/config/installations/{installation}/history | history |

Reutilizar sessão administrativa vigente; actor vem exclusivamente da sessão,
autorizar installation no backend. MFA continua pendente: operações que o
exijam devem recusar, nunca fingir segundo fator concluído. Preservar política
mínima de senha 8. POST encaminha o DTO request da biblioteca, sem inventar
patch: snapshot completo, expected_revision e idempotência conforme schema.
Mapear Conflict para 409 com revisão atual, validação para 422 sanitizado,
ausência de sessão para 401 e falta de autorização para 403. Não ecoar segredos.
Capabilities vem de instalador/backend confiável, nunca do navegador.
begin_application, record_verified, confirm_application e fail_application são
internos; não aceitar recibos do assistente como prova. Efetiva desconhecida
permanece null. Esta proposta não implementa API nem primeiro assistente e
depende de aceite Backend; a biblioteca não foi migrada para banco operacional.

## Limites e próxima ação

Integração validada localmente com entrada sintética e cliente mockado;
Poste 1 permanece desabilitado. Não é integração operacional validada.
Ativação depende de composição do bootstrap alvo, equivalência do store/Record,
empacotamento P06, testes TLS/CA/hostname, identidade/ACL e segredo próprios,
hardware/GPIO/circuito/NTP/fila e ensaio físico. Não houve broker, rede, firewall,
VM, gravação de firmware, inferência, contenção ou geração BitNet.

Login: nenhum portal conectado; consulta local não encontrou listeners 4174 e
18000. Não foi iniciado túnel/serviço nem solicitado segredo. Próxima ação de
aceite visual é reconectar o portal observável e restabelecer o preview/túnel
aprovados; operador entra no formulário, depois observar polling/logout/expiração.
Próxima ação de desenvolvimento é Backend aceitar/ajustar a interface acima e
implementar a API em worktree própria, sem editar o bootstrap do Arquiteto.
