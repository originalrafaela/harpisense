# Relatório de validação do pacote

**Data:** 2026-09-23

## Validação automatizada realizada na geração

O pacote possui testes em `tests/test_repository.py` para:

- presença dos arquivos obrigatórios por caso;
- validade de `diagram.json` e `wokwi.toml`;
- caminho correto do firmware PlatformIO;
- garantia de que os firmwares usam `host.wokwi.internal`, e não broker público;
- existência/metadados A03–A09;
- `allow_anonymous false`, ACL e password file no Mosquitto.

Execute:

```bash
python -m unittest discover -s tests -v
```

## Validação runtime que precisa ser produzida no laboratório do grupo

A simulação gráfica **Wokwi for VS Code** e o build PlatformIO dependem das extensões/toolchains instalados na estação do grupo. Portanto, um caso só deve ser marcado como `PASS runtime` após:

1. `PlatformIO: Build` sem erros;
2. geração de `firmware.bin` e `firmware.elf`;
3. `Wokwi: Start Simulator`;
4. conexão ao Mosquitto local;
5. evidência de Serial/broker/observer;
6. preenchimento do `RESULT_TEMPLATE.md`.

Não rotule no TCC um caso como executado apenas porque o código foi preparado. Preserve a distinção entre **pré-validação do artefato** e **resultado experimental obtido**.
