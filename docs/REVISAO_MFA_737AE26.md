# Revisão do contrato candidato MFA

Hash revisado: `737ae26a098588f2c2bbdb953bee1514b1a1fb95`, posterior a
`3b5aa70`, na worktree exclusiva `admin-bootstrap-mfa`. Revisão de fonte,
OpenAPI e recibos publicados; não houve novo ensaio MFA, cherry-pick ou implantação.

O delta de runtime é a instalação do descritor OpenAPI pela candidata. O novo
`http_contract.py` descreve as respostas existentes; não cria outra autenticação
nem altera a serialização das respostas. O SHA256 do OpenAPI publicado foi
conferido: `8a135dc91ed0f027f3013e666c3e7eae813a82245eef7d6bd67ac00ac9b65c62`,
igual ao dos recibos do Backend.

Contrato aceito como base **candidata para integração isolada do frontend**:

- `/login` retorna sessão `AdminSession` **ou** `MFAChallenge` com next_step e
  validade. Desafio nunca deve entrar como Bearer administrativo ou abrir P11,
  configuração, auditoria ou controles. Somente access_token de sessão completa.
- Bootstrap/recuperação local retornam desafio de cadastro; confirmação do cadastro
  retorna sessão e dez recovery_codes. QR/chave e códigos têm exibição privada,
  sem persistência em logs/localStorage pela camada frontend.
- `/mfa/recover` retorna desafio para novo cadastro, sem acesso direto. Conta
  existente segue pela adesão opt-in; a candidata é instalada depois de P11 e
  controles e antes da API de configuração, substituindo o instalador legado.
- Bearer/Authorization e CORS de origens explícitas permanecem; sem nova camada
  cookie. Erros estruturados e Cache-Control no-store; email recovery indisponível.

O Backend publicou 258 verificações HTTP da instalação nova e 65 da transição de
conta existente, incluindo preservação antes da confirmação, revogação posterior,
reinício/chave restaurada e recuperação. Esses números são **recibos do Backend**,
não testes repetidos pelo integrador nem eficácia de segurança estatística.

Não foi identificada incompatibilidade contratual com P11 nesta revisão. Continua
pendente integrar o transporte frontend e o instalador, validar no ambiente-alvo
a transição da conta atual e a custódia/recuperação de banco e chave. Esta revisão
não aprova implantação MFA na VM e não substitui a prioridade P08.
