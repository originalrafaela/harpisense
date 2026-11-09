# Atualização da composição do gateway existente

Este pacote atualiza **somente** `harpisense-p11.service`, mantendo PostgreSQL,
MQTT, gateway, VPN, firewall e a identidade administrativa existentes. Não é o
instalador para uma máquina nova e não emite licença para a instalação antiga.

`build_release.py --output CAMINHO` monta código, frontend já compilado,
migrações e manifesto SHA256. Não inclui `.env`, chave MFA, banco ou pesos.
O destino esperado é `/opt/harpisense/staging/p11-postgresql`; o checksum do
bootstrap antigo é conferido antes da preparação e da aplicação. A release fica
em diretório privado separado; não substitui `app.py` nem o venv antigo.

## Ordem e limites

1. Extrair em diretório 0700 pertencente a `harpiserver`, criar `venv` separado e
   instalar `requirements.txt` a partir desse diretório. Não editar o venv ativo.
2. Executar `venv/bin/python upgrade_gateway.py smoke`: testa frontend compilado,
   presença/proteção de MFA/XAI e criação/verificação Argon2id em Linux, sem banco.
3. Um operador executa **com sudo** `venv/bin/python upgrade_gateway.py deploy`.
   O motivo do privilégio é concreto: backup completo do PostgreSQL incluindo
   sequências de configuração, migração sob proprietário e reinício do systemd.
   A conta de serviço não recebe privilégios adicionais de DDL ou de backup.
4. `deploy` faz backup completo privado, ensaia restauração/migração num cluster
   descartável com socket Unix privado e sem TCP, verifica preservação da conta
   e das projeções e testa as rotas. Só depois aplica no banco real e instala o
   drop-in systemd `initial-auth.conf`. Verifica MFA/XAI no OpenAPI após reiniciar.
   Falha no ensaio interrompe a implantação. Falha na partida/checagem de rotas
   remove somente o drop-in criado e reinicia o serviço original. O esquema
   aditivo permanece; as senhas não são redefinidas. O banco inteiro nunca é
   restaurado automaticamente sobre dados em uso.

Migrações: `delivery/{001_local,002_operational_authority,003_incident_assessment,
004_activity_decision_snapshot,006_action_review}.sql`,
`admin_auth/{002_admin_mfa,003_password_reset,004_first_access,005_initial_auth_v2}.sql`
e `config_manager/003_assets.sql`. A migração inicial de identidade 001 existente
nunca é repetida. O administrador entra com a senha atual, recebe desafio de
cadastro MFA e só obtém sessão administrativa após confirmar TOTP. Sessões sem
MFA são revogadas. Cadastro inicial permanece bloqueado nesta composição legada.

A chave Fernet fica em `.initial-auth-private/admin-mfa.key`, fora do banco,
do dump e do pacote. Não apagá-la nem regenerá-la depois de cadastrar MFA.
Diretório 0700 e arquivo 0600, pertencentes ao usuário do serviço; proteção por
permissões do SO, sem promessa de TPM ou resistência a um administrador do host.
O backup é sensível e fica apenas no servidor, também com permissões privadas.

## BitNet

O backend agora tem ligação explícita com `harpia.client.Client` e o frontend
aceita `harpia.mode=bitnet_optional`, contrato 1. O enablement exige
`HARPISENSE_BITNET_ENABLED=1`; o endereço `HARPIA_URL` é restrito a HTTP em
127.0.0.1, sem redirects nem proxy do ambiente. Na release do gateway o valor é
derivado de `settings.json.bitnet_enabled`, inicialmente `false`.

`generation_enabled` informa configuração; **`model_ready` informa modelo de
fato carregado** por `/ready`, não apenas processo HTTP vivo. A geração é somente
texto `bitnet_unverified_text`, sem autoridade sobre Risk/Policy/execução.
Identidade e revisão são conferidas e a explicação determinística é mantida como
referência. Falha ou timeout preserva a explicação determinística completa.

Não habilitar o modelo por simples troca de flag: o gateway inspecionado tem
1.594 MiB de RAM total, enquanto a política do runtime exige 3.584 MiB livres e
3.072 MiB de margem de commit. O host Windows também estava abaixo do limiar.
É necessário provisionar host com memória suficiente, runtime da plataforma,
pesos verificados e serviço loopback. A última avaliação textual registrada
continua reprovada; texto gerado não deve ser promovido a evidência verificada.

Não foi aprovada política de perda do autenticador. Licença e código de
recuperação continuam sem poder desativar ou recadastrar MFA.
