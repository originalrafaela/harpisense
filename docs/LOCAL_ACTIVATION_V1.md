# Ativador instalado — contrato fadebd9

Biblioteca: `backend/local_activation`. Base `9cd930c`, branch `feat/local-activation`.
Não altera captura, defesa, gateway, serviços ou banco. Composição/empacotamento
é responsabilidade de `feat/native-initial-auth`; emissor real é de Backend Data.

## Integração

```python
from backend.local_activation.client import ActivationClient, HTTPSIssuer
from backend.local_activation.initial_access import create_initial_access
from backend.local_activation.transport import NativeTransport

client = ActivationClient(private_directory, protector, issuer_public_keys,
                          HTTPSIssuer(packaged_issuer_url), platform)
# Executar sob a identidade do serviço; activation_key vem de arquivo privado/memória.
client.activate(activation_key)
transport = NativeTransport('127.0.0.1', 18080)
initial_access = create_initial_access(
    client, administrator_state=read_account_state,
    retry_action=retry_with_privately_stored_license,
    native_transport=transport.authorized)
# Injetar initial_access no backend; ausência continua fail-closed.
# Servir transport.wrap(app) SOMENTE no listener nativo exclusivo:
# uvicorn.run(..., host='127.0.0.1', port=18080, proxy_headers=False)
```

O wrapper produz selo objeto em `request.scope`, após verificar peer loopback,
endereço real do listener e ausência de headers de proxy. Nenhum header produz o
selo. Não usar esse wrapper no listener de rede ou atrás de proxy. Cookie separado,
obtido apenas por IPC autenticado, continua obrigatório mesmo no listener local.
Host exato e Origin exata são obrigatórios nas mutações; status nunca contém segredo.
`require` retorna somente license_id/installation_id, nunca Bearer administrativo.
`invalidate()` deve ser chamado ao confirmar MFA; estado ready também recusa sessões.
Conta migration_required mantém login backend preexistente e não libera novo cadastro.

`WindowsHandoff(name, adapter, service_sid, installer_sids).start()` cria pipe
com ACL explícita, rejeita cliente remoto e valida SID por impersonação.
`UnixHandoff(path, adapter, allowed_uids).start()` exige diretório privado do dono,
socket 0600 e SO_PEERCRED. `.close()` encerra somente o endpoint da própria
instância. Endpoint existente só é removido sob lock exclusivo, se for socket
privado do mesmo dono, recusar conexão e conservar o mesmo inode na revalidação.
Listener ativo, symlink, arquivo comum e socket com permissão pública são preservados
e recusados. O launcher Ubuntu precisa executar IPC como o dono/root;
somente incluir UID na lista não concede acesso a um socket 0600.

Cliente instalador: `request_windows_handoff(..., expected_server_sid=...)` ou
`request_unix_handoff(..., expected_server_uid=...)`. Ambos autenticam servidor.
Retorno sensível só em memória, passado diretamente a
`launch_first_use(handoff, chromium_executable=packaged_chromium)`.
Essa função cria navegador isolado via Playwright, instala cookie HttpOnly,
SameSite=Strict, sem domínio de compartilhamento (hostname literal), Path
`/p11-api/api/v1/`, Secure sob HTTPS. HTTP é permitido apenas em loopback literal.
Não usar webbrowser/xdg-open, grant manual, query/fragment, stdout ou argv com token.
CLI `python -m backend.local_activation --ipc PATH --server-identity SID_OU_UID
--chromium PATH` recebe apenas identificadores públicos/caminhos.
Launcher deve rodar na sessão gráfica do usuário, nunca iniciar Chromium como root.
Em Ubuntu, separar aquisição privilegiada do handoff e lançamento gráfico em memória.
Empacotar Chromium e dependências offline; não baixar browser em runtime.

As sessões duram 900s, guardam somente hash persistido protegido fora do PostgreSQL,
vínculo instalação/receipt/usuário local e nonce da instância. Reinício invalida
sessões antigas e exige novo IPC. Uma sessão IPC pode tentar ativação pendente,
mas só permite cadastro após recibo verificado e posse da chave correspondente.

## Proteção e contas

Windows: `WindowsDPAPI` usa CurrentUser e UI_FORBIDDEN; sem fallback LocalMachine.
Provisionar identidade e chave Fernet TOTP sob MESMO SID da API que as consumirá.
Instalador administrativo não pode gerar os blobs sob sua própria conta. Diretório
precisa ACL privada com SID API/SYSTEM; não conceder ao serviço PostgreSQL,
MQTT, gateway ou usuários interativos. O processo API autorizado pode ler segredos
em memória. SYSTEM/administrador com controle do processo permanece no limite de confiança.

