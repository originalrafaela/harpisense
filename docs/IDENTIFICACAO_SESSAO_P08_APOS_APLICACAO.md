# Instalação confirmada e identificação de sessão P08

Rodada de conferência e identificação somente leitura, posterior à aplicação
executada pelo usuário. Nenhuma coleta, execução de pipeline/modelo, consulta SQL,
associação de lote, alteração de checkpoint ou serviço foi realizada.

## Código efetivamente instalado

Os hashes lidos na VM coincidem com a candidata testada do commit `2de050e`,
branch `fix/p08-p09-validated-batch`:

| Arquivo | SHA256 instalado |
|---|---|
| auxiliary_audit_adapter.py | 04b58d66d5d6d9cd513bff4b559c187bca4a2d13ea370e80fcbfc97bb9eb5416 |
| p08_p09_pipeline.py | 4ec9ed8c2fb5b068ebdae4b6cd7643d1aca5a5c0fcc5d9c354e28f5f7f12d8dc |

Diretório: `/opt/harpisense/staging/p09-deteccao-decisao/adaptador_logs_p08_p09`.
Ambos root:root 0644, diretório root:root 0755: adequados para código legível
pelo usuário do processo sem conceder escrita a grupo/outros. Os gates, leitor
de janelas e demais fontes conferidos permanecem com hashes anteriores.

Backup encontrado: `.validated-batch-backup-5jgd2gmh`, root:root 0700. A existência
e proteção estão confirmadas. O acesso SSH harpiserver não pode ler os arquivos
internos nem receipt.json. **Conferência dos hashes de backup e do recibo ainda
pendente de leitura privilegiada**, sem inferir que houve divergência ou afirmar
que a restauração foi integralmente verificada.

Lotes, manifestos e checkpoint: os cinco hashes continuam iguais aos da base
confirmada. A inspeção sanitizada também comparou metadados/hashes antes e depois,
sem alteração. O Store P11 mantém cba6be580f72a8e39077ea9e7437cadee04b67effbb618737309f6450d97643c;
app.py mantém 52078a449886528569a85645e02df974826dc1a24566c01db6bc5f487f328ef2.
P11 ativo, PID 1787, início 26/10/2026 12:53:53 -03, sem reinício. A paginação SQL
não foi instalada. `INSTALLED_READONLY_RESULTS.json` e `STAGING_STATUS.json`, na
branch de implementação, registram o estado aplicado e os limites da conferência.

## Sessão: identificação pendente de acesso, não de uma nova coleta

Os scripts P08 atuais apontam para `/opt/harpisense/capturas`, mas esse diretório
nega leitura ao usuário SSH. Não é possível afirmar quais sessões estão nele.
O ID `p08-v4-persistencia-auto02` aparece como padrão do leitor existente;
isso é **uma referência candidata**, não prova de que seus arquivos existem ou
de que os lotes de auditoria pertençam a essa sessão.

Foi preparado `inspect_p08_applied_readonly.py`, que usa apenas biblioteca padrão,
leitura de arquivos e stdout. Não importa módulos do projeto, não acessa SQL,
não executa subprocessos e não grava arquivos. Ele verifica os backups, lista
relatórios .session.json e identifica uma candidata com seus artefatos/janelas,
expondo somente campos de metadados permitidos, sem payloads ou credenciais.
O script já foi exercitado com o acesso comum: confirma os hashes instalados e
reporta PermissionError nos dois locais protegidos. Para concluir esta tarefa,
foi solicitado ao usuário executar em seu terminal da VM:

```sh
sudo /usr/bin/python3 -B /tmp/harpisense-p08p09-validated-batch.grdSWc/p08_p09/inspect_p08_applied_readonly.py
```

Não mudar permissões dos backups/capturas. Não enviar senha. A saída privilegiada
ainda não foi recebida neste registro. Sem ela, não se marca backup como
integralmente verificado nem sessão como identificada. A impossibilidade de ler
um diretório não demonstra ausência de dados ou necessidade de nova coleta.

## Vínculos a demonstrar, sem criá-los nesta rodada

Conforme o código atual do P08 e as referências aprovadas V2:

| Relação | Evidência necessária |
|---|---|
| Sessão → PCAP | .session.json com caminho, tamanho e SHA256 correspondentes ao PCAP existente; intervalo UTC, interface e resultado das verificações básicas. |
| Sessão/PCAP → integração | `<session>.p08.json` com session explícita, pcap.path/sha256/size_bytes e interface correspondentes. O nome de arquivo isoladamente não comprova a relação. |
| Integração → janelas | aggregation.windows; IDs únicos, collection_session_id, sensor_id, interface, perfil, feature_schema_version, duração e início/fim; integridade/proveniência do relatório. |
| Evidência → sessão/janela/alvo | ID estável da evidência, inventário/vínculo confiável para collection_session_id, sensor_id, target_ref e scope_ref quando exigido pelo contrato; intervalo temporal coerente. Um endereço IP não substitui identidade MQTT/dispositivo. |
| Lote → evidências/fonte | Hash e manifesto local consistente, evento, cursor e boot; identidade/procedência da fonte e contexto confirmado separadamente. Hash não autentica autoria. |
| Fontes → cobertura | Fontes obrigatórias explícitas e intervalos comprovados por fonte/contexto, retenção, rotações/reinícios/lacunas e relógios. O diagnóstico de captura não substitui coverage_records autenticados. |

