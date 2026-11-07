"""Relatórios, curvas OVR e diagnóstico de probabilidade."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve,precision_recall_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import make_scorer,f1_score
from harpisense_data.windows import read_csv,validate,digest,versions
from harpisense_rf.random_forest import load_bundle,predict_windows
from harpisense_rf.metricas import evaluate


def report(bundle,frame,directory,repeats=20):
    if repeats<2: raise ValueError('Minimo de duas medicoes')
    metrics=evaluate(bundle,frame)
    sample=frame.iloc[:1]; predict_windows(bundle,sample); latencies=[]
    for _ in range(repeats):
        start=time.perf_counter(); predict_windows(bundle,sample); latencies.append((time.perf_counter()-start)*1000)
    metrics['benchmark_single_window']={'median_ms':float(np.median(latencies)),
        'p95_ms':float(np.percentile(latencies,95)),'min_ms':float(min(latencies)),
        'repeats':repeats,'scope':'Validacao e predicao com modelo carregado; sem rede, janela, LLM ou executor'}
    metrics['runtime_versions']=versions()
    out=Path(directory); out.mkdir(parents=True,exist_ok=False)
    rows=predict_windows(bundle,frame)
    with (out/'predictions.jsonl').open('w') as f:
        for row,label in zip(rows,frame.label): f.write(json.dumps({**row,'true_label':label})+'\n')
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    pd.DataFrame(metrics['per_class_ovr']).T.to_csv(out/'per_class.csv')
    classes=bundle['classes']; cm=np.array(metrics['confusion_matrix'])
    pd.DataFrame(cm,index=classes,columns=classes).to_csv(out/'confusion_matrix.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,8)); ax.imshow(cm,cmap='Blues')
    for (i,j),v in np.ndenumerate(cm): ax.text(j,i,str(v),ha='center',va='center',fontsize=8)
    ax.set(xticks=range(len(classes)),yticks=range(len(classes)),xticklabels=classes,yticklabels=classes,
        xlabel='Previsto (argmax)',ylabel='Real',title='Random Forest — matriz de confusão')
    fig.tight_layout(); fig.savefig(out/'confusion_matrix.png',dpi=150); plt.close(fig)
    for kind in ['roc','precision_recall']:
        fig,ax=plt.subplots(figsize=(7,5)); count=0
        for c in classes:
            y=frame.label.eq(c).to_numpy(int)
            if len(np.unique(y))<2: continue
            scores=np.array([r['probabilities'][c] for r in rows]); count+=1
            if kind=='roc': x,z,_=roc_curve(y,scores)
            else: z,x,_=precision_recall_curve(y,scores)
            ax.plot(x,z,label=c)
        ax.set(xlabel='FPR' if kind=='roc' else 'Recall',ylabel='Recall' if kind=='roc' else 'Precisão',xlim=(0,1),ylim=(0,1))
        if count:
            ax.legend(); fig.tight_layout(); fig.savefig(out/(kind+'.png'),dpi=150)
        plt.close(fig)
    bins=metrics['probabilistic']['reliability_bins']; bins=[b for b in bins if b['n']]
    fig,ax=plt.subplots(figsize=(5,5)); ax.plot([0,1],[0,1],'--',color='gray')
    ax.plot([b['confidence'] for b in bins],[b['accuracy'] for b in bins],'o-')
    ax.set(xlabel='Confiança média',ylabel='Fração correta',xlim=(0,1),ylim=(0,1),title='Confiabilidade da classe mais provável')
    fig.tight_layout(); fig.savefig(out/'calibration.png',dpi=150); plt.close(fig)
    # Importância pós-avaliação, não usada para selecionar features neste teste.
    x=validate(frame,bundle['features'],bundle['profile'],bundle['window_seconds'])
    importance=permutation_importance(bundle['model'],x,frame.label,n_repeats=3,random_state=42,n_jobs=1,
        scoring=lambda estimator, data, truth: f1_score(truth,estimator.predict(data),labels=classes,average='macro',zero_division=0))
    pd.DataFrame({'feature':bundle['features'],'f1_macro_drop_mean':importance.importances_mean,
        'std':importance.importances_std}).to_csv(out/'permutation_importance.csv',index=False)
    (out/'LEIA_ME.md').write_text('''# Como interpretar

Métricas usam todas as previsões argmax; revisão por baixa confiança é avaliada separadamente em selective. Não excluir erros encaminhados à revisão. Matriz usa a ordem de classes no JSON. Macro inclui todas as classes do modelo; verificar suporte e classes ausentes. OVR significa uma classe contra as demais. Average precision não é AUC trapezoidal da curva PR.

Importância por permutação mede queda de F1 macro; features correlacionadas podem compartilhar ou mascarar importância. É diagnóstico pós-avaliação, não autorização para ajustar o modelo usando o teste final. Brier multiclasse é soma por observação (escala até 2); ECE usa dez intervalos de confiança da classe mais provável.

Dados artificiais não medem eficácia real no TCC. Tempo local não inclui fechamento da janela nem execução de bloqueios.
''',encoding='utf-8')
    return metrics

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['model','input','out']: p.add_argument('--'+key,required=True)
    a=p.parse_args(); report(load_bundle(a.model),read_csv(a.input),a.out)
    (Path(a.out)/'dataset_sha256.txt').write_text(digest(a.input)+'\n')
