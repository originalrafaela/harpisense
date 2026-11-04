# Integração e recuperação — candidata administrativa

Não executar na VM sem coordenação do arquiteto. Branch `feat/admin-bootstrap-mfa`,
base `9d35906`. O bootstrap compartilhado não foi alterado. Contrato frontend:
[ADMIN_MFA_CONTRATO_CANDIDATO.md](ADMIN_MFA_CONTRATO_CANDIDATO.md).

## Preparação do instalador

1. Reutilizar a instalação PostgreSQL/backend e o mecanismo de configuração já
   aprovado. Preparar DSN, identidade da instalação, origens HTTPS explícitas e
   credenciais técnicas separadas. Não criar credenciais humanas default; nunca
   transformar senha de API, banco, MQTT ou agentes em senha administrativa.
2. Instalar `backend/delivery/requirements.txt` e
   `backend/admin_auth/requirements-mfa.txt` no ambiente do backend. Não exige
   Pillow ou serviço externo para QR; o SVG é gerado localmente.
3. Em janela coordenada, fazer backup verificável e registrar contagem/recibo das
   projeções e identidade existente. Aplicar `001_admin_auth.sql` **somente se a
   autenticação existente ainda não foi instalada**. Aplicar explicitamente
   `002_admin_mfa.sql` no mesmo banco. A segunda é idempotente e aditiva; não
   executar SQL automaticamente no startup ou reaplicar 001 sobre instalação existente.
4. Sob usuário de serviço/instalador confiável, criar diretório local 0700 fora do
   repositório, raiz web e backup do banco. Gerar uma chave Fernet uma única vez.
   O helper abaixo exige Linux, dono atual, arquivo 0600 e não sobrescreve arquivos.
   Distribuir a chave ao processo backend por arquivo protegido, sem gravá-la no DB.
5. Somente sem conta existente, emitir grant bootstrap local de 10 minutos (máximo
   15 via API Python do instalador). Entregar o arquivo apenas ao operador autorizado,
   localmente. Não imprimir seu conteúdo nem incluir em argumentos, URL ou logs.
   Um grant reemitido invalida o anterior; conta criada impede novo bootstrap.
6. Na instalação existente **não emitir bootstrap**, não recriar conta, não resetar
   senha nem revogar sessões. Oferecer adesão por sessão + senha atual. Verificar
   continuidade antes de concluir cadastro e confirmar novo login de duas etapas
   após a ativação. Obrigatoriedade nasce apenas na confirmação voluntária.

Exemplo de comandos do helper (caminhos ilustrativos; sem segredos em argumentos):

```sh
export PYTHONPATH=backend:backend/domain:genai
python -m admin_auth_ops.mfa_local key --key-file /private-install/admin-mfa.key
python -m admin_auth_ops.mfa_local bootstrap --key-file /private-install/admin-mfa.key --grant-file /private-install/admin-bootstrap.secret
```

`DATABASE_URL` é herdada do mecanismo privado existente do instalador. O diretório
`/private-install` deve existir e ser 0700 antes dos comandos. Nunca copiar a chave
junto com dump PostgreSQL. Backup da chave deve ter custódia e criptografia separadas.
O helper não aplica migrações, não reinicia serviços nem edita o bootstrap.
No frontend, o administrador digita o grant no corpo do formulário local autorizado;
o operador remove o arquivo privado após consumo/expiração. Nenhum cadastro público.

## Ponto de integração isolado

No ponto onde a composição candidata já chama `install_admin_auth`, o arquiteto
substitui **essa chamada**, sem instalar os dois provedores. Depois de P11/HarpIA/
controls e antes de `install_config_api` e antes de atender requisições:

```python
from pathlib import Path
from admin_auth.candidate import install_candidate_admin_auth

auth = install_candidate_admin_auth(
    app, dsn,
    protection_key=Path(installer_private_key_path).read_bytes().strip(),
    allowed_origins=installer_allowed_origins,
    technical_credentials=installer_technical_credentials,
)
```

O helper Linux `private_file` permite validar dono/mode do arquivo antes da leitura.
O integrador deve fornecer **todas** as credenciais técnicas relevantes à checagem
de separação, inclusive as não expostas pelas variáveis já reconhecidas pela base.
`app.state.admin_auth`, `require_admin_session` e `require_admin_token` permanecem
compatíveis com o gerenciador. Não alterar rota técnica de ingestão: preserva Basic
e token de serviço; demais consumidores administrativos usam sessões existentes.

