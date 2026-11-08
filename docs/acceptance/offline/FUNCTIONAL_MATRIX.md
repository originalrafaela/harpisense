# Matriz de percurso funcional — offline Windows e Ubuntu

Branch `audit/native-security-acceptance-20261107`; política/execução interna em `e5ce471`, preparação em `6e3959a`; base protegida `a8fef1f5810ad5077658a29fe2aa407ffd21df6d`. Este documento consolida o aceite, sem substituir os contratos nem editar o trabalho de outras equipes.

## Regra para marcar conclusão

Cada célula Windows/Ubuntu representa **I/C/S/O/U/P**, nesta ordem: incluído no instalador com hash; configurado pelo produto; serviço disponível; operação real executada; resultado consultável na interface; persistência/reconsulta após reboot, quando aplicável. `P` = pendente neste alvo/versão. Fonte, fixture, botão, build ou serviço isolado não marcam nenhuma etapa instalada como aprovada. `NA` só pode ser usado com justificativa do critério, nunca para omitir uma função exigida.

Nenhum novo ensaio instalado offline foi executado nesta revisão. A presença de arquivos ou VM ligada não atesta SO limpo. A inexistência de incidente numa instalação nova pode ser saudável; é diferente de produtor indisponível ou cobertura desconhecida. Serviço de executor disponível nunca substitui autorização M1/M2/M3/evidência/alvo/escopo/validade.

| Função exigida | Windows limpo I/C/S/O/U/P | Ubuntu limpo I/C/S/O/U/P | Fonte/contrato observado e vínculo de aceite necessário |
|---|---|---|---|
| Instalação gráfica offline autocontida | P/P/P/P/P/P | P/P/P/P/P/P | Windows builder tem payload nativo; Ubuntu installer ainda chama apt-get no destino. Sem terminal/download complementar para o usuário |
| API autenticada, PG e migrações/auditoria | P/P/P/P/P/P | P/P/P/P/P/P | `backend/native_server`, delivery, admin_auth; hash payload, readiness e conta durável |
| Admin/senha/TOTP e primeiro acesso | P/P/P/P/P/P | P/P/P/P/P/P | `FIRST_ACCESS_AUTH_CONTRACT_20261107.md` em Backend; modal nome da conta, propósitos separados, emissão só em memória, completed persistido, reset concorrente único e MFA preservado |
| Ativo genérico: cadastrar e consultar | P/P/P/P/P/P | P/P/P/P/P/P | ConfigStore/asset; ID/revisão do cadastro iguais na resposta, PG e UI, inclusive após reboot |
| Mosquitto local TLS/identidades/ACL | P/P/P/P/P/P | P/P/P/P/P/P | Serviço broker instalado automaticamente, LAN testada somente no guest; não inferir LAN a partir de listener loopback |
| Consumidor e telemetria do ativo | P/P/P/P/P/P | P/P/P/P/P/P | CONNECT/SUBACK/publicação/freshness separados. Message ID/projection ID/dados iguais no MQTT, PG e UI |
| Captura/preparação suportada | P/P/P/P/P/P | P/P/P/P/P/P | `edge/capture` existe como CLI/fixtures, não serviço do pacote. Driver/permissões/BPF, seleção de interface/configuração pelo produto pendentes |
| Amostra identificada RF aprovado | P/P/P/P/P/P | P/P/P/P/P/P | Modelo, transformação, ordem/schema/dtype de features, referências e versões do pacote; IDs/hash de entrada no resultado/UI |
| Mesma amostra IF aprovado | P/P/P/P/P/P | P/P/P/P/P/P | Mesma janela/sessão/registro; score/margem/percentil IF nunca chance de ataque |
| Risk/Policy e investigação | P/P/P/P/P/P | P/P/P/P/P/P | Motores canônicos e produtores Backend; registrar fatores/proveniência/cobertura, sem deduzir realidade da amostra |
| Avaliação de incidente | P/P/P/P/P/P | P/P/P/P/P/P | `IncidentDossier.assess` Backend; avaliação separada não aprova nem executa nem muda perfil/origem |
| Aprovação específica de defesa elegível | P/P/P/P/P/P | P/P/P/P/P/P | Hook ActionReview entregue; falta resolver persistido, rota autenticada, projeções e integração UI. M1 manual, M2 Low elegível auto/Medium-Hard manual, M3 política |
| Execução e verificação | P/P/P/P/P/P | P/P/P/P/P/P | Só simulação interna testada. Adaptador REAL/verificador por SO não integrado; ausência de execução = motivo explícito, sem sucesso inventado |
| Revalidação/aplicação de perfil | P/P/P/P/P/P | P/P/P/P/P/P | Mesmo lock e revisão no backend; atividade ativa/pending/unknown bloqueia, histórico fechado não. Perda comunicação não apaga casos |
| Emergência independente | P/P/P/P/P/P | P/P/P/P/P/P | Rota/controle existente; testar enquanto fila/observação indisponíveis, sem habilitar contenção |
| SHAP TreeExplainer real RF/IF | P/P/P/P/P/P | P/P/P/P/P/P | Backend `a3eb885`; calcular com payload instalado, saída RF pré-calibração/IF identificada, histórico SHAPLEY_PERMUTATION preservado |
| SHAP PermutationExplainer real Risk | P/P/P/P/P/P | P/P/P/P/P/P | Saída exata do Risk Engine, referência/modelo/versão/hash. Não substituir por gráfico de fixture |
| Ficha técnica/gráfico/tabela | P/P/P/P/P/P | P/P/P/P/P/P | Mesmo ID/revisão/explanation em todos; trocar para ID sem XAI limpa dados e mostra “Explicação não disponível” |
| HarpIA BitNet LOCAL: geração real | P/P/P/P/P/P | P/P/P/P/P/P | Lock de pesos existe, não prova payload. Runtime binário por SO, pesos, dependências, licença, hash e geração real identificada na ficha |
| BitNet off mantém registros/logs | P/P/P/P/P/P | P/P/P/P/P/P | Desativar geração sem apagar dossiê, SHAP/telemetria/avaliações/logs; nenhuma frase gerada altera registros |
| Configurações persistentes | P/P/P/P/P/P | P/P/P/P/P/P | Aplicar/reconsultar somente capacidades reais; rascunho não equivale a infraestrutura aplicada |
| Cloud backup opcional | P/P/P/P/P/P | P/P/P/P/P/P | Não bloquear primeira instalação, painel ou configuração por ausência de provedor; planejar não equivale a executar backup |

