"""Envelope auditável para Risk Engine. Não executa nem autoriza contenção."""
import hashlib
import json
from datetime import datetime, timezone
import pandas as pd
from harpisense_rf.random_forest import predict_windows


def timestamp(value):
    stamp=pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None: raise ValueError('Timestamp deve conter timezone')
    return stamp


def risk_signal(bundle, window, *, now=None, max_age_seconds=60):
    if max_age_seconds<=0: raise ValueError('max_age_seconds deve ser positivo')
    current=timestamp(now or datetime.now(timezone.utc).isoformat())
    frame=pd.DataFrame([window])
    prediction=predict_windows(bundle,frame)[0]
    start,end=timestamp(window['window_start']),timestamp(window['window_end'])
    if abs((end-start).total_seconds()-bundle['window_seconds'])>1e-6:
        raise ValueError('Inicio/fim incompativeis com a duracao da janela')
    if end>current: raise ValueError('Janela ainda nao encerrada ou relogio incorreto')
    age=(current-end).total_seconds()
    if not isinstance(window.get('sensor_id'),str) or not window['sensor_id'].strip():
        raise ValueError('sensor_id obrigatorio no envelope operacional')
    # IP/cliente sao contexto, nunca features nem identidade autenticada por inferencia.
    entity={k:window[k] for k in ['src_ip','dst_ip','device_id','mqtt_client_id'] if k in window and pd.notna(window[k])}
    canonical=json.dumps([prediction['model_version'],window['collection_session_id'],
                          window['window_id']],ensure_ascii=False)
    return {'signal_schema_version':'harpisense.detection.rf.v1',
        'signal_id':hashlib.sha256(canonical.encode()).hexdigest(),
        **prediction,'observed_at':end.isoformat(),'generated_at':current.isoformat(),
        'window_start':start.isoformat(),'window_end':end.isoformat(),
        'sensor_id':window['sensor_id'],'entity_context':entity,
        'age_seconds':age,'status':'stale' if age>max_age_seconds else 'ok',
        'eligible_for_correlation':age<=max_age_seconds,
        'evidence':{'features':{f:float(window[f]) for f in bundle['features']}},
        'explanation_method':None,
        'risk_score':None,'decision_mode':None}


from harpisense_engines.routing import policy_route
