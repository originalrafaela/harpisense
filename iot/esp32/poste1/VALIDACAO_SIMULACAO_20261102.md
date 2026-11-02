# Simulação executada no Wokwi web — 02/11/2026

Continuação de `feat/poste1-ensaio-wokwi`, commit-base `d746d43`.
**Circuito executado no simulador web**, com variação de luminosidade,
comando do LED e histerese observados. Nenhuma gravação ou medição física.
Não houve recompilação nem repetição do diagnóstico do GCC.

## Arquivos e caminho de execução

Conferidos `VALIDACAO_BUILD_20261101.md`, `simulation/EXECUTAR.md`, o diagrama,
a configuração virtual, o cenário e o binário existente. Permanecem os fontes
do firmware original e o perfil GPIO34 LDR / GPIO25 LED. A precedência das
referências é a registrada na entrega-base: pacotes aprovados em
`referencias/versão_v2`, complementados por `referencias/Versões corretas` onde
ainda não houve atualização. Nenhum componente foi declarado ausente ou trocado.

O terminal continua sem `WOKWI_CLI_TOKEN`; a CLI não foi usada para executar
o circuito. A alternativa viável foi o editor web, cuja opção de upload de
binário é [documentada pelo Wokwi](https://docs.wokwi.com/guides/esp32).

Criado no Maestri o portal **Poste 1 Wokwi**, em
`https://wokwi.com/projects/new/esp32`. Substituído o conteúdo da aba
diagram.json pelo arquivo canônico e usado **Upload Firmware and Start
Simulation…**, selecionando `.pio/build/wokwi/firmware.bin`. Não foi compilado
o sketch vazio do template. Não houve login, salvamento em conta Wokwi nem
uso de token. O endereço é um template, não um link permanente deste ensaio.

Binário aprovado reutilizado, 917.648 bytes, SHA256:
`a01327f11ac8102e3b1d138b71b105efc112040162ab0b0383d26ea51d6d33f6`.
Foi conferida a igualdade estrutural entre o JSON aberto no editor e o
diagram.json local. Hashes dos arquivos: [input-hashes.json](evidence/simulation-20261102/input-hashes.json).

## Resultados observados

O módulo LDR virtual foi ajustado pelo controle de lux. Após cada mudança
foram aguardadas novas amostras do firmware. O navegador rodou lentamente;
o tempo abaixo é o **tempo simulado**, não o tempo real de espera.

| Condição | Lux no controle virtual | ADC observado | led_commanded | LED virtual |
| --- | --- | --- | --- | --- |
| Claro inicial | 100000 | 32 | 0 | desligado |
| Intermediário após claro | 100 | 2045 | 0 | permaneceu desligado |
| Escuro | 0.1 | 4063 | 1 | ligado |
| Intermediário após escuro | 100 | 2045 | 1 | permaneceu ligado |
| Claro final | 100000 | 32 | 0 | desligado |

**Histerese demonstrada:** o mesmo ADC 2045, dentro da banda 1200..2800,
manteve o estado anterior, tanto desligado quanto ligado. Não se trata de
um ADC calculado em host: são linhas seriais do firmware executado pelo Wokwi.
O sentido virtual permanece invertido em relação ao divisor físico proposto;
`HS_ADC_DARK_IS_LOW=false` é usado somente no perfil Wokwi.

Evidências: [serial completo](evidence/simulation-20261102/serial.txt) e
[observações por fase](evidence/simulation-20261102/observations.json), incluindo
UTC da coleta, tempo simulado, leitura e estado do componente virtual. A coleta
abrangeu aproximadamente 4..14 segundos simulados; o serial também contém a
amostra inicial com o valor padrão do sensor, antes da primeira fase clara.

O estado do LED virtual foi lido no componente da página, com brilho 0/1.
Não foi possível obter screenshot: o portal retornou timeout de renderização.
Isso não foi apresentado como observação visual de uma placa física. Na última
fase, o coletor auxiliar parou porque a propriedade opcional `value` do elemento
LED estava ausente; a confirmação final foi feita separadamente pelo serial
ADC32/comando0 e pela propriedade `brightness=0`. Não se inferiu sucesso a
partir dessa falha do coletor.

O serial mostrou `network_closed: configuration/acceptance gates` e
`utc_valid=0` em todas as amostras. A configuração Wokwi permaneceu com
HS_ALLOW_PUBLISH=false e gates de contrato/ACL/TLS falsos, sem credenciais.
Nenhum broker, VM ou contrato foi acessado/alterado; TLS não foi desativado.

## Repetição e estado final

- [simulation/EXECUTAR.md](simulation/EXECUTAR.md) contém o caminho web exato,
  as opções VS Code/CLI e entrada oculta do token somente no terminal local.
- `scripts/prepare-web.ps1` prepara `.tools/wokwi-web/` e o ZIP local
  `.tools/wokwi-web.zip`: binário aprovado, diagrama e hashes. O script foi
  executado; não compila, não acessa USB e não gera outra implementação.
  Binários/ZIP ficam ignorados pelo Git; o script reproduz o pacote a partir
  dos artefatos locais aprovados da base.
- `simulation/circuit.yaml` foi ampliado para incluir as duas passagens na
  banda intermediária. **Esse YAML não foi executado pela CLI** nesta rodada;
  o ensaio equivalente foi executado no editor web.
- O simulador foi pausado após registrar o retorno ao claro. O portal ficou
  aberto para inspeção; recarregar pode perder o diagrama/binário temporários.

## Limites e próximo passo

Builds aprovados e teste sintético em host pertencem à rodada anterior.
Esta rodada acrescenta execução Wokwi web. Ensaio físico, identificação USB,
alimentação, corrente do LED, calibração real, Wi-Fi/NTP e MQTT real continuam
**não executados**. O comando do LED não comprova iluminação física, e lux/ADC
do modelo não calibram o LDR real. Não há declaração de entrega MQTT garantida.

Próximo passo: usuário confirmar a placa conectada e pronta; então identificar
USB/COM e revisar a configuração física offline antes de qualquer gravação.
Sequência curta preparada em [PROXIMO_ENSAIO_FISICO.md](PROXIMO_ENSAIO_FISICO.md).
**Nenhuma operação de gravação foi executada nesta rodada.**
