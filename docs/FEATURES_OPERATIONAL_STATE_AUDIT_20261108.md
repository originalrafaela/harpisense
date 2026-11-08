# Features, executor e estado operacional — checagem de 08/11/2026

**Não estão todas ativas e funcionando no ambiente em uso.** O teste funcional anterior aprovou fluxos isolados com software real; não comprovou implantação da integração atual no HarpiServer nem ativação de modelos e contenção.

Fonte inspecionada: `integration/initial-auth-20261108`, commit `8d91548`. Inspeção do servidor somente de leitura. Nenhum perfil, conta, serviço, regra de firewall, configuração de VPN ou VM do laboratório foi alterado. Nenhum ataque foi executado.

## Resultado por feature

| Feature | Verificação | Conclusão |
|---|---|---|
| API | HarpiServer com harpisense-p11 ativo, listener 127.0.0.1:8000 e health401 sem credenciais | API em execução e protegida; não equivale a todas as rotas da integração implantadas |
| Microsoft Authenticator / MFA | QR/TOTP passaram no ensaio nativo anterior; rotas mfa/verify e mfa/enrollment/begin retornam404 no servidor atual | Implementado/testado na integração; não ativo pelo contrato novo no HarpiServer. Aplicativo físico do celular não foi ensaiado pelo agente |
| Hash da senha | Repetido teste Argon2id: mesma senha recebe salts e hashes diferentes; verificação correta e compatibilidade scrypt legada | 1 teste aprovado; isso não identifica o algoritmo usado pela instalação antiga do servidor |
| Hash da licença | Emissor possui UNIQUE do SHA256 e testes anteriores de colisão/emissão concorrente | Propriedade implementada e testada em banco isolado; emissor de produção não foi comprovado ativo |
| Configurações de redes/dados | Catálogo da integração oferece presentation, escopo display_name/timezone; campos MQTT/rede podem ser rascunhos/validados | Persistência e aplicação de apresentação testadas. Não há aplicador operacional de redes/VPN/firewall nesse catálogo; salvar não comprova reconfiguração real |
| RF e IF | Código de treinamento/inferência presente; testes científicos treinaram e executaram estimadores reais sobre dados artificiais | Componentes funcionam em teste. Modelos operacionais aprovados/carregados em pipeline contínuo não foram identificados |
| XAI / SHAP | API de leitura montada no runtime da integração; teste científico e composição aprovados; rota de explicações por incidente retorna404 no servidor atual | Leitura/produção em desenvolvimento não comprova XAI disponível nessa instalação |
| TreeExplainer | Teste real reconstruindo saída do RF original antes de calibração | Funciona em teste, sem comprovação de execução contínua em produção; não representa probabilidade calibrada do Risk |
| PermutationExplainer | Teste real da função de RF calibrado e do score operacional IF, com reconstrução/aditividade e vínculo de janela | Funciona em teste; depende de modelos e referências corretos montados no produtor |
| BitNet fornecido | GGUF de 1.187.801.280 bytes com SHA256 exatamente igual ao lock; CLI executa --version | Integridade e executável confirmados. Serviço não ativo nas portas verificadas; integração usa deterministic_only/generation_enabled=false |
| Executor de defesa | Integração declara isolated_simulation_only, not_integrated e bloqueia REAL | Apenas simulação validada. Executor real e contenção real não estão disponíveis nessa composição |
| Modo / estado operacional | 39 testes novos de política/controles/simulação passaram; endpoint de controles do servidor responde404 | Regras funcionam nos testes; modo aplicado do HarpiServer não é observável por esse contrato. Não presumir M1/M2/M3 ativo no servidor |

## Evidência do ambiente em uso

SSH confirmou hostname gateway e WorkingDirectory `/opt/harpisense/staging/p11-postgresql`, com entrada app.py de SHA256 `d8dc01de8ee14ca4daa31d34408882ef2a22a1d7858cad46abdd308bb0e957a9`. Essa composição não é o runtime nativo da integração atual inspecionada. O OpenAPI não anuncia MFA ou controles operacionais; consultas confirmaram:

| Recurso | Resultado HTTP sem credenciais |
|---|---|
| GET /api/v1/p11/health | 401 |
| GET /api/v1/admin-auth/session | 401 |
| POST /api/v1/admin-auth/mfa/verify com corpo vazio | 404 |
| POST /api/v1/admin-auth/mfa/enrollment/begin com corpo vazio | 404 |
| GET /api/v1/security/settings/mode/default | 404 |
| GET /api/v1/activation/status | 404 |
| GET /api/v1/native/status | 404 |
| GET /api/v1/config/catalog | 401 |
| GET /api/v1/p11/incidents/audit-readonly/explanations?incident_revision=1 | 404 |

