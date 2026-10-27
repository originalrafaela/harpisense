"""Contratos auxiliares da distribuição oficial (fonte única: este módulo).

Estruturas auxiliares não são os cinco registros persistidos. As marcas ``verified``
e ``approval_verified`` nunca são deduzidas destes documentos: autenticação externa
permanece obrigatória na integração.
"""
import json
from pathlib import Path
from .schema_source import obj,string,number,nullable,enum,array,STAMP,HASH,BOOL,TARGET
from .validation import ContractError,_shape,require,timestamp
from harpisense_catalog import OPERATION_MODES,NORMALIZED_EVENT_TYPES,SCENARIOS,ACTION_PARAMETER_KEYS

STR=string(); NULLSTR=nullable(STR)
EVENT_REF={'type':'object','properties':{
 'source_file':STR,'line':{'type':'integer','minimum':1},'record_id':NULLSTR},
 'required':['source_file','line'],'additionalProperties':False}
NORMALIZED_EVIDENCE=obj(dict(schema_version=enum(['1.0.0']),evidence_id=STR,
    source=enum(['mosquitto','fastapi','telemetry_consumer']),
    event_type=enum(NORMALIZED_EVENT_TYPES),observed_at=STAMP,
    identity=NULLSTR,target=NULLSTR,origin=NULLSTR,
    outcome=enum(['SUCCESS','DENIED','OBSERVED']),source_ref=EVENT_REF,
    coverage=enum(['COMPLETE','PARTIAL','UNKNOWN']),correlation_group=STR,
    risk_assessed={'const':False},block_authorized={'const':False}))

TRIGGER=obj(dict(schema_version=enum(['1.0.0']),record_type={'const':'confirmatory_trigger'},
    scenario_id=enum(list(SCENARIOS)),trigger_met=nullable(BOOL),
    trigger_status=enum(['TRUE','FALSE','UNKNOWN']),reason=STR,
    window=obj(dict(start=STAMP,end=STAMP,seconds=number(0))),
    scope=obj(dict(identity=NULLSTR,origin=NULLSTR,target=NULLSTR)),
    threshold_version=STR,threshold_fingerprint=HASH,
    thresholds={'type':'object'},calculation={'type':'object'},
    evidence_refs=array(STR,0,True),
    coverage=obj(dict(observed=array(STR),sufficient=BOOL,note=STR)),
    outcomes={'type':'object'},missing_evidence=array(STR),
    invalid_evidence=array({'type':'object'}),independent_sources=array(STR),
    safety=obj(dict(attack_confirmed={'const':False},
                    block_authorized={'const':False},risk_assessed={'const':False})),
    limitations=array(STR,1)))

CONTROLS={'type':'object','properties':dict(operation=enum(OPERATION_MODES),execution_enabled=BOOL,
                  autonomy_mode=enum([1,2,3]),revision={'type':'integer','minimum':1}),
                  'required':['operation','execution_enabled','autonomy_mode'], 'additionalProperties':False}

TARGET_RESOLUTION=obj(dict(status={'const':'RESOLVED'},inventory_version=STR,
  action_type=STR,target=TARGET,ttl_seconds={'type':'integer','minimum':1},
  parameters=obj(dict(rate_profile_ref=NULLSTR,topic_ref=NULLSTR,
                      permission=nullable(enum(['SUBSCRIBE','PUBLISH'])),message_id=NULLSTR)),
  executor_id=STR,asset_id=NULLSTR,criticality=nullable(enum(['LOW','MODERATE','HIGH','CRITICAL'])),
  identity_id=NULLSTR,gates=obj({k:enum(['PASS','FAIL','UNKNOWN'])
                     for k in ('target','scope','protected_assets','executor_ready')}),
  execution_requested={'const':False},authorization_granted={'const':False},
  inventory_fingerprint=HASH))

# Propostas de interfaces v2 para implementação FUTURA por verificadores/adaptadores.
OUTCOME_RESULT=obj(dict(schema_version={'const':'2.0.0'},record_type=enum([
    'application_result','verification_result','reversal_result']),
    execution_id=STR,action_fingerprint=HASH,observed_at=STAMP,
    status=enum(['ACCEPTED','UNAVAILABLE','FAILED','UNKNOWN_OUTCOME',
                 'CONFIRMED','NOT_CONFIRMED','INCONCLUSIVE','REVERSED','REVERSAL_FAILED']),
    verifier_ref=NULLSTR,evidence_refs=array(STR)))

AUX_SCHEMAS={'normalized_evidence':NORMALIZED_EVIDENCE,
             'confirmatory_trigger':TRIGGER,'operational_controls':CONTROLS,
             'target_resolution':TARGET_RESOLUTION,'action_outcome':OUTCOME_RESULT}
for kind,spec in AUX_SCHEMAS.items():
    spec['$schema']='https://json-schema.org/draft/2020-12/schema'
    spec['$id']='urn:harpisense:aux:'+kind+':1.0.0' if kind!='action_outcome' else 'urn:harpisense:aux:action_outcome:2.0.0'


def validate_aux(kind,record):
    require(kind in AUX_SCHEMAS,'Contrato auxiliar desconhecido')
    _shape(record,AUX_SCHEMAS[kind])
    if kind=='operational_controls':
        require(record['operation']!='IDS' or record['execution_enabled'] is False,
                'IDS não admite execução habilitada')
    if kind=='confirmatory_trigger':
        w=record['window'];require(timestamp(w['start'])<timestamp(w['end']),'Janela inválida')
        status=record['trigger_status']
        require(record['trigger_met']==({'TRUE':True,'FALSE':False,'UNKNOWN':None}[status]),
                'Status do gatilho inconsistente')
        require(status=='UNKNOWN' or record['coverage']['sufficient'] is True,
                'Cobertura insuficiente para gatilho conhecido')
    if kind=='normalized_evidence':
        require(record['correlation_group']==record['source'],'Grupo de origem incompatível')
    if kind=='action_outcome':
        typ=record['record_type'];state=record['status']
        allowed={ 'application_result':{'ACCEPTED','UNAVAILABLE','FAILED','UNKNOWN_OUTCOME'},
            'verification_result':{'CONFIRMED','NOT_CONFIRMED','INCONCLUSIVE'},
            'reversal_result':{'REVERSED','REVERSAL_FAILED','INCONCLUSIVE'}}
        require(state in allowed[typ],'Status fora da fase de execução')
        if typ!='application_result':require(record['verifier_ref'] is not None,
             'Verificação/reversão exige fonte verificável')
    return record


def export_aux(directory):
    dest=Path(directory);dest.mkdir(parents=True,exist_ok=True)
    for kind,schema in AUX_SCHEMAS.items():
        (dest/(kind+'.schema.json')).write_text(json.dumps(schema,ensure_ascii=False,
            indent=2,allow_nan=False)+'\n',encoding='utf-8')
