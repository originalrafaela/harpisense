"""XAI model-agnostic: probabilidade RF calibrada e -score_samples do IF."""
import json
import math
import time
from pathlib import Path
from datetime import datetime,timezone,timedelta
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import IsolationForest
from harpisense_contracts import validate as validate_record,validate_links,fingerprint,input_fingerprint
from harpisense_data.windows import validate,versions,digest

VERSION='harpisense.xai.permutation.v1'


def kind(bundle):
    if isinstance(bundle['model'],CalibratedClassifierCV): return 'random_forest'
    if isinstance(bundle['model'],IsolationForest): return 'isolation_forest'
    raise ValueError('Exige RF calibrado ou IF dos pacotes HarpiSense')


def load_model(directory):
    p=Path(directory); meta=json.loads((p/'metadata.json').read_text())
    if meta['versions']!=versions(): raise ValueError('Ambiente diferente do treinamento')
    if digest(p/'model.joblib')!=meta['artifact_sha256']: raise ValueError('Hash do modelo divergente')
    # Nunca carregar arquivos de origem desconhecida: joblib pode executar código.
    b=joblib.load(p/'model.joblib')
    expected=1 if kind(b)=='random_forest' else 2
    if b['artifact_version']!=expected: raise ValueError('Versao de artefato incompativel')
    if b['model_version']!=meta['model_version']: raise ValueError('Versao interna divergente')
    return b


def create_reference(bundle,*,training=None,max_rows=64,seed=42):
    if type(max_rows) is not int or not 2<=max_rows<=256: raise ValueError('Background entre 2 e 256 linhas')
    if training is None:
        if kind(bundle)!='random_forest': raise ValueError('IF exige CSV normal de treino registrado no artefato')
        rows=np.asarray(bundle['background'],dtype=np.float32)
        if len(rows)>max_rows: rows=rows[np.random.default_rng(seed).choice(len(rows),max_rows,replace=False)]
        provenance={'type':'embedded_training_background','dataset_sha256':bundle.get('dataset_sha256',{}).get('train')}
    else:
        expected=bundle.get('dataset_sha256',{}).get('train')
        if not expected or digest(training)!=expected: raise ValueError('CSV deve corresponder ao hash de treino registrado')
        from harpisense_data.windows import read_csv
        frame=read_csv(training)
        x=validate(frame,bundle['features'],bundle['profile'],bundle['window_seconds'],labelled=True)
        if kind(bundle)=='isolation_forest' and not frame.label.eq('normal').all(): raise ValueError('Background IF deve ser normal')
        rows=x.sample(n=min(len(x),max_rows),random_state=seed).to_numpy(np.float32)
        provenance={'type':'verified_training_csv','dataset_sha256':expected}
    if rows.ndim!=2 or len(rows)<2 or rows.shape[1]!=len(bundle['features']) or not np.isfinite(rows).all():
        raise ValueError('Background invalido')
    ref=dict(schema_version='harpisense.xai.background.v1',model_version=bundle['model_version'],
        detector=kind(bundle),features=bundle['features'],feature_schema_version=bundle['feature_schema_version'],
        traffic_profile=bundle['profile'],window_seconds=bundle['window_seconds'],seed=seed,
        provenance=provenance,rows=rows.tolist())
    ref['reference_id']='bg-'+fingerprint(ref)
    return ref


def check_reference(bundle,ref):
    if ref.get('schema_version')!='harpisense.xai.background.v1': raise ValueError('Schema de background divergente')
    body={k:v for k,v in ref.items() if k!='reference_id'}
    if ref.get('reference_id')!='bg-'+fingerprint(body): raise ValueError('Digest do background divergente')
    for key,value in [('model_version',bundle['model_version']),('detector',kind(bundle)),('features',bundle['features']),
        ('feature_schema_version',bundle['feature_schema_version']),('traffic_profile',bundle['profile']),('window_seconds',bundle['window_seconds'])]:
        if ref.get(key)!=value: raise ValueError('Background incompativel: '+key)
    rows=np.asarray(ref['rows'],dtype=np.float32)
    if rows.ndim!=2 or not 2<=len(rows)<=256 or rows.shape[1]!=len(bundle['features']) or not np.isfinite(rows).all(): raise ValueError('Background invalido')
    return rows


