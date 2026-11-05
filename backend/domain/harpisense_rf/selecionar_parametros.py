"""Busca opcional apenas no treino, com folds separados por sessão."""
import argparse,json
from pathlib import Path
from sklearn.model_selection import StratifiedGroupKFold,GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import make_scorer,f1_score
from harpisense_data.windows import read_csv,validate,FEATURES,digest


def group_splits(frame,folds=3):
    if type(folds) is not int or folds<2: raise ValueError('Ao menos dois folds')
    splitter=StratifiedGroupKFold(n_splits=folds,shuffle=True,random_state=42)
    splits=list(splitter.split(frame,frame.label,frame.collection_session_id))
    classes=set(frame.label)
    for train,val in splits:
        if set(frame.iloc[train].collection_session_id)&set(frame.iloc[val].collection_session_id): raise ValueError('Vazamento entre sessoes')
        if set(frame.iloc[train].label)!=classes or set(frame.iloc[val].label)!=classes:
            raise ValueError('Fold sem classe: coletar mais sessoes ou revisar numero de folds')
    return splits

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['train','profile','out']: p.add_argument('--'+key,required=True)
    p.add_argument('--features',nargs='+',default=FEATURES); p.add_argument('--folds',type=int,default=3)
    p.add_argument('--window-seconds',type=float,default=10)
    a=p.parse_args(); frame=read_csv(a.train); x=validate(frame,a.features,a.profile,a.window_seconds,labelled=True)
    splits=group_splits(frame,a.folds); classes=sorted(frame.label.unique())
    search=GridSearchCV(RandomForestClassifier(n_estimators=100,class_weight='balanced_subsample',random_state=42,n_jobs=1),
        {'max_depth':[8,16],'min_samples_leaf':[2,5]},
        scoring=lambda estimator, data, truth: f1_score(truth,estimator.predict(data),labels=classes,average='macro',zero_division=0),cv=splits,n_jobs=1,refit=False,error_score='raise')
    search.fit(x,frame.label)
    result={'train_sha256':digest(a.train),'folds':a.folds,'best_params':search.best_params_,
        'cv_f1_macro':float(search.best_score_),
        'candidates':[{'params':p,'mean_f1_macro':float(m),'std':float(s)} for p,m,s in zip(search.cv_results_['params'],search.cv_results_['mean_test_score'],search.cv_results_['std_test_score'])],
        'note':'Somente selecao no treino; ajustar modelo final e calibrar em sessoes distintas. Teste final ainda necessario.'}
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    with open(a.out,'x') as f: json.dump(result,f,indent=2,allow_nan=False)
