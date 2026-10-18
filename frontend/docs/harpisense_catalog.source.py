"""Fonte única compartilhada pelos contratos, Risk e Policy. Valores iniciais de laboratório."""
CATALOG_VERSION='harpisense.catalog.v1'
ACTION_SPECS={
 'BLOCK_SOURCE_IP':('SOURCE_IP',()),'LIMIT_SOURCE_RATE':('SOURCE_IP',('rate_profile_ref',)),
 'SUSPEND_MQTT_IDENTITY':('MQTT_IDENTITY',()),'REVOKE_MQTT_PERMISSION':('MQTT_IDENTITY',('topic_ref','permission')),
 'RATE_LIMIT_API_CLIENT':('API_CLIENT',('rate_profile_ref',)),
 'RATE_LIMIT_MQTT_CLIENT':('MQTT_IDENTITY',('rate_profile_ref',)),
 'QUARANTINE_TELEMETRY':('TELEMETRY_MESSAGE',('message_id',))}
# id: grupo, nome, impacto potencial, tipo de evidência, ações permitidas
ROWS=[
 ('C01','Low','Varredura TCP',30,'PORT_SCAN',['BLOCK_SOURCE_IP','LIMIT_SOURCE_RATE']),
 ('C02','Low','Assinatura MQTT indevida',40,'MQTT_SUBSCRIBE_DENIED',['SUSPEND_MQTT_IDENTITY','REVOKE_MQTT_PERMISSION']),
 ('C03','Low','Ingestão sem autenticação',40,'INGEST_AUTH_DENIED',['BLOCK_SOURCE_IP','RATE_LIMIT_API_CLIENT']),
 ('C04','Medium','Tentativas contra admin',65,'ADMIN_AUTH_FAILURES',['BLOCK_SOURCE_IP','RATE_LIMIT_API_CLIENT']),
 ('C05','Medium','Tentativas de autenticação MQTT',60,'MQTT_AUTH_FAILURES',['BLOCK_SOURCE_IP','LIMIT_SOURCE_RATE']),
 ('C06','Medium','Publicação MQTT indevida',65,'MQTT_PUBLISH_DENIED',['SUSPEND_MQTT_IDENTITY','REVOKE_MQTT_PERMISSION']),
 ('C07','Hard','Integridade da telemetria',85,'TELEMETRY_INTEGRITY',['QUARANTINE_TELEMETRY','SUSPEND_MQTT_IDENTITY']),
 ('C08','Hard','Excesso de conexões TCP',90,'TCP_CONNECTION_FLOOD',['BLOCK_SOURCE_IP','LIMIT_SOURCE_RATE']),
 ('C09','Hard','Excesso de publicações MQTT',85,'MQTT_PUBLISH_FLOOD',['RATE_LIMIT_MQTT_CLIENT','SUSPEND_MQTT_IDENTITY'])]
CATALOG={r[0]:dict(group=r[1],name=r[2],impact=r[3],evidence_kind=r[4],actions=r[5]) for r in ROWS}
SCENARIOS={k:v['group'] for k,v in CATALOG.items()}
SCENARIO_ACTIONS={k:v['actions'] for k,v in CATALOG.items()}
ACTIONS=list(ACTION_SPECS)
AUTONOMY={1:{'Low':'MANUAL','Medium':'MANUAL','Hard':'MANUAL'},
          2:{'Low':'AUTO','Medium':'AUTO','Hard':'MANUAL'},
          3:{'Low':'AUTO','Medium':'AUTO','Hard':'AUTO'}}
DEFAULT_CONFIG=dict(version='harpisense.risk-policy.v1',weights=dict(detection=35,corroboration=20,impact=20,anomaly=15,criticality=10),
 min_action_score=60,min_rf_confidence=.9,min_independent_sources=1,max_evidence_age_seconds=60,
 decision_seconds=120,min_ttl_seconds=30,max_ttl_seconds=600,default_ttl_seconds=120)

# Campos auxiliares centralizados; matriz e pesos v1 permanecem intocados.
OPERATION_MODES=('IDS','SIMULATION','REAL')
TARGET_TYPES=tuple(sorted({target for target,_ in ACTION_SPECS.values()}))
ACTION_PARAMETER_KEYS=('rate_profile_ref','topic_ref','permission','message_id')
NORMALIZED_EVENT_TYPES=('mqtt_auth_failure','mqtt_auth_success','mqtt_acl_denial',
 'api_auth_failure','api_auth_success','api_access_denied',
 'telemetry_identifier_conflict','telemetry_duplicate','telemetry_stale',
 'telemetry_validation_failure')