def detection(bundle,window,*,created_at=None,max_age_seconds=60):
    from harpisense_contracts.validation import timestamp
    from harpisense_contracts import detection_from_legacy
    if type(max_age_seconds) not in [int,float] or not math.isfinite(max_age_seconds) or max_age_seconds<=0: raise ValueError('Frescor invalido')
    frame=pd.DataFrame([window]);x=validate(frame,bundle['features'],bundle['profile'],bundle['window_seconds'])
    now=created_at or datetime.now(timezone.utc).isoformat()
    age=(timestamp(now)-timestamp(window['window_end'])).total_seconds()
    if abs((timestamp(window['window_end'])-timestamp(window['window_start'])).total_seconds()-bundle['window_seconds'])>1e-6: raise ValueError('Duracao divergente')
    name=kind(bundle)
    r=dict(signal_schema_version='harpisense.detection.'+('rf' if name=='random_forest' else 'if')+'.v1',
        signal_id=fingerprint([name,bundle['model_version'],window['collection_session_id'],window['window_id']]),
        generated_at=now,window_start=window['window_start'],window_end=window['window_end'],age_seconds=age,
        status='ok' if age<=max_age_seconds else 'stale',eligible_for_correlation=age<=max_age_seconds,
        detector=name,model_version=bundle['model_version'],window_id=window['window_id'],
        collection_session_id=window['collection_session_id'],sensor_id=window['sensor_id'],
        feature_schema_version=bundle['feature_schema_version'],traffic_profile=bundle['profile'],block_authorized=False,
        entity_context={k:window[k] for k in ['src_ip','dst_ip','device_id','mqtt_client_id'] if k in window and pd.notna(window[k])},
        evidence={'features':{f:float(x.iloc[0][f]) for f in bundle['features']}})
    if name=='random_forest':
        p=bundle['model'].predict_proba(x)[0]; classes=list(bundle['model'].classes_)
        if classes!=bundle['classes']: raise ValueError('Ordem de classes divergente')
        winner=classes[int(np.argmax(p))]; confidence=float(max(p)); review=confidence<bundle['min_confidence']
        r.update(predicted_class=winner,accepted_class=None if review else winner,probabilities=dict(zip(classes,map(float,p))),
            confidence=confidence,attack_probability=float(1-p[classes.index('normal')]),
            confidence_threshold=bundle['min_confidence'],needs_review=review)
    else:
        score=float(-bundle['model'].score_samples(x)[0]);threshold=bundle['threshold']
        r.update(anomaly_score=score,anomaly_threshold=threshold,anomaly_margin=score-threshold,
            is_anomaly=score>threshold,normal_reference_percentile=float(np.searchsorted(bundle['calibration_scores'],score,side='right')/len(bundle['calibration_scores'])))
    return detection_from_legacy(r,max_age_seconds=max_age_seconds)