Ubuntu: `SystemdCredential(path)` lê exatamente 32 bytes de arquivo 0400/0600
sem symlink. Provisionar chave por stdin a `systemd-creds encrypt --with-key=host`,
persistir só o resultado cifrado, configurar `LoadCredentialEncrypted` SOMENTE
na unit API. PID1/root e a API recebem acesso; PostgreSQL deve usar OUTRA conta
e não receber a credencial. Root pode ler memória/chave host. O empacotamento
antigo usa harpisense para API e PostgreSQL: não satisfaz esse isolamento.
Não usar `$CREDENTIALS_DIRECTORY` como argumento de segredo; apenas o caminho é público.

Backend: `provision_totp_key(path, protector)` cria envelope protegido exclusivo;
`load_totp_key(path, protector)` fornece bytes Fernet para `MFAAdminAuth`.
Identidade e chave TOTP têm domínios distintos; troca de arquivos é recusada.
Excluir estado protegido, credencial cifrada e chave host das rotinas de backup DB.
Nenhum segredo privado é retornado por status ou incluído em exceções do protocolo.

## Evidência e limites (08/11/2026)

Comando Windows: `../native-installers/.venv/Scripts/python.exe -m unittest
discover -s backend/local_activation_tests -v`: 11 testes passaram inicialmente.
Usa DPAPI nativa; emissor é fixture Python explícita, não o servidor PostgreSQL real.

| Fronteira | Evidência atual |
|---|---|
| Windows DPAPI | roundtrip, adulteração rejeitada e ausência de plaintext no blob |
| Reinício offline | nova instância do cliente, mesmo estado, emissor removido: ativo |
| Receipt alterado/copied | assinatura alterada ou falta de chave correspondente: inválido |
| Segunda instalação/licença | fixture recusa vínculo diferente; não é segunda máquina física |
| Expiração/replay | cliente não assina challenge expirado; fixture recusa repetição |
| Resposta perdida | retoma mesma identidade e mesmo recibo persistido no emissor fixture |
| Rede/browser | selo falso, peer remoto, proxy, cookie ausente, Host/Origin e TTL recusados |
| Administração sem MFA | adaptador não emite Bearer; teste real é de Backend Data, pendente |
| Ubuntu | implementação disponível; execução nativa/systemd pendente |
| VMware Windows/Ubuntu | teste em VM limpa e restart SO pendentes |
| Logs/argv/URLs | código não imprime corpos/segredos; captura real instalador/browser pendente |

Cópia do instalador gera nova identidade quando provisionado: nenhum estado privado
é incluído no pacote. Copiar SÓ recibo falha sem chave vinculada. Copiar recibo e
blobs para outro usuário/máquina depende da proteção OS; teste cruzado real pendente.
Clonagem INTEGRAL de VM pode incluir perfil DPAPI, chave host systemd e identidade;
NÃO há alegação de resistência. Não existe binding TPM/vTPM implementado.
Não declarar aceite de VM, browser real ou integração servidor antes dessas rodadas.

## Complemento lifecycle Unix e navegador (08/11/2026)

O Gerenciador definiu `state.handoff_directory=/run/harpisense-api`, com
`RuntimeDirectory=harpisense-api`, `RuntimeDirectoryMode=0700` e
`RuntimeDirectoryPreserve=no` na unit systemd. Isso mantém socket fora do estado
persistente. Esta biblioteca também recupera conservadoramente um socket stale
após morte do processo, inclusive quando não houve limpeza pelo supervisor.
Não modifica runtime/units do Gerenciador.

`UnixHandoff` mantém flock durante toda a vida do listener. `close()` compara
dispositivo/inode antes de unlink e não remove endpoint substituído por outra
instância. O arquivo de lock permanece privado, sem segredos, e o kernel libera
o lock quando o processo morre. Fechar a janela durante navegação ou espera
termina o launcher normalmente; falha real de driver ainda é propagada.

Validação complementar executada:

* Debian WSL, Python 3.13: **5 testes Linux reais passaram**, incluindo processo
  filho encerrado por `os._exit(71)`, recuperação do inode stale, preservação de
  listener ativo com/sem flock, preservação de endpoint substituído em `close()`
  e recusa de arquivo comum/symlink/socket público. Comando: `python3 -m unittest
  backend.local_activation_tests.test_unix_ipc -v` na worktree.
* Windows: descoberta local executou **14 testes com sucesso e pulou os 5 testes
  Linux**. Os 3 testes novos de navegador usam driver fixture para simular
  fechamento da página/janela e falha de driver; não executam Chromium.
* Para testar IPC sem instalar cryptography no Debian, o carregamento de identidade
  e verificador criptográfico passou a ser sob demanda. Não há alteração de algoritmo
  ou fallback: operações criptográficas continuam exigindo a dependência instalada.

Não se repetiram os 17 testes de integração do Backend. Debian WSL não comprova
Ubuntu/systemd, reboot do SO, VMware ou instalação limpa. Chromium real e integração
do `RuntimeDirectory` continuam sujeitos ao aceite do pacote do Gerenciador.