Os dois lotes antigos **continuam sem associação**. A leitura permitida mostrou:

- acabf4…: um evento raw validation_failure com observed_at
  `2026-10-25T18:46:20.171871+00:00`, sensor_id=null, cursor/boot presentes, sem
  collection_session_id, window_id ou target_ref explícitos no evento.
- d94cc2…: lista vazia, sem eventos para estabelecer vínculo.
- Os manifestos têm UNKNOWN, continuity_verified=False e autorizações False;
  não declaram os vínculos de sessão/janela/alvo. Cursores delimitam uma leitura,
  mas não provam cobertura ou pertinência a uma sessão.

Mesmo uma coincidência futura de horário com uma sessão não basta para autenticar
o vínculo. Não preencher contexto por proximidade temporal ou pelo nome dos lotes.

## Artefatos e fontes ainda necessários para validar cobertura

Primeiro, concluir acesso aos artefatos existentes; sua ausência ainda não está
demonstrada. Depois, verificar PCAP, session, integração/janelas e diagnóstico
coverage do mesmo conjunto, além de registros de cobertura **por fonte** e
inventário/vínculos confiáveis. O produtor atual de `<session>.coverage.json`
é um diagnóstico conservador: seus intervalos têm cobertura_comprovada=False.
Heartbeat ativo e zero perdas do kernel, isoladamente, não comprovam captura
integral nem logs completos, conforme o próprio código P08.

Fontes a disponibilizar conforme required_sources: journal do consumidor
`harpisense-mqtt.service` (telemetria/validação/duplicidade), logs Mosquitto de
autenticação/ACL/publicação, e logs da API quando exigidos pelo cenário. Para cada
fonte faltam confirmação do host/serviço, intervalo, retenção/rotação, boot/cursor,
continuidade e sincronização temporal. O host SSH se identifica como `gateway`;
nele foram observados `harpisense-mqtt` e `harpisense-p11` ativos. Isso não prova
onde o broker roda nem que o histórico completo esteja retido.

As referências V2 P08 de correlação exigem sessão/escopo/alvo confiáveis e deixam
os componentes v1 preservados em componentes/. Usam-se pacotes anteriores de
Versões corretas para componentes sem atualização; não se conclui ausência por
não existir revisão individual V2. Nenhum componente foi substituído nesta rodada.

## Se uma coleta nova se mostrar necessária: procedimento proposto, não executado

Uma nova sessão só deve ser proposta após verificar se a sessão e os logs antigos
permitem o vínculo/intervalo exigidos. Se não houver evidência recuperável, manter
os lotes antigos sem vínculo e produzir um conjunto novo, sem reinterpretar os
antigos como evidência da nova sessão.

1. Definir sessão com ID novo e diretório/arquivos exclusivos, janela UTC,
   interface, sensor, percurso, perfil, alvo e fontes obrigatórias confirmados.
   Não usar valores default dos scripts como inventário de rede verificado.
2. Disponibilizar HarpiServer/gateway de captura; host real do broker; consumidor
   de telemetria; produtores legítimos ESP32/Poste 02 conforme o fluxo. O host da
   API é necessário se seus logs forem fonte obrigatória. Windows/VMware e
   intermediário Tailscale precisam estar ligados somente se hospedarem ou
   transportarem esses papéis. Não há necessidade de ataques/Kali para esse fluxo.
3. Registrar relógios e limites de retenção/boot/cursor das fontes no começo/fim,
   com exportação limitada ao intervalo e arquivos novos. Não executar os
   coletores incrementais atuais nem avançar seus checkpoints para esse ensaio.
4. Em rodada autorizada, usar o controlador `capture_session_v4.py` com interface,
   source-ip, duration e output explícitos. Ele recusa sobrescrita; a existência
   de PCAP não promove collection_complete. Não iniciar essa captura nesta rodada.
5. Processar offline com `integrar_p08_v2.py` e diagnosticar com
   `diagnosticar_cobertura.py`, preservando hashes e saídas exclusivas. O
   `orquestrar_p08_v4_experimental.py` vigente também chama
   `persistir_janelas_p08.py`: **não usá-lo para um procedimento sem escrita no
   PostgreSQL**. A persistência é uma ação separada e não foi autorizada aqui.
6. Validar vínculos e cobertura independente por fonte antes de produzir contagens.
   Campos desconhecidos não viram zero. Eventos auxiliares de validação/duplicidade
   não criam features novas no esquema RF/IF.
7. Guardar o conjunto novo com provenance/manifestos sem tocar lotes/checkpoint
   antigos. Permanecer UNKNOWN quando houver lacuna, com inferência e IPS False.

Próximo passo mínimo desta rodada: receber o resultado da inspeção privilegiada,
concluir a conferência de backup e identificar uma sessão real com seus vínculos
comprováveis. Não implementar associação, coletor ou promoção de cobertura.