def explain(bundle,ref,record,*,target_class=None,permutations=32,seed=42,created_at=None):
    validate_record(record);background=check_reference(bundle,ref)
    if type(permutations) is not int or not 2<=permutations<=256: raise ValueError('Permutacoes entre 2 e 256')
    if record['model']['model_version']!=bundle['model_version'] or record['model']['detector']!=kind(bundle): raise ValueError('Deteccao de outro modelo')
    if record['window']['feature_schema_version']!=bundle['feature_schema_version'] or record['window']['traffic_profile']!=bundle['profile']: raise ValueError('Perfil/schema divergente')
    if set(record['features'])!=set(bundle['features']): raise ValueError('Features divergentes')
    x=np.array([record['features'][f] for f in bundle['features']],dtype=np.float32)
    name=kind(bundle)
    from harpisense_contracts.validation import timestamp
    duration=(timestamp(record['window']['end'])-timestamp(record['window']['start'])).total_seconds()
    if abs(duration-bundle['window_seconds'])>1e-6: raise ValueError('Duracao divergente')
    if name=='random_forest':
        if list(bundle['model'].classes_)!=bundle['classes']: raise ValueError('Ordem de classes divergente')
        label=target_class or record['classification']['predicted_class']
        if label not in bundle['classes']: raise ValueError('Classe nao treinada')
        index=bundle['classes'].index(label);output_name='CALIBRATED_CLASS_PROBABILITY'
        def score(a): return bundle['model'].predict_proba(pd.DataFrame(a,columns=bundle['features']))[:,index]
        operational=record['classification']['probabilities'][label]
    else:
        if target_class is not None: raise ValueError('IF nao tem classe explicada')
        if abs(record['anomaly']['anomaly_threshold']-bundle['threshold'])>1e-12: raise ValueError('Limiar operacional divergente')
        label=None;output_name='ANOMALY_SCORE'
        def score(a): return -bundle['model'].score_samples(pd.DataFrame(a,columns=bundle['features']))
        operational=record['anomaly']['anomaly_score']
    start=time.perf_counter();actual=float(score(x[None,:])[0]);base=float(score(background).mean())
    if abs(actual-operational)>1e-6: raise ValueError('Saida da deteccao nao corresponde ao modelo carregado')
    actual,base,values,residual,runs=estimate(score,x,background,permutations=permutations,seed=seed)
    now=created_at or datetime.now(timezone.utc).isoformat()
    params=dict(seed=seed,permutations=permutations,background_rows=len(background))
    result=dict(schema_version='1.0.0',record_type='explanation',
        explanation_id='exp-'+fingerprint([record['detection_id'],VERSION,ref['reference_id'],label,params]),created_at=now,
        detection_id=record['detection_id'],window_id=record['window']['window_id'],collection_session_id=record['window']['collection_session_id'],
        model_version=bundle['model_version'],input_fingerprint=record['input_fingerprint'],method='SHAPLEY_PERMUTATION',
        explainer_version=VERSION,reference_ref=ref['reference_id'],target=dict(output=output_name,class_label=label),
        base_value=base,output_value=actual,contributions=[dict(feature=f,value=float(x[i]),contribution=float(values[i])) for i,f in enumerate(bundle['features'])],
        additivity_residual=residual,parameters=params,
        limitations=['Estimativa Shapley por permutacoes; nao e TreeSHAP nem prova causal.',
            'Intervencoes podem quebrar correlacoes entre features derivadas; interpretacao depende do background.',
            'Erro Monte Carlo nao cobre incerteza do modelo ou representatividade da referencia.'])
    validate_links(detections=[record],explanations=[result],incidents=[],decisions=[])
    diagnostics={'explanation_id':result['explanation_id'],'elapsed_ms':(time.perf_counter()-start)*1000,
        'monte_carlo_standard_error':dict(zip(bundle['features'],map(float,runs.std(axis=0,ddof=1)/np.sqrt(permutations)))),
        'reference_id':ref['reference_id'],'operational_output':actual}
    if name=='isolation_forest':
        diagnostics.update(anomaly_threshold=bundle['threshold'],is_anomaly=record['anomaly']['is_anomaly'],
            anomaly_margin=actual-bundle['threshold'],margin_base_value=base-bundle['threshold'],
            interpretation='Contribuicao positiva aumenta o score de anomalia. Margem usa as mesmas contribuicoes e base menos limiar.')
    else: diagnostics['interpretation']='Contribuicao positiva aumenta a probabilidade da classe explicada, inclusive quando a classe e normal.'
    return result,diagnostics


def estimate(score,x,background,*,permutations,seed):
    """Núcleo numérico único, compartilhado com a API legada RF."""
    actual=float(score(x[None,:])[0]);base=float(score(background).mean())
    rng=np.random.default_rng(seed);runs=[]
    for _ in range(permutations):
        order=rng.permutation(len(x));state=background.copy();stages=[state]
        for j in order:
            state=state.copy();state[:,j]=x[j];stages.append(state)
        means=score(np.concatenate(stages)).reshape(len(x)+1,len(background)).mean(axis=1)
        values=np.zeros(len(x));values[order]=np.diff(means);runs.append(values)
    runs=np.asarray(runs);values=runs.mean(axis=0);residual=actual-base-float(values.sum())
    return actual,base,values,residual,runs
