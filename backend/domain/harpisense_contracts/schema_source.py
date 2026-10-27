"""Fonte única dos JSON Schemas 2020-12. Campos desconhecidos são recusados."""
import json
from pathlib import Path

VERSION='1.0.0'
from harpisense_catalog import SCENARIOS,SCENARIO_ACTIONS,ACTIONS
CLASSES=['normal',*SCENARIOS]

def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}

def string(): return {'type':'string','minLength':1}
def enum(values): return {'enum':values}
def nullable(spec): return {'anyOf':[{'type':'null'},spec]}
def number(lo=None,hi=None):
    d={'type':'number'}
    if lo is not None: d['minimum']=lo
    if hi is not None: d['maximum']=hi
    return d

def array(item,minimum=0,unique=False):
    return {'type':'array','items':item,'minItems':minimum,'uniqueItems':unique}

def refs(minimum=0): return array(string(),minimum,True)
def const(value): return {'const':value}
STAMP={'type':'string','format':'date-time'}
BOOL={'type':'boolean'}
HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
PROB=number(0,1)
FEATURES={'type':'object','minProperties':1,'additionalProperties':number(0)}
WINDOW=obj(dict(window_id=string(),collection_session_id=string(),sensor_id=string(),
    feature_schema_version=string(),traffic_profile=string(),start=STAMP,end=STAMP))
ENTITY=obj(dict(source_ip=nullable({'type':'string','format':'ip'}),
    destination_ip=nullable({'type':'string','format':'ip'}),
    device_id=nullable(string()),mqtt_client_id=nullable(string())))
RF=obj(dict(predicted_class=enum(CLASSES),accepted_class=nullable(enum(CLASSES)),
    probabilities={'type':'object','minProperties':2,'additionalProperties':PROB},
    confidence=PROB,attack_probability=PROB,confidence_threshold=PROB,needs_review=BOOL))
IF=obj(dict(anomaly_score=number(),anomaly_threshold=number(),anomaly_margin=number(),
    is_anomaly=BOOL,normal_reference_percentile=PROB))
GATES=obj({k:enum(['PASS','FAIL','UNKNOWN']) for k in ['evidence','target','scope','freshness','protected_assets','executor_ready']})
RISK=obj(dict(status=enum(['COMPLETE','INCOMPLETE','NOT_EVALUATED']),score=nullable(number(0,100)),
    level=nullable(enum(['LOW','MODERATE','HIGH','CRITICAL'])),formula_version=nullable(string()),
    factors=obj({k:nullable(number(0,100)) for k in ['detection','corroboration','impact','anomaly','criticality']})))
TARGET=obj(dict(target_ref=string(),target_kind=enum(['SOURCE_IP','MQTT_IDENTITY','API_CLIENT','TELEMETRY_MESSAGE']),
    scope_ref=string()))
ACTION=obj(dict(action_type=enum(ACTIONS),target=TARGET,ttl_seconds={'type':'integer','minimum':1,'maximum':86400},
    parameters=obj(dict(rate_profile_ref=nullable(string()),topic_ref=nullable(string()),
                        permission=nullable(enum(['SUBSCRIBE','PUBLISH'])),message_id=nullable(string())))))
APPROVAL=obj(dict(approval_id=string(),decision_id=string(),action_fingerprint=HASH,
    policy_version=string(),approved_by=string(),approved_at=STAMP,expires_at=STAMP))

def common(kind,idkey):
    return dict(schema_version=const(VERSION),record_type=const(kind),**{idkey:string()},created_at=STAMP)

