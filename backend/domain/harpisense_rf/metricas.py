"""Métricas multiclasse, binárias, probabilísticas e de abstenção."""
import time
import numpy as np
from sklearn.metrics import (accuracy_score,classification_report,confusion_matrix,
    f1_score,roc_auc_score,average_precision_score,log_loss,matthews_corrcoef)
from harpisense_data.windows import validate,LABELS
from harpisense_rf.random_forest import independent,predict_windows


def ratio(a,b): return float(a/b) if b else None


def binary(y,p,score):
    tn,fp,fn,tp=confusion_matrix(y,p,labels=[0,1]).ravel()
    both=len(np.unique(y))==2
    return {'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp),
        'accuracy':float(accuracy_score(y,p)),'precision':ratio(tp,tp+fp),
        'recall':ratio(tp,tp+fn),'f1':ratio(2*tp,2*tp+fp+fn),
        'fpr':ratio(fp,fp+tn),'fnr':ratio(fn,fn+tp),'specificity':ratio(tn,tn+fp),
        'roc_auc':float(roc_auc_score(y,score)) if both else None,
        'average_precision':float(average_precision_score(y,score)) if both else None,
        'brier_score':float(np.mean((np.asarray(score)-y)**2))}


def bootstrap(frame,pred,classes,repeats=300):
    groups=list(frame.groupby('collection_session_id').indices.values())
    if len(groups)<2: return {'available':False,'reason':'Menos de duas sessoes'}
    rng=np.random.default_rng(42); values={'accuracy':[],'f1_macro':[],'binary_recall':[],'binary_fpr':[]}
    truth=frame.label.to_numpy()
    for _ in range(repeats):
        ix=np.concatenate([groups[i] for i in rng.integers(len(groups),size=len(groups))])
        y,p=truth[ix],pred[ix]; pos=y!='normal'; alert=p!='normal'
        values['accuracy'].append(float(np.mean(y==p)))
        values['f1_macro'].append(float(f1_score(y,p,labels=classes,average='macro',zero_division=0)))
        for name,mask in [('binary_recall',pos),('binary_fpr',~pos)]:
            if mask.any(): values[name].append(float(alert[mask].mean()))
    return {'available':True,'unit':'session','repeats':repeats,'seed':42,
        'warning':'Exploratorio; classes ausentes em reamostragens entram como zero no F1 macro fixo.',
        'intervals95':{k:{'low':float(np.quantile(v,.025)) if v else None,
            'high':float(np.quantile(v,.975)) if v else None,'valid_repeats':len(v)} for k,v in values.items()}}


def evaluate(bundle,frame):
    validate(frame,bundle['features'],bundle['profile'],bundle['window_seconds'],labelled=True)
    independent(bundle,frame)
    classes=bundle['classes']
    if not set(frame.label)<=set(classes): raise ValueError('Teste contem classe nao treinada; usar avaliacao aberta separada')
    start=time.perf_counter(); rows=predict_windows(bundle,frame); elapsed=(time.perf_counter()-start)*1000
    truth=frame.label.to_numpy(); pred=np.array([r['predicted_class'] for r in rows])
    prob=np.array([[r['probabilities'][c] for c in classes] for r in rows])
    attack=np.array([r['attack_probability'] for r in rows]); accepted=np.array([not r['needs_review'] for r in rows])
    report=classification_report(truth,pred,labels=classes,output_dict=True,zero_division=0)
    cm=confusion_matrix(truth,pred,labels=classes); per={}
    for i,c in enumerate(classes):
        y=(truth==c).astype(int); yp=(pred==c).astype(int)
        per[c]={**report[c],**binary(y,yp,prob[:,i])}
    confidence=prob.max(axis=1); correct=truth==pred; bins=[]; ece=0.
    for i in range(10):
        mask=(confidence>=i/10)&(confidence<(i+1)/10 if i<9 else confidence<=1)
        n=int(mask.sum()); acc=float(correct[mask].mean()) if n else None; conf=float(confidence[mask].mean()) if n else None
        if n: ece+=n/len(frame)*abs(acc-conf)
        bins.append({'lower':i/10,'upper':(i+1)/10,'n':n,'accuracy':acc,'confidence':conf})
    onehot=np.array([[int(y==c) for c in classes] for y in truth])
    binary_result=binary((truth!='normal').astype(int),(pred!='normal').astype(int),attack)
    supported=[c for c in classes if (truth==c).any()]
    return {'model_version':bundle['model_version'],'windows':len(frame),'classes':classes,
        'class_support':{c:int((truth==c).sum()) for c in classes},
        'missing_classes':[c for c in classes if c not in supported],
        'accuracy':float(accuracy_score(truth,pred)),
        'balanced_accuracy_present_classes':float(np.mean([per[c]['recall'] for c in supported])),
        'f1_macro':float(f1_score(truth,pred,labels=classes,average='macro',zero_division=0)),
        'f1_weighted':float(f1_score(truth,pred,labels=classes,average='weighted',zero_division=0)),
        'f1_micro':float(f1_score(truth,pred,labels=classes,average='micro',zero_division=0)),
        'mcc':float(matthews_corrcoef(truth,pred)) if len(set(truth))>1 else None,
        'per_scenario':{c:{'windows':int((truth==c).sum()),
            'attack_detection_rate':float((pred[truth==c]!='normal').mean()) if (truth==c).any() else None,
            'correct_class_recall':per[c]['recall']} for c in classes if c!='normal'},
        'roc_auc_macro_ovr_supported':float(np.mean([v['roc_auc'] for v in per.values() if v['roc_auc'] is not None])) if any(v['roc_auc'] is not None for v in per.values()) else None,
        'average_precision_macro_ovr_supported':float(np.mean([v['average_precision'] for v in per.values() if v['average_precision'] is not None])) if any(v['average_precision'] is not None for v in per.values()) else None,
        'classification_report':report,'per_class_ovr':per,'confusion_matrix':cm.tolist(),
        'binary_attack_detection':binary_result,
        'probabilistic':{'log_loss':float(log_loss(truth,prob,labels=classes)),
            'multiclass_brier_sum':float(np.mean(np.sum((prob-onehot)**2,axis=1))),
            'ece_top_label_10_bins':ece,'reliability_bins':bins},
        'selective':{'threshold':bundle['min_confidence'],'coverage':float(accepted.mean()),
            'review_count':int((~accepted).sum()),
            'accuracy_accepted':float(correct[accepted].mean()) if accepted.any() else None,
            'attack_recall_accepted':ratio(int(((pred!='normal')&accepted&(truth!='normal')).sum()),int((truth!='normal').sum()))},
        'per_session':{str(s):{'n':len(ix),'accuracy':float(correct[ix].mean()),
            'binary':binary((truth[ix]!='normal').astype(int),(pred[ix]!='normal').astype(int),attack[ix])}
            for s,ix in frame.groupby('collection_session_id').indices.items()},
        'bootstrap':bootstrap(frame,pred,classes),
        'inference_batch_ms':elapsed,'amortized_ms_per_window':elapsed/len(frame),
        'convention':'Argmax avaliado em todas as janelas; abstenção separada. Report sklearn usa zero_division=0; taxas indefinidas em OVR usam null. Macro inclui todas as classes configuradas.'}