Nenhuma senha foi tentada. O 401 do catálogo confirma proteção/existência, mas não revela seus aplicadores sem sessão. As ausências de rota são evidência de diferença de implantação, não simples erro de credencial.

API, consumidor MQTT, PostgreSQL18 e Tailscale aparecem em execução. harpisense-firewall e UFW aparecem active/exited, estado compatível com serviços oneshot; isso não comprova um executor dinâmico. A leitura das tabelas nftables exige sudo interativo e não foi concluída. `net.ipv4.ip_forward=0`: o encaminhamento IPv4 entre interfaces segue desligado. Não atestar o percurso roteado IoT nem a contenção com esses resultados.

No Windows local, as portas8000/18000/18080/5174/5176/8091/8092 estavam fechadas. Os processos dos ensaios anteriores foram encerrados intencionalmente; os testes aprovados não deixaram um produto em execução permanente.

## Testes desta rodada e significado

- **7 testes SHAP aprovados:** RF/IF treinados em janelas artificiais; TreeExplainer e PermutationExplainer reais; reconstrução numérica e vínculo de features/janela; CLI e composição. Não usam resultados fictícios dos explainers, mas os dados/modelos são de ensaio. TreeExplainer de IF é recusado explicitamente: comprimento de caminho não equivale ao score operacional negativo de score_samples.
- **39 testes operacionais aprovados:** M1/M2/M3, IDS/SIMULATION/REAL, revisão e perfil histórico, concorrência, aprovação específica, recusa de estado desconhecido, ausência de replay, emergência independente e execução somente simulada. Usam repositórios de memória/fixtures; não modificam o SO. A persistência e os controles via PostgreSQL/HTTP foram também exercitados nas61 verificações funcionais anteriores.
- **1 teste Argon2id aprovado:** salts individuais, verificação da senha correta/errada e transição a partir do hash legado. Não foi consultado hash de uma conta real.

Comandos:

```text
../native-initial-auth/.venv/Scripts/python.exe -m unittest discover -s backend/domain/tests -p test_shap_library.py -v
PYTHONPATH=backend;backend/domain;genai;backend/delivery_tests
../native-initial-auth/.venv/Scripts/python.exe -m unittest test_delivery.DeliveryTests test_control_state.ControlStateTests test_action_review.ActionReviewTests test_operational_state.SnapshotTests -v
../issuer-local-auth/.venv311/Scripts/python.exe -m pytest backend/initial_auth_tests/test_initial_auth.py::test_argon2_individual_salts_and_legacy_scrypt -q
```

## BitNet: pesos presentes não significam geração ativa ou aprovada

Arquivo identificado: `harpia-bitnet/.local-harpia/models/ggml-model-i2_s.gguf`, SHA256 `4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162`, conforme genai/artifacts.lock.json. CLI/servidor correspondem aos hashes registrados na rodada7; CLI informa9918 (390c30775), Clang19.1.5 x64.

Não houve inferência nova nesta rodada. Havia2.855MiB livres no host, abaixo do limiar de início configurado de3.584MiB; as VMs do laboratório foram preservadas. Além disso, genai/RODADA7_VALIDACAO_PATCH.md registra que a última avaliação textual desse runtime/modelo foi reprovada em fidelidade. Esse registro histórico não foi substituído por um simples --version ou hash correto. O backend principal instala HarpIA determinística e declara geração desabilitada.

## Bloqueios antes de testar ataques

1. Implantar e identificar a composição integrada correta no alvo, preservando o administrador e as autenticações técnicas. As rotas MFA/controles/XAI verificadas não estão disponíveis na API em uso.
2. Provisionar versões RF/IF e backgrounds/referências aprovados, com hashes confiáveis, e conectar captura → features → inferência → persistência → explicação → UI. O inventário disponível identifica oito artefatos de desenvolvimento, não modelos operacionais aprovados.
3. Integrar um adaptador executor real por plataforma com autorização, auditoria, verificação de resultado e reversão. M2/M3 não fornecem essa integração e SIMULATED não é MITIGATION_CONFIRMED.
4. Confirmar topologia e percurso legítimo no gateway, inclusive forwarding e regras efetivas, sem comprometer a VPN. Depois comprovar o cenário controlado de detecção/contenção antes de executar a bateria de ataques.
5. BitNet exige serviço carregado, memória adequada, integração real e revalidação de fidelidade; o fallback determinístico não substitui essa comprovação.

**Não considero o conjunto pronto para ataques de detecção/contenção com todas as features anunciadas.** O núcleo funcional testado funciona, mas há diferença de implantação e componentes sem ativação operacional comprovada. Política de perda do autenticador continua pendente. Registro sanitizado: [summary.json](evidence/feature-runtime-audit-20261108/summary.json).
