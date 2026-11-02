# Aplicador de apresentação — contrato e recuperação

Escopo único: `display_name` e `timezone` de exibição do HarpiSense. Reutiliza
config.document/config.proposal v1, ConfigStore, PostgreSQL, sessão e throttle
administrativos existentes. Não há catálogo de ações, autenticação, schema SQL
ou banco alternativos. Migrações 001/002 permanecem byte a byte inalteradas.

O documento aplicado deve conter **exatamente os dois parâmetros**. Nome usa
os limites do schema existente (1–100 caracteres, sem controles) e não pode ser
apenas espaço. Fuso deve ser aceito por Python ZoneInfo; a interface também
verifica Intl.DateTimeFormat antes de enviar a aplicação. Timestamps originais
continuam em seus registros; conversão ocorre apenas ao apresentar o instante.
Valores sem offset explícito são preservados, sem inventar seu fuso de origem.

## Composição explícita

```python
app = build_candidate_app(
    installation_id=installer_identity,
    capabilities=trusted_capabilities,
    allowed_origins=exact_frontend_origins,
    technical_credentials=existing_technical_credentials,
    presentation_directory=installer_private_persistent_directory,
)
```

O diretório é fornecido pelo instalador, exclusivo dessa instalação, persistente
e com acesso restrito ao serviço/operador. Não vem do navegador. Todas as instâncias
da mesma instalação devem usar o mesmo diretório. Nenhuma migração ou conta é
criada pelo bootstrap. Sem presentation_directory, o comportamento anterior fica
preservado: nenhum aplicador exposto. Não ativar automaticamente na VM.

Arquivos: presentation.json é a configuração materializada que o consumidor da
aplicação realmente carrega; presentation-journal.json contém alvo, snapshot
anterior, operação, revisão, fingerprint e fence para recuperação. Não são outra
fonte de propostas ou banco. Registry, revisões, autorização, recibos e auditoria
continuam no PostgreSQL. Antes da primeira aplicação, baseline explícito de
apresentação é HarpiSense/UTC, sem revisão efetiva; não é o fuso do sistema operacional.

## HTTP e autorização

Rotas adicionais quando o aplicador está instalado, sob a sessão/origem existentes:

| Rota | Contrato |
| --- | --- |
| GET /api/v1/config/presentation | parâmetros consumidos, revisão/fence/hash, verified/status/last_result, instante original e sua exibição |
| POST /api/v1/config/proposals/{operation_id}/apply | expected_revision inteiro e current_password; ambos obrigatórios, sem propriedades extras |

Aplicar exige sessão Bearer administrativa válida **e reautenticação da senha
atual em cada solicitação**, usando a mesma conta/hash/throttle/auditoria. Não é
um segundo login nem um token alternativo. A conta continua singleton e o ator
estável admin-account-1. Não se afirma MFA: permanece indisponível. A senha é
limpa do campo ao enviar, não é armazenada no progresso, journal ou logs.

Não existe booleano `authorized` enviado pelo cliente, caminho de arquivo, comando,
recibo ou endpoint de confirmação fornecido pelo navegador. Basic técnico não
autoriza. Sem sessão: 401; sem senha: 422; senha incorreta/origem recusada: 403;
concorrência/revisão antiga/recuperação pendente: 409; escopo inválido: 422.
Respostas mantêm no-store. O proxy só adiciona GET presentation e POST apply
no UUID da proposta; não abre `/config/apply` genérico nem CORS.

Resposta de execução é um resultado de domínio: HTTP 200 pode conter status
APPLIED, FAILED ou RECOVERY_REQUIRED. O frontend deve ler status e verified;
200 sozinho não é sucesso. Um retry de operação FAILED retorna FAILED, sem
reaplicar. Nova tentativa após rollback confirmado exige nova proposta.

## Transições e idempotência

1. Validar a proposta pelo mecanismo existente. Aplicador recusa qualquer outro
   parâmetro, inclusive a remoção implícita de grupo previamente efetivo sem aplicador.
