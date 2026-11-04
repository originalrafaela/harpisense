# Retomada P08: bloqueio concreto e ensaio preparado

## Base e propriedade

HEAD local e remoto conferidos: `e5a7f17a15859c697415f7ba8d56576bb278fcfb`, branch `feat/p08-evidence-coverage`, limpa no início. Não foi encontrado HEAD posterior no remoto consultado nesta rodada. Base de implementação: `c314ca5`, validação/correção Linux `1cf058e`; evidência de rede incorporada até `a2e7a2f`. Base comum com `9d35906`: `9d58e69cda20a2f918707a4c023a6084260d9164`.

Confirmo a solicitação de propriedade do arquiteto: **integração/edição de todo `backend/p08_p09/` exclusivamente pela composição em `feat/detection-composition`**. Edge/P08 preserva sua worktree e não edita essa pasta, inclusive testes/fixtures. Esta entrega altera somente recibos/procedimento em `p08_captura/`. Mudanças futuras no contrato exigem coordenação; não copiar uma versão antiga sobre a composição. Essa confirmação responde à reserva pedida pelo usuário; não presume resposta recebida via Maestri.

Referências: `referencias/versão_v2` P08/P09 e contratos aprovados; componentes não substituídos de `referencias/Versões corretas` continuam válidos. A data de um diretório não substitui a implementação vigente nem homologa propostas de schema.

## Aceite anterior preservado com distinção de evidências

Mensagem `poste2-2aaecdebdf958fb477df944622d7aede8926a3effe2beaa831a8395129f67e9b`, `sent_at=2026-11-04T18:43:25Z`, luminosity351, led_stateON: publicação/PUBACK por transcrição do operador; consumidor e PostgreSQL por inspeção técnica read-only; exibição na interface autenticada por relato visual do usuário. **Não republicada nesta retomada.** O usuário confirmou novamente esse alcance na instrução de retomada, superando o estado de pausa sem reclassificar capturas históricas.

Não foi capturada resposta HTTP autenticada independente da API. O relato visual não demonstra atualização automática. Nenhuma dessas evidências prova trânsito no gateway ou cobertura P08. O recibo original da pausa permanece como registro datado; o adendo de aceite é esta seção e `RETOMADA_COLETA_READONLY_2026-11-04.json`.

## Delta obtido, sem repetir publicação ou saúde geral

Leituras sanitizadas desta rodada, por SSH estrito e comandos Windows somente leitura:

- VM reportou `2026-11-04 23:49:00 UTC`. Integrador legado `/opt/harpisense/staging/p08-captura/integracao/integrar_p08.py`: tamanho4727, modo664, donoharpiserver; SHA256 `f1537b54ba721153b3daf8a09a09ba1e7aef24aee4a513828302ca237e5f06a5`, igual ao histórico. Nenhuma escrita remota.
- Controlador instalado SHA256 `0dc0c3e5a12d54ae6a26010e853dfab99380a08ed5f4cba718bc7ecabfe51efc`, candidata local `85432f7166e653a2c2ad98f793c58e542b9516fca43e720910cda61c82dad1fd`: diferentes.
- Wrapper instalado SHA256 `040143d349f82ba8b6579a87476bb73b575584a44ed5ac35edf613b7a331a021`, candidata local `652a0d2a6ea4c7fb0256b16a4ec449eb17a67565af04ec724684739b3f2acfd9`: diferentes. Busca limitada maxdepth3 não encontrou `coverage_evidence.py` ou `build_source_manifest.py` no staging P08 consultado; não afirma ausência em toda a VM.
- Consumidor `active`, `NRestarts=0`, ActiveEnterTimestamp `2026-11-04 15:18:28 -03`; conexão ESTAB `192.168.155.144:56345 -> 192.168.155.1:1883`. Windows confirmou o par inverso às `23:50:58Z`. Comprova conexão atual e contador desde o boot, não leitura integral/sem lacunas de mensagens ou janelas.
- Retorno Windows para Poste2: VMnet8, origem192.168.155.1, prefixo conectado192.168.155.0/24, NextHop0.0.0.0. Complementa `route get` já fornecido pelo Poste2, direto ens33/src192.168.155.142. Não repetir esse inventário como desconhecido. Regras/policy routing e MAC/VMnet do produtor ainda não foram inspecionados; rota isolada não prova pacotes.
- HarpiServer para Poste2: ens33/src192.168.155.144, sem próximo salto. NTPSynchronized=yes. Não fornece limite de erro entre hosts.
- Windows `w32tm`: não sincronizado, stratum0, fonteLocal CMOS Clock, último sucesso não especificado. Não há offset confiável medido. Não foi executado resync.
- Diretiva explícita do Mosquitto: `listener 1883 192.168.155.1`. Consulta restrita a listener/log/include não retornou log_dest/log_type/log_timestamp/include_dir explícitos. Isso não certifica ausência de logs; destino real de logs, geração/rotação e exportador com offsets continuam sem confirmação. Não ler password_file nem alterar logging.
- PktMon disponível em `C:/Windows/system32/PktMon.exe`. dumpcap/tshark/tcpdump não encontrados no PATH consultado; `C:/Program Files/Wireshark/dumpcap.exe` e `C:/Windows/System32/drivers/npcap.sys` não encontrados; serviço Npcap não retornado. São verificações delimitadas, não inventário exaustivo de software.

