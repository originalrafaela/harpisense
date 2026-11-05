# Auditor offline P08 → requisitos RF/IF

Reutiliza o conversor instalado e o agregador aprovado, com hashes em
`compatibility_sources/ORIGINS.json`. As duas fontes são preservadas sem alteração.
Validação numérica, ordem de colunas e float32 usam `harpisense_data.windows.validate`
do P09, sem recriar o pré-processamento. Não desserializa modelos, treina, infere,
envia pacotes, persiste no P11 ou autoriza coleta/contenção.

Na raiz da worktree, com a imagem já preparada em `7fe8294`:

```powershell
docker run --rm --network none -v "${PWD}:/work" harpisense-detection:integration python -B backend/p08_p09/compatibility_tests/run_tests.py
docker run --rm --network none -v "${PWD}:/work" harpisense-detection:integration python -B -m p08_p09.compatibility_audit --profile docs/evidence/p08-compatibility-20261105/observation-plan.json --output local-evidence/p08-compatibility/requirements-new.json
```

O segundo comando retorna BLOCKED e código não zero: é o resultado esperado da
dependência atual. Recusa sobrescrever resultados. O plano tem schema distinto
do perfil de captura e chaves desconhecidas explícitas; não é um perfil aprovado.

Depois de obter uma sessão real assinada, usar o mesmo comando com perfil de
captura real e acrescentar `--pcap`, `--session-report`, `--evidence-dir`,
`--rf-directory`, `--rf-sha256`, `--if-directory` e `--if-sha256`. Todos os caminhos
devem estar acessíveis dentro do contêiner. Os hashes são pins externos confiáveis,
não valores preenchidos a partir de um bundle desconhecido. O diretório de
evidências contém os bundles assinados das quatro fontes do perfil. PCAP e logs
sensíveis permanecem fora do Git; publicar somente resumo sanitizado e hashes.

O auditor verifica integridade/assinatura de sessão pelo validador Edge existente,
recalcula features pelo conversor/agregador existentes e consulta cobertura pelo
verificador existente. Reporta janelas parciais, alias v2 sem substituir o ID legado,
formatos rejeitados, features ausentes, divergência de perfil/janela/ambiente e a
ordem exata do artefato. Bytes e colunas numericamente compatíveis **não provam**
treinamento, calibração válida no laboratório, limite temporal entre hosts ou
eficácia. O auditor mantém autorização de inferência/IPS falsa em todo resultado.

Os oito testes usam somente PCAPs mínimos construídos offline e metadados
explicitamente fictícios para testar o auditor, sem desserialização. Não são o
ensaio sintético de inferência anterior e não são dados do laboratório. Os testes
ficam separados do runner P08 original de biblioteca padrão; não ampliam suas
dependências nem mudam os gates.

Entrega à captura e pendências: `docs/COMPATIBILIDADE_P08_LAB_20261105.md`.