2. Lock advisory de sessão por instalação serializa aplicadores/reconciliadores.
   begin_application persiste intenção APPLYING, revisão e fence. A escrita do
   artefato verifica active_operation/fence sob o lock de linha do registry.
3. Journal com snapshot anterior é sincronizado antes do efeito; arquivos são
   trocados atomicamente. Consumidor lê o artefato e executa a conversão ZoneInfo.
   Verificador compara valores, revisão, fence/hash e resultado da apresentação.
4. Somente após isso record_verified registra recibo interno config-registry,
   document_fingerprint e observação; confirm_application avança a revisão efetiva
   e audita APPLIED. Nenhum recibo é aceito da interface.
5. Identidade idempotente é operação UUID + revisão imutável, já reservada pela
   proposta. Retry APPLIED confirma novamente o consumo e não repete efeito nem
   eventos APPLYING/VERIFIED/APPLIED. Reautenticação continua auditada em cada retry.
   Se a revisão já foi substituída, o retry conflita em vez de afirmar sucesso antigo.

GET current acrescenta proposed_operation_id, presentation e
applicability=presentation_only. Catálogo informa applicators=[presentation] e
application_scope=[display_name,timezone]. State=applied_verified refere-se ao
snapshot de apresentação, **operational=false permanece**. MQTT/captura/modelos/
defesa, dispositivos, perfil e backup não são configurados por este resultado.

## Falha e recuperação

Se ocorrer falha após intenção/efeito, restaurar o snapshot anterior e fazer o
consumidor real relê-lo. Somente com correspondência ao snapshot efetivo anterior
do registry e read-back positivo, finish_recovery registra FAILED com código
PRESENTATION_ROLLBACK_VERIFIED, mantém a revisão efetiva anterior, libera a
instalação e invalida workers antigos. Isso não usa no_external_effects=True:
efeitos ocorreram e foram revertidos. Recibos/auditoria anteriores são preservados.

Se a restauração/verificação não puder ser confirmada, registrar RECOVERY_REQUIRED,
reter exclusão e invalidar o fence. Consumo aparece unknown/verified=false;
frontend não adota os valores incertos, informa exibição não confirmada e bloqueia
novas aplicações. A revisão efetiva histórica não é prova de consumo atual.

Reinício com journal pendente tenta **restaurar o anterior**, não repetir o alvo.
Se confirmação já tiver sido gravada como APPLIED, verifica e conserva o alvo;
nunca o desfaz por uma falha posterior ao commit. Journal divergente do registry,
snapshot ausente/incompatível, corrupção ou perda de acesso não liberam a instalação.

Procedimento local de recuperação do operador confiável:

1. Impedir novas aplicações nesse serviço e preservar cópias/hash dos dois arquivos,
   da auditoria e dos recibos. Corrigir a causa de I/O/permissão/espaço disponível.
   Diretório deve ser o mesmo da aplicação; não copiar snapshot de outra instalação.
2. Com journal íntegro, reiniciar o bootstrap aprovado ou executar no contexto
   interno do serviço `PresentationApplicator(store, installation_id, directory).recover()`.
   Conferir `observe().verified`, GET presentation/current e evento de recuperação.
3. Confirmado rolled_back: nome/fuso/revisão do consumidor devem corresponder à
   revisão efetiva anterior e active_operation ficar vazio; operação falha permanece
   FAILED na auditoria. Para reaplicar, criar e validar outra proposta.
4. Se continuar unknown, manter bloqueado e conservar evidências. Journal perdido
   ou corrompido exige reconciliação específica com backup da mesma instalação;
   não editar status/fence/recibos no SQL, apagar o journal ou forçar APPLIED.

Antes de implantação futura, incluir esses arquivos/diretório e seus controles de
acesso no backup/ensaio de restauração, além do PostgreSQL. Os testes desta rodada
cobrem reinício de processo e falhas controladas, não perda física de disco/energia
nem filesystem distribuído. Nenhum rollback de banco inteiro é necessário para
desfazer apresentação. Sem implantação remota nesta entrega.