Não basta aplicar 002 mantendo a factory antiga: isso só prepara o banco. O ponto
acima é opt-in e exige aprovação. Depois que alguma conta confirmar MFA, **não
retornar à factory antiga**, pois ela não aplica o segundo fator. Correção deve ser
progressiva com o módulo MFA e chave correta. Não apagar as tabelas para recuperar
acesso. Não restaurar backup antigo sem reconciliar revisões, sessões e códigos já
consumidos, pois isso pode reintroduzir credenciais revogadas.

## Recuperação controlada

Com senha e um código de recuperação: seguir `/login` → `/mfa/recover` →
cadastro/confirmar novo TOTP. O código é consumido imediatamente e as sessões são
revogadas. Se perder a resposta, usar outro código ou o processo local; não reutilizar
o consumido. Até confirmar o novo autenticador, o antigo permanece ativo.

Sem autenticador nem códigos: o operador local autorizado deve verificar a identidade
do administrador por procedimento externo e registrar a aprovação na operação.
Só então emitir grant `recover`, no mesmo helper/arquivo privado:

```sh
python -m admin_auth_ops.mfa_local recover --key-file /private-install/admin-mfa.key --grant-file /private-install/admin-recovery.secret
```

Essa operação não tem endpoint de emissão público, não altera senha, não remove MFA
e não revoga sessões só por emitir o arquivo. Grant expira em 10 minutos, é de uso
único e vinculado à revisão atual das credenciais. O administrador usa grant + nome
e senha existentes em `/local-recovery`. Só após essa validação as sessões são
revogadas e é emitida autorização limitada para cadastrar/confirmar novo TOTP.
O novo conjunto de recuperação substitui o anterior. Não se emite sessão de bypass.

Sem senha conhecida: esta candidata **não** implementa reset nem bypass. O arquiteto
deve coordenar recuperação de identidade e credenciais como operação separada,
sem desabilitar MFA nem reutilizar a senha técnica. Se a chave de cifragem for perdida,
restaurar sua cópia privada separada primeiro; erro de decifragem falha fechado
(`MFA_KEY_UNAVAILABLE`). Não gerar uma chave substituta como se fosse a original.

## Verificação e testes isolados

Criar PostgreSQL descartável, em loopback, banco obrigatoriamente `auth_fixture`.
Não definir as variáveis de teste com DSN operacional. Exemplo de ambiente local
(senha abaixo é exclusivamente da fixture descartável):

```sh
docker run -d --name harpisense-admin-mfa-fixture -p 127.0.0.1:55446:5432 -e POSTGRES_DB=auth_fixture -e POSTGRES_USER=auth_fixture -e POSTGRES_PASSWORD=mfa-isolated-fixture-only postgres:18.6
export ADMIN_MFA_TEST_DATABASE_URL=postgresql://auth_fixture:mfa-isolated-fixture-only@127.0.0.1:55446/auth_fixture
python -m unittest discover -s backend/admin_auth_tests -p test_mfa.py -v
```

Para incluir os controles reais de arquivo 0600/0700 do helper Linux, há uma imagem
de teste que recebe a worktree somente para leitura e compartilha apenas a rede
da fixture PostgreSQL. A partir da raiz da worktree, em Linux:

```sh
docker build -t harpisense-admin-mfa-tests -f backend/admin_auth_tests/Dockerfile.mfa .
docker run --rm --network container:harpisense-admin-mfa-fixture -e ADMIN_MFA_TEST_DATABASE_URL=postgresql://auth_fixture:mfa-isolated-fixture-only@127.0.0.1:5432/auth_fixture -v "$PWD:/work:ro" harpisense-admin-mfa-tests
```

Os testes resetam exclusivamente as tabelas da fixture, validam o nome do banco
antes de fazê-lo e nunca usam `DATABASE_URL` como fallback. A suíte legada
`test_admin_auth.py` deve rodar em fixture separada, sem tabelas MFA (ou schema
isolado), pois seu TRUNCATE original não conhece as novas FKs. Não modificar a
suíte legada ou desativar restrições para contornar essa separação.

Na integração coordenada verificar: projeções/ingestão inalteradas; login legado
antes da adesão; QR somente com desafio autorizado; código inválido sem ativação;
confirmação revogando sessões anteriores; login agora em duas etapas; logout;
código de recuperação consumido uma vez; tentativas limitadas e auditoria sanitizada.
Não disparar ações de defesa ou alterar fila/gerenciador para validar autenticação.
