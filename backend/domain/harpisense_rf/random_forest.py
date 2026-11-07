"""HarpiSense: classificação supervisionada, calibração e contrato sem bloqueio."""
import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from harpisense_data.windows import FEATURES, OPTIONAL_FEATURES, LABELS, SCHEMA_VERSION, validate, read_csv, digest, versions, _separate

ARTIFACT_VERSION=1


def independent(bundle,frame):
    for column,key in [('collection_session_id','fitted_sessions'),('window_id','fitted_window_ids')]:
        if set(frame[column]) & set(bundle[key]):
            raise ValueError('Avaliacao compartilha '+column+' com treino/calibracao')


def train_model(train,calibration,*,profile,features=None,classes=None,window_seconds=10,
                trees=200,max_depth=16,min_samples_leaf=2,seed=42,min_confidence=.7):
    features=list(FEATURES if features is None else features)
    classes=sorted(LABELS if classes is None else classes)
    if len(classes)!=len(set(classes)) or len(classes)<2 or 'normal' not in classes or not set(classes)<=LABELS:
        raise ValueError('Classes devem incluir normal e ao menos um cenario C01-C09, sem duplicatas')
    if not 0<min_confidence<=1 or not np.isfinite(min_confidence): raise ValueError('Confianca invalida')
    if not np.isfinite(window_seconds) or window_seconds<=0: raise ValueError('Duracao invalida')
    if type(trees) is not int or not 10<=trees<=2000: raise ValueError('Arvores entre 10 e 2000')
    if type(max_depth) is not int or not 1<=max_depth<=64: raise ValueError('Profundidade entre 1 e 64')
    if type(min_samples_leaf) is not int or min_samples_leaf<1: raise ValueError('Folha minima invalida')
    x=validate(train,features,profile,window_seconds,labelled=True)
    xc=validate(calibration,features,profile,window_seconds,labelled=True)
    _separate(train,calibration)
    for name,f in [('treino',train),('calibracao',calibration)]:
        if set(f.label)!=set(classes): raise ValueError(name+': todas e apenas as classes configuradas devem estar presentes')
        for label,g in f.groupby('label'):
            if len(g)<20 or g.collection_session_id.nunique()<2:
                raise ValueError(name+': cada classe exige >=20 janelas em >=2 sessoes; minimo tecnico, nao estatistico')
    forest=RandomForestClassifier(n_estimators=trees,max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,class_weight='balanced_subsample',
        random_state=seed,n_jobs=1)
    forest.fit(x,train.label)
    calibrated=CalibratedClassifierCV(FrozenEstimator(forest),method='sigmoid')
    calibrated.fit(xc,calibration.label)
    background=x.sample(n=min(16,len(x)),random_state=seed).to_numpy().tolist()
    return dict(artifact_version=ARTIFACT_VERSION,feature_schema_version=SCHEMA_VERSION,
        model=calibrated,raw_model=forest,features=features,classes=list(calibrated.classes_),
        profile=profile,window_seconds=float(window_seconds),seed=seed,
        min_confidence=float(min_confidence),calibration='sigmoid_heldout_sessions',
        model_version='rf-'+str(uuid.uuid4()),created_at=datetime.now(timezone.utc).isoformat(),
        versions=versions(),counts={'train':len(train),'calibration':len(calibration)},
        fitted_sessions=sorted(set(train.collection_session_id)|set(calibration.collection_session_id)),
        fitted_window_ids=sorted(set(train.window_id)|set(calibration.window_id)),
        class_counts={'train':train.label.value_counts().to_dict(),'calibration':calibration.label.value_counts().to_dict()},
        parameters=forest.get_params(),background=background,
        baseline={c:{'median':float(x[c].median()),'q01':float(x[c].quantile(.01)),
                     'q99':float(x[c].quantile(.99))} for c in features},
        constant_features=[c for c in features if x[c].nunique()==1])