## Onde observar e possibilidade de contenção

Para Poste2 -> broker, pontos corretos são o próprio Poste2/ens33 ou Windows/VMnet8. O percurso configurado é direto; o gateway não é próximo salto. Ainda falta observação de pacotes no sensor escolhido, correlacionada com origem vista no broker, para afirmar o percurso efetivamente observado. Não declarar que todo pacote atravessa ou contorna qualquer sensor com base somente nessas rotas.

HarpiServer/ens33 observa sua própria conexão consumidor -> broker. Pode ser coleta válida de **outro trecho**, se esse escopo for explicitamente aprovado antes; não substitui o trecho de publicação e não deve receber origem do Poste2 no perfil. A ens37 não tem visibilidade garantida do MQTT NAT.

Não há capacidade comprovada de contenção do fluxo de publicação pelo gateway. O último ip_forward observado era0; nenhuma leitura desta rodada o altera ou homologa regras. Interromper a conexão do consumidor afetaria ingestão, sem comprovar bloqueio da publicação. Não executar teste de bloqueio.

**Bloqueio de execução:** sensor compatível/permitido no trecho produtor-broker não confirmado, candidata assinada diferente do staging, fronteiras/exportadores de fontes não definidos, erro temporal sem limite e janela/escopo sem confirmação pelo arquiteto. Uma sessão vazia no gateway não resolve essas pendências. Não houve captura nesta rodada.

## Plano mínimo sem mudar a rede

1. Arquiteto escolhe Poste2/ens33 como sensor Linux, se acesso autorizado, tcpdump e permissões já existirem. Leituras faltantes somente nesse host: `ip -br link`, `ip -4 rule show`, `ip -4 route show table all`, `command -v tcpdump`, `tcpdump --version`, `timedatectl show -p NTPSynchronized`, `cat /proc/sys/kernel/random/boot_id`; associar MAC/NIC à VMnet. Não instalar nem habilitar serviços como efeito dessas consultas. Acesso SSH desta entrega ao Poste2 foi recusado por autenticação; console do operador continua alternativa, sem trocar chaves.
2. Alternativa é sensor Windows/VMnet8 com integração de PCAP homologada. PktMon ETL não é automaticamente PCAP aceito pelo controlador Linux: é necessário validar conversão, metadados, estatísticas de perdas e contrato antes. Não instalar Wireshark/Npcap, adaptar rede ou fingir que PktMon já está suportado. Esta entrega não implementa conversor sem o formato e o escopo aprovados.
3. Em sensor aprovado, preparar **diretório novo da candidata**, sem sobrescrever staging/serviços e sem executar seu integrador na instalação. Manifesto com hashes por arquivo, versões das ferramentas e perfil aprovado. Wrapper atual referencia o integrador legado por caminho absoluto; em outro host precisa de cópia byte a byte autorizada desse integrador e suas dependências, ou extensão revisada para indicar o caminho preservado. Não declarar que copiar apenas o controlador basta. Usar perfil próprio com host/interface reais, nunca `harpiserver` por conveniência.
4. Rollback dessa preparação: parar somente o processo da sessão nova pelo PID registrado e descartar a referência à candidata; manter diretório/evidências para auditoria. O integrador legado e os serviços originais não são substituídos, logo não há restauração de rede/firewall ou de binários instalados. Se alguém propuser substituição de arquivos, exige plano separado com hash anterior, backup exato, verificação e restauração antes da mudança.
5. Perfil proposto: **120s efetivos após readiness**, janelas de10s, startup máximo30s e exportação posterior limitada180s; sem inferência, IPS ou persistência automática de janelas no P11. Nome novo `p08-poste2-<UTC>-<sufixo único>`, arquivos criados com recusa de sobrescrita. Fontes obrigatórias: captura do sensor, broker, consumidor MQTT e API; trilha PostgreSQL somente leitura para correlação da mensagem. Publicador fornece recibos de envio. Não retirar fonte para obter PASS. API sem eventos só pode ser vazia com cobertura integral de seu intervalo comprovada.
6. Antes da janela: obter decisão explícita do arquiteto, donos das fontes, perfil/hash e chaves públicas autenticadas; reservar essa execução para um único publicador e confirmar que não há publicação concorrente. Planejar até3 mensagens legítimas **novas** com o contrato/identidade/credenciais existentes, uma a cada10s dentro da sessão, identificadas como simulação no recibo. Isso não repete a mensagem aceita e só será executado após coordenação. Sem retenção, sem alteração de tópico, sem shell remoto arbitrário e sem loop infinito. Segredos nunca saem do host nem entram no Git.
7. Capture completo: filtro restrito ao par produtor/broker e TCP1883, PCAP sensível apenas em armazenamento local protegido fora do Git. MQTT em1883 pode revelar autenticação; não versionar PCAP, payloads externos, logs brutos, chaves ou env. Git recebe apenas hashes/recibos sanitizados e resultados de validação.

