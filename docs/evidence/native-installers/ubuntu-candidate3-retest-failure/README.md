# Reteste manual da candidata 3 — falha MQTT — 2026-11-06

**Instalação falhou.** O ensaio anterior aprovado da candidata 3 permanece
preservado como execução histórica, mas este reteste revela uma corrida que
impede considerar a instalação confiável. Candidata 4 preparada para corrigir.

Alvo novo: `harpisense-ubuntu-reteste`, IP confirmado `192.168.155.149`,
MAC `00:0c:29:a9:9d:21`, UUID DMI `2aab4d56-df4b-5ef3-ce71-f1fad2a99d21`.
VMX `.native-test/ubuntu-clean-retest-20261106/Ubuntu-Clean-Retest.vmx`.
Snapshot do usuário confirmado como **`Snapshot 1`** antes da instalação;
cloud-init concluído e ausência dos diretórios HarpiSense confirmadas por SSH
com chave de host fixada pelo console. Somente esta VM estava em execução.

Download da candidata 3 feito na VM em `/home/trial/harpisense-teste`;
checksum publicado e hash fixado ambos retornaram OK:
`72b0e0776d44ea2f6ad1b4dffbc3815932270177ba1c1f6de82e5ffd23468b65`.
Usuário executou `sudo sh HarpiSense-Setup-Ubuntu-24.04-x86_64.run`
pela sua sessão SSH interativa e forneceu o traceback abaixo.

## Falha observada

```text
ubuntu_install.py, finish, line 125: probe_broker(state)
native_server/runtime.py, probe_broker, line 176:
    client.connect(state['mqtt']['host'], state['mqtt']['port'], 30)
paho/mqtt/client.py -> socket.create_connection -> sock.connect
ConnectionRefusedError: [Errno 111] Connection refused
```

Inspeção posterior, somente leitura, encontrou os quatro serviços ativos e
broker escutando `127.0.0.1:8883`; PostgreSQL e API também escutando. Todos
iniciaram às 21:33:34 UTC. Ver `services-after-failure.txt`. Nenhum serviço
foi iniciado manualmente e nenhum arquivo do produto ou dado SQL foi alterado
para contornar a falha. Não declarar bootstrap/login desta tentativa aprovados.

## Causa e correção na fonte

As units são `Type=simple` (padrão). `systemctl enable --now` não garante que
Mosquitto já abriu o socket quando retorna; em seguida o instalador tentava
um CONNECT imediato, sem tolerância a `ConnectionRefusedError`. A recusa e
o listener ativo depois são compatíveis com essa corrida, presente na fonte.

`wait_for_broker` agora repete apenas recusa de conexão, com prazo de 30 s e
intervalo de 250 ms, antes de validar CONNECT/SUBACK/TLS do broker local.
TLS inválido ou autenticação/assinatura rejeitada continuam sendo falhas
imediatas. O modo externo mantém o probe original, sem administrar o broker.
Somente a fonte do pacote foi corrigida; a instalação da candidata 3 não
recebeu patch nem nova execução do instalador.

Regressão determinística em `backend/native_server_tests/test_readiness.py`:
três testes aprovados, abrangendo duas recusas seguidas de sucesso, prazo
esgotado e ausência de repetição para erros TLS/autenticação. Isso não substitui
o novo ensaio real da candidata 4. Nenhuma suíte já aprovada foi repetida
sem relação com a mudança.

Preservação adicional solicitada: snapshot
`candidate3-install-failed-preserved-20261106`. Aguardar callback de sucesso
antes de restaurar `Snapshot 1`. Os discos da tentativa anterior e releases
1–3 permanecem preservados. A próxima instalação deve partir do snapshot limpo.