## Evidência separada, sem promoção entre ambientes

| Ambiente | Evidência disponível | O que não comprova |
|---|---|---|
| Prévia 5174 | Preservada; não operada por esta revisão. Portal conectado agora anuncia revisão 5175, não foi usada para inferir estado da 5174 | Runtime instalado, operação real do backend, offline ou reboot |
| Backend nativo descartável Windows de desenvolvimento | `../security-fixture-result.json`: 22 testes; `../security-postgres-result.json`: 8 verificações com PG privado e simulação | Instalação limpa, contenção/verificação reais, geração BitNet, captura real |
| Captura fixtures | `inventory-observed.json`, testes existentes com observações conhecidas/backend simulado | Captura física, travessia LAN, RF/IF operacional, Windows/Ubuntu instalado |
| Ubuntu candidata 3 histórico | Evidências originais em `native-installers/docs/evidence/native-installers/ubuntu-candidate3-trial/` | Offline autocontido: instalou pacotes online. Não estender a SHAP/BitNet/executor nem a nova candidata |
| Windows limpo offline atual | Não executado | Todas as etapas da matriz pendentes |
| Ubuntu limpo offline atual | Não executado | Todas as etapas da matriz pendentes |

## Bloqueios concretos e responsáveis

1. **B01 — Ubuntu offline**: `ubuntu_install.py` chama apt-get update/install. Configurações deve entregar dependências deb transitivas assinadas/versionadas no payload ou solução equivalente sem rede, Python/venv/PG/Mosquitto/CA e bibliotecas nativas. Testar instalação gráfica em Ubuntu Desktop suportado; não extrapolar a outras distros/arquiteturas.
2. **B02 — RF/IF/SHAP**: Backend deve entregar manifesto de modelos aprovados, transformações, features ordenadas/schema/dtype, referências, dependências científicas com hashes por Python/SO e amostra identificada. Commit fonte SHAP não prova modelos/payload instalado.
3. **B03 — BitNet**: `genai/artifacts.lock.json` fixa origem/revisão/hash esperado dos pesos; runtime/pesos ainda não comprovados em ambos os instaladores. Embutir binários/libs e licenças, caminho instalado sem procura/download/build no destino e evidência de geração real. Não usar servidor/modelo da máquina de desenvolvimento.
4. **B04 — Captura**: módulo/Scapy/driver/permissões/configuração/serviço/persistência/UI ainda sem percurso instalado. O filtro padrão é TCP 1883; MQTT local do pacote é TLS 8883. Payload TLS não fornece tópico/identidade/autenticação ao parser. Alinhar captura de metadados e eventos confiáveis do broker, sem reduzir TLS.
5. **B05 — Executor/verificador**: simulação isolada não entrega contenção operacional. Inventariar adaptadores reais, primitivas/escopo, privilégios mínimos, TTL/reversão, verificação e auditoria por SO. Não ativar adaptador apenas por embutir modelo/serviço.
6. **B06 — Alvos**: VMX/discos existentes não garantem SO limpo ou snapshot atual. Candidata 3 é protegida. Nenhuma VM foi iniciada, reiniciada ou teve rede alterada por este coletor. Disponibilidade, RAM, login/GUI e clone limpo dedicado ainda precisam ser confirmados.
7. **B07 — Primeiro acesso**: Backend publicou `071d052` (`feat(auth):persist-first-access-and-purpose-bound-code-rotation`), confirmado por leitura do HEAD. Há alterações posteriores em runtime/contrato naquela worktree; não foram copiadas. Commit fonte deve ser revisado e integrado com UI; persistência `completed`, separação de finalidades e teste concorrente ainda não comprovados nos instalados offline.
8. **B08 — Vínculos e produtores**: falta integração ActionReview/projeções/autoridade, contexto exato/autenticado, auditorias avaliação/aprovação/resultado/verificação, modo histórico e UI. Fonte Backend `dd7d813` é inventariada, não incorporada automaticamente nesta branch.

