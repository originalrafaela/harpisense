# Pedido incremental ao arquiteto — 01/11/2026

Delta recebido na retomada de 02/11 incorporado a `RETOMADA_ROTAS_2026-11-02.md`: não repetir inventário Windows. Falta evidência temporal confiável (`w32tm` não sincronizado/Local CMOS Clock), além das leituras remotas já pendentes. A tentativa SSH com chave Maestri alcança aceitação da chave pública, mas não conclui assinatura local; isso não fornece leitura das VMs. Não solicitar nova chave ou iniciar agente/serviço nesta rodada. As observações abaixo sobre canal Maestri e autenticação descrevem a tentativa histórica, não substituem este delta recebido.

Atualização de 02/11: interfaces e tabela IPv4 do Windows já obtidas em `WINDOWS_NETWORK_READONLY_2026-11-02.json`; não repetir esse inventário. Serviço Mosquitto Stopped e consulta TCP 1883 OK sem endpoints. Restam somente os itens descritos em `RETOMADA_ROTAS_2026-11-02.md`, com comandos para console. SSH do HarpiServer recusou a chave existente; Maestri sem arquiteto conectado. Pedido ainda não transmitido; solicitar conexão/canal autorizado, sem enviar segredos. O pedido abaixo é histórico e a atualização reduz seu escopo.

Já reutilizados: relatórios V2 de 18/10 e 23/10, procedimento P08 de 31/10, inspeção de percurso de 31/10 e comparação candidata/VM. Não reenviar pacotes inteiros. Favor fornecer apenas as evidências abaixo, com host, operador e UTC, sanitizadas; sem senhas, tokens ou Environment completo de serviços. Nenhuma mudança ou geração de tráfego é solicitada.

1. **Poste 2 pelo console autenticado**: saídas abaixo, MAC de cada NIC e correspondência VMware NIC → VMnet/modo. Confirmar destino MQTT resolvido, porta, client_id/tópico e serviço/configuração em uso, sem segredo. `.142` não é premissa.

```sh
date -u
hostname
id -un
ip -br link
ip -br -4 addr
ip -4 rule show
ip -4 route show table all
ip -4 route get 192.168.155.1
ip -6 route show table all
ss -nt
```

Se destino efetivo diferir de `.155.1`, repetir route get para o IPv4 resolvido. Ao analisar a saída: registrar dev/src/via e regra/tabela selecionadas. Rota conectada pela VMnet8 sugere caminho direto; via NIC de campo/gateway é requisito candidato, ainda não prova de trânsito. Endereços sobrepostos, proxy/túnel e policy routing exigem revisão própria. Não afirmar passagem com base apenas na rota do HarpiServer.

2. **Retorno no Windows**: `Get-Date -AsUTC` (PowerShell 7), `Get-NetIPConfiguration`, `Get-NetRoute -AddressFamily IPv4`, `Get-NetTCPConnection -LocalPort 1883`, `Get-Service mosquitto`. Após saber a origem real, `Find-NetRoute -RemoteIPAddress <IP_REAL_POSTE2>`; repetir para ESP32/intermediário se aplicável. Informar VMnet/máscara/MAC do segmento de campo e se há suporte a AP/espelhamento. Não alterar listener, firewall ou rotas.
3. **Somente delta do HarpiServer desde 31/10**: confirmar se NICs, rota ao broker e forwarding mudaram; se sim, anexar `date -u`, `ip -br -4 addr`, `ip -4 rule`, `ip -4 route show table all`, `ip -4 route get <BROKER_REAL>`, `sysctl net.ipv4.ip_forward`. Identificar canal administrativo/console que deve sobreviver. Confirmar hash/stat atuais do integrador legado indicado na proposta, sem substituí-lo.
4. **ESP32-WROOM-32**: AP/localização, IP/máscara/gateway/DNS, uplink do AP e acesso possível ao segmento de campo; configuração MQTT sanitizada e hash/versão do firmware efetivo. Se intermediário: host/interfaces, rota ao broker, modo subnet-router/proxy, NAT e IP/identidade vistos no broker, inclusive transporte VPN. Não instalar firmware nem mudar Wi-Fi/VPN.
5. **Fontes**: caminho/formato/rotação/retenção dos logs Mosquitto Windows e método de exportação íntegra por intervalo; identidade de host/chaves públicas e fingerprints, sincronismo UTC e fronteiras/cursores de broker, consumidor e API. Informar se campos necessários não existem, em vez de fabricar prova de continuidade.

Bloqueio exato: itens 1–2 impedem fechar ida/retorno e comandos/inversas de roteamento; item 4 impede incluir ESP32 no mesmo perímetro; item 5 impede aceite de cobertura completa mesmo com PCAP. Recebidas as rotas, devolver análise dev/src/via/retorno/desvios antes de propor qualquer alteração. Solicitação pronta para repasse manual; não enviada por falta de arquiteto conectado no Maestri.