Não é necessária alteração de topologia para capturar no endpoint. Se for exigido especificamente trânsito e contenção pelo gateway, isso é outro desenho: candidata mínima seria rota específica de ida via10.20.30.1, encaminhamento e retorno específico ao produtor via gateway. Isso altera rede, requer análise de bypass/policy routing/administração e plano de recuperação por console. **Não está autorizado nem preparado para aplicação**; apresentar comandos exatos e inversas somente após inventário decisivo e revisão do arquiteto, sem habilitar forwarding agora.

## Observações que fecharão continuidade, perdas e tempo

- Captura: readiness, PID, heartbeats a cada1s, intervalo efetivo, encerramento normal e estatísticas finais tcpdump. Exigir contador kernel drops presente; zero é requisito local, não prova perda fim a fim. Contadores NIC antes/depois são diagnóstico por interface e não substituem recibos do fluxo.
- Broker: identificar processo/geração, arquivo ou journal real, offsets/cursor de início e fim, tamanho/inode/rotação e retenção. Exportar intervalo integral em bundle autenticado; ausências ou lacunas mantêm UNKNOWN/INCOMPLETE. PUBACK MID é local à conexão, não cursor global.
- Consumidor/API: guardar boot_id, cursor inicial e final, intervalo de journal, perdas/rotação e unidade; enumerar registros entre as fronteiras sem avançar checkpoint antigo. Verificar que cursor final cobre até depois do fim efetivo, sem inferir continuidade a partir de NRestarts0 ou de um evento.
- Publicador e PostgreSQL: correlacionar hashes dos bytes originais/topic, ID, resultado QoS e registro persistido; contar mensagens únicas previstas/aceitas/persistidas e registrar faltantes/duplicadas. Um ID SQL/revisão não é cursor de cobertura temporal. Não somar esses recibos como features oficiais de log.
- Tempo: obter comparação independente entre relógios com incerteza/offset e instante de validade; NTP yes isolado não basta. Windows sem sincronismo continua pendente. Não calcular latência confiável como created_at-sent_at. Não ajustar relógios nesta coleta; registrar desvio/incerteza e bloquear vínculos que não possam ser garantidos.
- Janelas: usar IDs oficiais, hashes de PCAP, sessão/perfil assinados e somente intervalos inteiros dentro da cobertura de todas as fontes; bordas parciais ficam diagnósticas. Sem alterar histórico, inventar fonte vazia, cortar dados para parecer completo ou mapear cursor de outra janela.

## Dependências reais e gate

`backend/p08_p09` usa biblioteca padrão e módulos irmãos para artefatos/lotes/contexto/cobertura; não carrega modelos treinados nem implementa inferência RF/IF. `p08_captura` depende de Linux/tcpdump e utilitários de assinatura conforme a candidata, além do integrador legado e sua cadeia de integração. Instalar a candidata de lote antiga com `apply_staging.py` não instala a captura assinada atual.

Contrato de features: P09 V2 `schemas/feature_schema.json`, nove features de rede `harpisense.if.window.v1`; RF anterior preservado também precisa ser considerado. O Pacote09 reúne RF/IF/XAI/Risk/Policy e demonstração sintética; isso não fornece automaticamente artefatos treinados homologados. Para alimentar gate de inferência: esquema, ordem, unidades, duração de janela e metadados dos **artefatos RF/IF reais**, hashes/versões/proveniência, auditoria numérica P08 e cobertura verificada. Sem metadados do modelo, `model_compatibility=NOT_VERIFIED`.

**As janelas desta retomada não podem alimentar o gate de inferência:** não houve sessão nova, não há prova completa de cobertura/tempo e a compatibilidade com artefatos reais não foi demonstrada. A candidata mantém separadas integridade, cobertura e autorizações; não habilitar inferência/IPS para contornar isso. Coleta válida futuramente não demonstra eficácia de detecção ou mitigação.

## Coordenação e continuidade

`maestri list` continua identificando este terminal como HarpiSense Arquiteto. `maestri ask "HarpiSense Arquiteto"` falhou com No connection; não houve confirmação de janela. O diagnóstico anterior já demonstrou transporte/list funcionais; não repetir diagnóstico de saúde para contornar a conexão ausente. Reporte será tentado novamente com o resumo final. Não executar o ensaio enquanto faltar confirmação explícita de janela/escopo.

Próximo desbloqueio concreto: confirmar sensor Linux no Poste2 e acesso/permissões existentes, ou homologar captura Windows; definir exportadores/fronteiras e limite temporal; conectar o arquiteto como destino distinto e aprovar a janela. Não republicar o aceite histórico nem modificar `backend/p08_p09/` pela Edge.