## Protocolo de ensaio futuro autorizado, exclusivamente guest identificado

1. Fixar manifesto de cada plataforma: SHA do instalador e de todos os componentes/pesos/modelos/dados. Conferir licenças e dependências por SO; nenhum segredo no manifesto. Não iniciar instalação enquanto B01–B05 não tiverem entrega concreta.
2. Registrar UUID/VMX/snapshot/SO-build, inventário de software e ausência de Docker/Desktop/WSL/VS Code/checkout. Snapshot limpo dedicado; nunca restaurar nem reinstalar sobre a candidata 3.
3. Transferir instalador final antes do isolamento. Configurar **somente** guest em segmento de ensaio LAN sem saída WAN e sem alterar host/VPN/rotas/firewall do usuário. NAT atual não comprova offline. Provar LAN broker/publisher e ausência de saída IPv4/IPv6/DNS/proxy, com registro do hipervisor/rede isolada; preservar essa configuração durante instalação e reboot.
4. Operador só abre instalador, cria admin/senha/MFA/guarda códigos e configura cenário pela UI. Não usar checkout, pip/npm/apt online, busca de pesos, shell para iniciar serviço ou script manual. Coleta externa do laboratório pode observar SO/PG/rede sem preparar o produto ou servir dependência a ele.
5. Antes/depois reboot: identidade/boot ID distintos, mesmas configurações/conta/IDs, autostart/readiness, painel por atalho e login admin. Registrar estados individualmente: componente incluído, configurado, serviço pronto, operação real, UI e persistência.
6. Executar ativo genérico/telemetria MQTT com message ID; conferir o mesmo registro no PG/UI. Amostra identificada percorre RF+IF/SHAP e resultado UI do instalado, sem alegação de tráfego real. BitNet deve gerar texto real identificado com hash/runtime locais; off preserva estruturados e logs.
7. Segurança em cenário de ensaio aprovado: avaliar não executa, aprovação específica, revalidação e registros separados; simulado permanece simulado. Captura real legítima e aplicação de defesa são aceites distintos e requerem infraestrutura/escopo/autoridade reais. Kali permanece separado; amostra nunca autoriza contenção.
8. Não capturar/publicar QR, segredo TOTP, código original, senha, grant, token ou DSN. Confirmar hashes/uso/gerações no banco e comparar logs/errors/cache sem divulgar os valores. Publicar apenas fatos sanitizados e falhas, por função/plataforma/versão.
