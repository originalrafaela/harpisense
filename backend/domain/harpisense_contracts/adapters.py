"""Adaptadores dos ZIPs RF/IF já entregues. Não recalculam decisões nem risco."""
from copy import deepcopy
import struct
from datetime import timedelta
from .validation import validate,validate_links,require,timestamp,input_fingerprint,fingerprint,ContractError
from .schema_source import VERSION


def detection_from_legacy(signal,*,max_age_seconds=60,previous=None):
    require(isinstance(signal,dict),'Sinal deve ser objeto')
    require(type(max_age_seconds) in [int,float] and 0<max_age_seconds<=86400,'Prazo de frescor invalido')
    source_schema=signal.get('signal_schema_version')
    expected={'harpisense.detection.rf.v1':'random_forest','harpisense.detection.if.v1':'isolation_forest'}
    require(source_schema in expected,'Somente envelopes operacionais RF/IF v1; predict_windows isolado nao tem contexto suficiente')
    require(signal.get('status') in ['ok','stale'],'Entrada invalida nao e deteccao normal; encaminhar a observabilidade')
    detector=expected[source_schema]
    require(signal.get('detector')==detector,'Detector/schema divergentes')
    require(signal.get('block_authorized') is False,'Modelo nao autoriza bloqueio')
    require(bool(signal.get('signal_id')),'signal_id ausente')
    try:
        features=signal['evidence']['features']
        require(type(features) is dict and all(type(v) in [int,float] for v in features.values()),'Features nao numericas')
        try:
            features={k:struct.unpack('!f',struct.pack('!f',v))[0] for k,v in features.items()}
        except (OverflowError,struct.error) as exc: raise ContractError('Feature fora de float32') from exc
        context=signal['entity_context'];require(type(context) is dict,'Contexto invalido')
        expiry=(timestamp(signal['window_end'])+timedelta(seconds=max_age_seconds)).isoformat()
        fresh=timestamp(signal['generated_at'])<=timestamp(expiry)
        require(signal['status']==('ok' if fresh else 'stale'),'Status legado nao corresponde ao prazo configurado')
        require(signal.get('eligible_for_correlation') is fresh,'Elegibilidade legada divergente')
        require(abs(signal['age_seconds']-(timestamp(signal['generated_at'])-timestamp(signal['window_end'])).total_seconds())<1e-6,'Idade legada divergente')
        c=a=None
        if detector=='random_forest':
            c={k:signal[k] for k in ['predicted_class','accepted_class','probabilities','confidence','attack_probability','confidence_threshold','needs_review']}
        else:
            a={k:signal[k] for k in ['anomaly_score','anomaly_threshold','anomaly_margin','is_anomaly','normal_reference_percentile']}
        result=dict(schema_version=VERSION,record_type='detection',
            detection_id='det-'+signal['signal_id'],created_at=signal['generated_at'],
            window=dict(window_id=signal['window_id'],collection_session_id=signal['collection_session_id'],
                sensor_id=signal['sensor_id'],feature_schema_version=signal['feature_schema_version'],
                traffic_profile=signal['traffic_profile'],start=signal['window_start'],end=signal['window_end']),
            entity=dict(source_ip=context.get('src_ip'),destination_ip=context.get('dst_ip'),
                device_id=context.get('device_id'),mqtt_client_id=context.get('mqtt_client_id')),
            model=dict(detector=detector,model_version=signal['model_version'],input_dtype='float32'),
            quality=dict(status='VALID' if fresh else 'STALE',valid_until=expiry),
            features=features,input_fingerprint=input_fingerprint(features),classification=c,anomaly=a,
            block_authorized=False,provenance=dict(source_schema=source_schema,source_id=signal['signal_id']))
    except KeyError as exc: raise ContractError('Campo legado obrigatorio ausente: '+str(exc)) from exc
    validate(result)
    if previous is not None:
        validate(previous)
        # Worker legado renova generated_at na retransmissao; preservar snapshot original.
        def substantive(record):
            x=deepcopy(record);x.pop('created_at');x['quality'].pop('status');return x
        require(substantive(previous)==substantive(result),'identifier_conflict: mesmo sinal com conteudo diferente')
        return deepcopy(previous)
    return result


def rf_explanation_from_legacy(payload,detection,*,created_at,reference_ref,explainer_version='harpisense.rf.permutation.v1'):
    validate(detection)
    require(detection['model']['detector']=='random_forest','Adaptador de explicacao exclusivo RF')
    require(payload.get('method')=='interventional_shapley_permutation_monte_carlo','Metodo legado nao suportado')
    require(payload.get('output')=='calibrated_class_probability','Saida legada nao calibrada')
    require(payload['model_version']==detection['model']['model_version'] and payload['window_id']==detection['window']['window_id'],'Modelo/janela divergentes')
    contributions=[dict(feature=v['feature'],value=v['value'],contribution=v['shapley_estimate']) for v in payload['contributions']]
    params=dict(seed=payload['seed'],permutations=payload['permutations'],background_rows=payload['background_rows'])
    identity=[detection['detection_id'],payload['class'],reference_ref,explainer_version,params]
    r=dict(schema_version=VERSION,record_type='explanation',explanation_id='exp-'+fingerprint(identity),created_at=created_at,
        detection_id=detection['detection_id'],window_id=detection['window']['window_id'],
        collection_session_id=detection['window']['collection_session_id'],model_version=payload['model_version'],
        input_fingerprint=detection['input_fingerprint'],method='SHAPLEY_PERMUTATION',
        explainer_version=explainer_version,reference_ref=reference_ref,
        target=dict(output='CALIBRATED_CLASS_PROBABILITY',class_label=payload['class']),
        base_value=payload['base_value'],output_value=payload['predicted_probability'],
        contributions=contributions,additivity_residual=payload['additivity_residual'],
        parameters=params,limitations=[payload['caveat']])
    validate_links(detections=[detection],explanations=[r],incidents=[],decisions=[])
    return r


def unresolved_incident(detections,*,incident_id,correlation_key,created_at):
    require(bool(detections),'Incidente exige deteccoes')
    for d in detections: validate(d)
    r=dict(schema_version=VERSION,record_type='incident',incident_id=incident_id,created_at=created_at,
        revision=1,updated_at=created_at,correlation_key=correlation_key,status='OBSERVED',
        scenario_id=None,scenario_group=None,detection_refs=[d['detection_id'] for d in detections],
        explanation_refs=[],evidence_refs=[],target_ref=None,
        risk=dict(status='NOT_EVALUATED',score=None,level=None,formula_version=None,
            factors={k:None for k in ['detection','corroboration','impact','anomaly','criticality']}),
        gates={k:'UNKNOWN' for k in ['evidence','target','scope','freshness','protected_assets','executor_ready']})
    validate_links(detections=detections,explanations=[],incidents=[r],decisions=[])
    return r