def predict_windows(bundle,frame):
    x=validate(frame,bundle['features'],bundle['profile'],bundle['window_seconds'])
    p=bundle['model'].predict_proba(x)
    classes=bundle['classes']; normal=classes.index('normal'); output=[]
    for (_,row),prob in zip(frame.iterrows(),p):
        idx=int(np.argmax(prob)); best=classes[idx]; confidence=float(prob[idx])
        accepted=confidence>=bundle['min_confidence']
        output.append(dict(detector='random_forest',model_version=bundle['model_version'],
            feature_schema_version=SCHEMA_VERSION,window_id=row.window_id,
            collection_session_id=row.collection_session_id,traffic_profile=bundle['profile'],
            predicted_class=best,accepted_class=best if accepted else None,
            confidence=confidence,probabilities=dict(zip(classes,map(float,prob))),
            attack_probability=float(1-prob[normal]),needs_review=not accepted,
            confidence_threshold=bundle['min_confidence'],
            suggested_action='REVIEW' if not accepted else ('MONITOR' if best=='normal' else 'ALERT'),
            severity=None,block_authorized=False))
    return output


def save_bundle(bundle,directory):
    path=Path(directory); path.mkdir(parents=True,exist_ok=False)
    joblib.dump(bundle,path/'model.joblib')
    meta={k:v for k,v in bundle.items() if k not in ['model','raw_model','background']}
    meta['artifact_sha256']=digest(path/'model.joblib')
    (path/'metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')


def load_bundle(directory):
    path=Path(directory); meta=json.loads((path/'metadata.json').read_text())
    if meta['artifact_version']!=ARTIFACT_VERSION or meta['versions']!=versions(): raise ValueError('Artefato ou ambiente incompativel')
    if digest(path/'model.joblib')!=meta['artifact_sha256']: raise ValueError('Hash divergente')
    # Apenas origem confiavel: pickle/joblib pode executar codigo antes de validar conteudo.
    bundle=joblib.load(path/'model.joblib')
    if bundle['feature_schema_version']!=SCHEMA_VERSION: raise ValueError('Schema incompativel')
    return bundle


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    t=sub.add_parser('train')
    for key in ['train','calibration','profile','out']: t.add_argument('--'+key,required=True)
    t.add_argument('--features',nargs='+',default=FEATURES); t.add_argument('--classes',nargs='+',default=sorted(LABELS))
    t.add_argument('--window-seconds',type=float,default=10); t.add_argument('--trees',type=int,default=200)
    t.add_argument('--max-depth',type=int,default=16); t.add_argument('--min-samples-leaf',type=int,default=2)
    t.add_argument('--min-confidence',type=float,default=.7); t.add_argument('--seed',type=int,default=42)
    for name in ['predict','evaluate']:
        s=sub.add_parser(name)
        for key in ['model','input','out']: s.add_argument('--'+key,required=True)
    a=p.parse_args()
    if a.command=='train':
        b=train_model(read_csv(a.train),read_csv(a.calibration),profile=a.profile,features=a.features,
            classes=a.classes,window_seconds=a.window_seconds,trees=a.trees,max_depth=a.max_depth,
            min_samples_leaf=a.min_samples_leaf,min_confidence=a.min_confidence,seed=a.seed)
        b['dataset_sha256']={k:digest(getattr(a,k)) for k in ['train','calibration']}; save_bundle(b,a.out)
    else:
        b=load_bundle(a.model); f=read_csv(a.input)
        if a.command=='evaluate':
            from harpisense_rf.metricas import evaluate
            result=evaluate(b,f)
        else: result=predict_windows(b,f)
        Path(a.out).parent.mkdir(parents=True,exist_ok=True)
        with open(a.out,'x',encoding='utf-8') as stream:
            if a.command=='evaluate': json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False)
            else:
                for row in result: stream.write(json.dumps(row,allow_nan=False)+'\n')
    print(a.out)

if __name__=='__main__': main()
