# Contrato MQTT para instalador nativo e Gerenciador web

Esta entrega estende o registry existente; não instala broker, executa comandos,
altera servidor externo nem fornece um aplicador MQTT fictício.

## API disponível

Todas as rotas usam a sessão administrativa já instalada, inclusive MFA na
composição que a exigir, e retornam `Cache-Control: no-store`.

- `GET /api/v1/config/catalog`: novo objeto `mqtt`, versão `1.0.0`.
  `default_mode=local_managed`, `modes=[local_managed,external]`.
  `constraints` contém revisão da política, hosts/tópicos/CA permitidos,
  TLS obrigatório e faixa de portas. Lista vazia não autoriza qualquer destino.
  Nenhum valor de credencial é exposto.
- `PUT /api/v1/config/setup`: aceita `document.parameters.mqtt_broker_mode`.
  Reutiliza expected_version, idempotência e auditoria existentes. Rascunho
  parcial pode conter somente a escolha; isso não cria ou inicia um serviço.
- Proposta e validação continuam nas rotas existentes. Uma proposta MQTT exige
  host, porta, TLS, CA, referência opaca de identidade, tópicos e client_id.
  Propostas antigas sem mode continuam válidas. Não inferir modo local de um host.
  Validar parâmetros verifica schema e política; não testa conexão.
- `GET /api/v1/config/mqtt/status`: componente instalado, broker disponível e
  consumidor conectado são observações independentes. Nesta composição, todos
  retornam `state=not_verified,observed_at=null`. `devices=[]` com
  `device_observation=not_verified` significa ausência de observador, não ausência
  comprovada de dispositivos. Não exibir “aguardando primeira mensagem” sem
  observação real de broker ativo e inventário conhecido.

`operations.save_draft` e `validate_parameters` são verdadeiros. Os demais
(`verify_connection`, `apply`, `install_component`, `manage_service`,
`register_device`) são falsos. O Frontend deve desabilitar as ações indisponíveis.
O aplicador de apresentação permanece limitado a nome/fuso. Nenhuma alteração
MQTT efetiva é executada por esta entrega; configuração funcional anterior é
preservada. As rotas existentes não devem ser apresentadas como conexão validada.

## Divisão com packaging/native

O instalador Windows/Ubuntu instala componentes e registra serviços com as
permissões do sistema. A aplicação web consulta APIs; não recebe senha técnica,
comando de shell ou autoridade para modificar um broker externo. Serviço
registrado/ativo não prova autenticação MQTT, consumidor conectado ou telemetria.
Wokwi, licença e token não são requisitos de instalação ou desse contrato.

## Backend ainda necessário antes de habilitar operação real

1. Manifesto confiável por instalação e plataforma para broker local gerenciado,
   com observação de componente/serviço e timestamps; sem descoberta por comandos
   fornecidos pelo navegador.
2. Verificador MQTT real usando referências do cofre e allowlist, TLS e identidade,
   timeout e códigos sanitizados de DNS/TLS/autenticação/ACL; TCP aberto não basta.
3. Aplicador com autorização/reautenticação, revisão, idempotência, auditoria,
   lock/fencing e recuperação durável. Verificar candidato antes de trocar;
   confirmar consumidor no novo destino e restaurar anterior na falha. Nenhuma
   escrita/administracão remota do broker externo deve ser presumida.
4. Observador real do consumidor e última mensagem por identidade de dispositivo,
   com timestamp, origem e frescor. “Broker ativo, aguardando primeira mensagem”
   exige broker comprovado e nenhuma mensagem no inventário observado.
5. Registro persistente e catálogo extensível de dispositivos/publicadores,
   separado do catálogo de firmware. O Poste 2 Ubuntu não é firmware ESP32.
   Atualização de evidência do Poste 1 deve preservar compatibilidade de IDs;
   build/lint e histerese reutilizada não comprovam físico/TLS/ACL ou conectividade.

Nenhum adaptador de teste é ativado pelo produto. Os testes de contrato usam
apenas autenticação controlada no teste; não alteram banco, broker ou serviços.
