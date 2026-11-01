# Leituras incrementais para Edge

Pedido lido em d2ddbdc:p08_captura/PEDIDO_EVIDENCIAS_ARQUITETO.md e proposta
PROPOSTA_LAB_2026-11-01.md. Reutilizados registros de percurso/VM de 31/10,
comparação candidata/VM e relatórios V2 já referidos pela Edge. Não reenviar pacotes.

Leitura local nesta sessão, Windows, operador agente Codex autorizado pelo usuário,
01/11/2026 21:30:34 UTC: VMnet8 ifIndex17 192.168.155.1/24 e rota conectada;
VMnet1 ifIndex12 192.168.180.1/24; Ethernet 192.168.1.5/24, default 192.168.1.1;
rota Tailscale 100.66.89.7/32 pela ifIndex31. Get-Service mosquitto: Stopped.
Consulta Get-NetTCPConnection -LocalPort 1883 não retornou entradas. Não prova
ausência de outros brokers/portas. Não iniciar serviço nem presumir estado de 31/10.
SSH ao gateway recusou autenticação; nenhuma evidência atual da VM foi obtida.

Lista única do que ainda falta, com host/operador/UTC e sem segredos:

1. **Console Poste 2:** date -u; hostname; id -un; ip -br link; ip -br -4 addr;
   ip -4 rule show; ip -4 route show table all; ip -4 route get 192.168.155.1;
   ip -6 route show table all; ss -nt. Confirmar broker resolvido/porta/client_id/
   tópico/configuração efetivos e NIC/MAC → VMnet/modo. Se destino diferente,
   repetir route get para IPv4 efetivo. Não coletar Environment completo.
2. **Windows após descobrir IP real Poste 2:** Find-NetRoute -RemoteIPAddress
   <IP_REAL_POSTE2>; Get-NetAdapter | Select Name,InterfaceIndex,MacAddress;
   confirmar VMnet/máscara/modo/espelhamento. Repetir Find-NetRoute para ESP32
   ou intermediário se aplicável. Estado 1883 já lido acima; só repetir se houver
   mudança declarada ou listener MQTT efetivo em outra porta.
3. **HarpiServer, somente delta desde 31/10:** confirmar NICs/rota/forwarding;
   se mudaram: date -u; ip -br -4 addr; ip -4 rule; ip -4 route show table all;
   ip -4 route get <BROKER_REAL>; sysctl net.ipv4.ip_forward. Sempre stat e
   sha256sum /opt/harpisense/staging/p08-captura/integracao/integrar_p08.py.
   Comparar SHA256 anterior f1537b54ba721153b3daf8a09a09ba1e7aef24aee4a513828302ca237e5f06a5;
   identificar canal administrativo/console preservável.
4. **ESP32/AP e fontes:** informar IP/máscara/gateway/DNS/AP/uplink, MQTT
   sanitizado e hash/versão do firmware efetivo; intermediário/proxy/VPN/NAT se
   existir. Informar caminhos/formato/rotação/retenção/exportação de logs broker,
   consumidor/API, sincronismo UTC, chaves públicas/fingerprints e cursores de
   continuidade disponíveis. Configuração Wokwi preparada não supre esses dados.

Sem IP/rota real Poste 2 não concluir ida/retorno. Sem fontes/cursores não afirmar
cobertura completa. Não executar captura/ataque/alteração de rede ou contenção.