SCHEMAS={
 'detection':obj({**common('detection','detection_id'),
    'window':WINDOW,'entity':ENTITY,
    'model':obj(dict(detector=enum(['random_forest','isolation_forest']),model_version=string(),input_dtype=const('float32'))),
    'quality':obj(dict(status=enum(['VALID','STALE']),valid_until=STAMP)),
    'features':FEATURES,'input_fingerprint':HASH,
    'classification':nullable(RF),'anomaly':nullable(IF),
    'block_authorized':const(False),
    'provenance':obj(dict(source_schema=string(),source_id=string()))}),
 'explanation':obj({**common('explanation','explanation_id'),
    'detection_id':string(),'window_id':string(),'collection_session_id':string(),
    'model_version':string(),'input_fingerprint':HASH,
    'method':enum(['SHAPLEY_PERMUTATION','SHAP_MODEL_AGNOSTIC']),
    'explainer_version':string(),'reference_ref':string(),
    'target':obj(dict(output=enum(['CALIBRATED_CLASS_PROBABILITY','ANOMALY_SCORE']),
                       class_label=nullable(enum(CLASSES)))),
    'base_value':nullable(number()),'output_value':nullable(number()),
    'contributions':array(obj(dict(feature=string(),value=number(),contribution=number())),0),
    'additivity_residual':nullable(number()),
    'parameters':obj(dict(seed={'type':'integer'},permutations=nullable({'type':'integer','minimum':1}),
                         background_rows={'type':'integer','minimum':1})),
    'limitations':array(string(),1)}),
 'incident':obj({**common('incident','incident_id'),
    'revision':{'type':'integer','minimum':1},'updated_at':STAMP,'correlation_key':string(),
    'status':enum(['OBSERVED','SUSPECTED','CORROBORATED','CLOSED']),
    'scenario_id':nullable(enum(list(SCENARIOS))),
    'scenario_group':nullable(enum(['Low','Medium','Hard'])),
    'detection_refs':refs(1),'explanation_refs':refs(),
    'evidence_refs':refs(),'target_ref':nullable(string()),
    'risk':RISK,'gates':GATES}),
 'decision':obj({**common('decision','decision_id'),
    'supersedes_decision_id':nullable(string()),'incident_id':string(),'incident_revision':{'type':'integer','minimum':1},
    'policy_version':string(),'autonomy_mode':{'type':'integer','minimum':1,'maximum':3},
    'scenario_id':nullable(enum(list(SCENARIOS))),'scenario_group':nullable(enum(['Low','Medium','Hard'])),
    'risk_score':nullable(number(0,100)),'risk_level':nullable(enum(['LOW','MODERATE','HIGH','CRITICAL'])),
    'status':enum(['OBSERVE_ONLY','REQUEST_APPROVAL','AUTHORIZED','DENIED']),
    'reason_codes':refs(1),'evidence_refs':refs(),'detection_refs':refs(1),
    'gates':GATES,'action':nullable(ACTION),'action_fingerprint':nullable(HASH),
    'approval':nullable(APPROVAL),'valid_until':STAMP,
    'execution_requested':const(False)})
}
# Adotado do HarpiSense_Gerenciador_Execucao_v1/execution.schema.json.
# Mantém versão 1.0.0 e conjunto de campos do contrato público de referência.
EXECUTION_STATES=['QUEUED','APPLYING','COMMAND_ACCEPTED','VERIFYING',
    'MITIGATION_CONFIRMED','SIMULATED','UNAVAILABLE','FAILED','UNKNOWN_OUTCOME',
    'EXPIRING','EXPIRED','REVERSING','REVERSED','REVERSAL_FAILED']
SCHEMAS['execution']=obj(dict(schema_version=const(VERSION),record_type=const('execution'),
    execution_id=string(),decision_id=string(),action_fingerprint=HASH,
    status=enum(EXECUTION_STATES),requested_at=STAMP,
    started_at=nullable(STAMP),accepted_at=nullable(STAMP),verified_at=nullable(STAMP),
    expires_at=nullable(STAMP),reversed_at=nullable(STAMP),
    attempt_count={'type':'integer','minimum':0}))

for kind,s in SCHEMAS.items():
    s['$schema']='https://json-schema.org/draft/2020-12/schema'
    s['$id']=f'urn:harpisense:contracts:{kind}:{VERSION}' if kind!='execution' else 'https://harpisense.local/schemas/execution/1.0.0'
    s['description']='Estrutura interoperavel; validar tambem invariantes e vinculos em harpisense_contracts.validation.'

def export(directory):
    out=Path(directory);out.mkdir(parents=True,exist_ok=True)
    for name,s in SCHEMAS.items(): (out/f'{name}.schema.json').write_text(json.dumps(s,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
