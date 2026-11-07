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

Preservação adicional concluída: snapshot
`candidate3-install-failed-preserved-20261106`, UID 2. Callback de sucesso
confirmado às 21:40:01 UTC, antes da restauração de `Snapshot 1`.
Árvore preservada em `snapshots.vmsd`. Os discos da tentativa anterior e
releases 1–3 permanecem preservados.

## Candidata 4 preparada

Fonte/build: commit `52a61ef`. Release
[native-installers-20261106-candidate.4](https://github.com/originalrafaela/harpisense/releases/tag/native-installers-20261106-candidate.4).
Recibo: [published-assets-candidate4.json](../published-assets-candidate4.json),
quatro digests conferidos contra o GitHub. Windows congelado passou em
`RUNTIME_IMPORTS_OK`. Builds concluídos; logs locais `.native-build/candidate4-*`.

- SHA-256 Ubuntu: `ec6b3dc27850fa4653a6218c78604023c0e9ee09913022bc02f36c49255ca11d`.
- SHA-256 Windows: `749b14a06db1a47a4e032d0669145a471d8588430782d7b1a8a0e5345770b8c3`.

VM restaurada somente após preservar a falha, iniciada e reconfirmada por SSH
com UUID/hostname/IP originais, cloud-init concluído e ausência de
`/opt/harpisense` e `/var/lib/harpisense`. Candidata 4 baixada por HTTPS em
`/home/trial/harpisense-teste/candidate4`; hash fixado e checksum publicado
retornaram OK. **Instalação candidata 4 ainda não executada**: usuário está
repetindo o fluxo interativamente por SSH. Nenhuma aprovação funcional é
transferida da candidata anterior. Não criar conta de aceitação em paralelo
ao primeiro acesso do usuário.
