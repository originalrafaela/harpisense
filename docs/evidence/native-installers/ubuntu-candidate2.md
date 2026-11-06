# Correção da tentativa Ubuntu — 2026-11-06

## Diagnóstico e custódia

O operador baixou a candidata 1 em `~/harpisense-teste` e confirmou SHA-256
(`SUCESSO`). O instalador falhou em `prepare_database`, após instalação de
dependências, cópia em `/opt/harpisense`, criação de estado/cluster e
`initialize_database`. Não chegou à criação/habilitação dos serviços HarpiSense.
O `finally` tenta parar o cluster temporário; não houve inspeção remota que
confirme o estado atual. Não afirmar que não existe nenhum processo ativo na VM.

Saída recebida preservada em `ubuntu-candidate1-failure.txt`. Não recebemos os
logs privados do disco da VM. URLs assinadas temporárias e identidade da máquina
foram omitidas. Não coletar `state.json`, chaves ou arquivos `.secret` publicamente.
A dificuldade anterior de copiar/colar é independente do erro do instalador.

## Causa e correção

O build Ubuntu copiava `harpisense_contracts`, mas não o módulo irmão
`backend/domain/harpisense_catalog.py`. `backend/domain` já estava no caminho
do runtime. Não é falha do runtime congelado (Ubuntu usa venv) nem import
incorreto do Backend. Nenhum import/estrutura de aplicação foi alterado;
não foi necessário solicitar alteração ao Backend. Nenhum módulo foi copiado
manualmente para a VM.

O payload inclui agora o catálogo. Windows declara também o módulo explicitamente
como hidden import. `check-runtime` carrega catálogo, contratos, setup/store,
MFA, API e consumidor sem conexão ou escrita no banco e confirma que os módulos
da aplicação vêm do pacote. Ubuntu usa o interpretador instalado com `-I`,
sem PYTHONPATH/PYTHONHOME, antes de criar estado e inicializar o banco.
Windows executa o runtime congelado após instalar o requisito VC++, antes do
estado/initdb; o build também exige o mesmo teste fora do checkout.

## Testes realmente executados

- Build Windows concluído; runtime congelado retornou `RUNTIME_IMPORTS_OK`,
  com cwd fora do checkout e sem PYTHONPATH/PYTHONHOME. Registro em
  `candidate2-windows-imports.txt`. Nenhuma instalação de serviço Windows feita.
- Build `.run` Ubuntu concluído. Teste do artefato em container descartável
  `python:3.12-slim`, sem rede: extração do próprio `.run`, venv novo, instalação
  offline dos wheels incluídos e execução `python -I entry.py check-runtime`
  a partir de `/`. Apenas artefato e script de teste montados; nenhum checkout.
  Resultado `RUNTIME_IMPORTS_OK`.
- Teste negativo no mesmo container: retirar o catálogo faz a verificação
  recusar com o ModuleNotFoundError esperado, antes de qualquer operação de banco.
  Resultado `MISSING_CATALOG_REJECTED_BEFORE_DATABASE`. Registro completo sem
  credenciais em `candidate2-linux-smoke.txt`.
- `git diff --check` passou. Verificações funcionais anteriormente aprovadas
  não foram repetidas. Nenhum teste completo apt/systemd/reboot em VM limpa
  foi executado nesta correção. Container Python 3.12 não homologa Ubuntu 24.04.

## Candidata e retomada

Nova release `native-installers-20261106-candidate.2`, mantendo a candidata 1.
Recibo antigo preservado em `published-assets-candidate1.json`; recibo da nova
publicação em `published-assets.json` quando publicado.

SHA-256 Ubuntu: `fd7b65896e55c83d61d211bb2687cb257ff90349ab4ef424e28477f1d3f58161`.
SHA-256 Windows: `4c31a7eda007620e3396a103118b4a09167d00d45432111430626b7f3e1003f5`.

VM parcial preservada: não reinstalar nem remover `/opt/harpisense` ou
`/var/lib/harpisense`. Nenhuma VM foi acessada, desligada ou alterada pelo agente.
Próxima ação: obter VM Ubuntu 24.04 x86_64 limpa ou snapshot anterior à tentativa;
baixar candidata 2 e checksum, verificar, instalar e registrar saída sanitizada.
Depois verificar serviços/painel/bootstrap e reinício, sem usar as VMs do laboratório.
Ensaio completo pendente de disponibilização/acesso ao alvo limpo.
