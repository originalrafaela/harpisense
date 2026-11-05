"""Avaliação binária, gráficos e benchmark local. Não mede contenção real."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, roc_curve
from harpisense_if.isolation_forest import evaluate, predict_windows, read_csv, load_bundle, digest, versions


def benchmark(bundle,frame,repeats=50):
    if repeats < 2: raise ValueError('Ao menos duas repeticoes')
    sample=frame.iloc[:1]
    predict_windows(bundle,sample)  # aquecimento fora da medição
    times=[]
    for _ in range(repeats):
        start=time.perf_counter()
        predict_windows(bundle,sample)
        times.append((time.perf_counter()-start)*1000)
    return {'repeats':repeats,'batch_size':1,'median_ms':float(np.median(times)),
        'p95_ms':float(np.percentile(times,95)), 'min_ms':float(min(times)),
        'scope':'validacao + inferencia + serializacao em memoria; modelo ja carregado; sem rede/disco'}


def report(bundle,frame,out,repeats=50):
    metrics=evaluate(bundle,frame)
    metrics['benchmark_single_window']=benchmark(bundle,frame,repeats)
    metrics['runtime_versions']=versions()
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    rows=predict_windows(bundle,frame)
    pred=pd.DataFrame(rows)
    pred['label']=frame.label.to_numpy()
    pred.to_csv(out/'predictions.csv',index=False)
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    cm=metrics['confusion_matrix']
    pd.DataFrame([[cm['tn'],cm['fp']],[cm['fn'],cm['tp']]],
        index=['real_normal','real_ataque'],columns=['prev_normal','prev_anomalia']).to_csv(out/'confusion_matrix.csv')
    pd.DataFrame(metrics['per_scenario']).T.to_csv(out/'scenarios.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(5,4))
    matrix=np.array([[cm['tn'],cm['fp']],[cm['fn'],cm['tp']]])
    ax.imshow(matrix,cmap='Blues')
    for (i,j),v in np.ndenumerate(matrix): ax.text(j,i,str(v),ha='center',va='center')
    ax.set(xticks=[0,1],yticks=[0,1],xticklabels=['Normal','Anomalia'],
        yticklabels=['Normal','Ataque'],xlabel='Previsão',ylabel='Real',title='Matriz de confusão')
    fig.tight_layout(); fig.savefig(out/'confusion_matrix.png',dpi=160); plt.close(fig)
    y=frame.label.ne('normal').to_numpy(int); scores=pred.anomaly_score.to_numpy()
    if len(np.unique(y))==2:
        for filename, x, yv, xlabel, ylabel in [
            ('roc',*roc_curve(y,scores)[:2],'Taxa de falsos positivos','Recall'),
            ('precision_recall',precision_recall_curve(y,scores)[1],precision_recall_curve(y,scores)[0],'Recall','Precisão')]:
            fig,ax=plt.subplots(figsize=(5,4)); ax.plot(x,yv)
            ax.set(xlabel=xlabel,ylabel=ylabel,xlim=(0,1),ylim=(0,1)); ax.grid(alpha=.2)
            fig.tight_layout(); fig.savefig(out/(filename+'.png'),dpi=160); plt.close(fig)
    (out/'LEIA_ME.md').write_text('# Relatório de avaliação\n\n'
        'Ataque é a classe positiva. O IF detecta anomalia, não o tipo C01–C09.\n'
        'Cenários sem amostras têm taxa nula (null), não zero.\n'
        'Acurácia e F1 devem ser lidos junto ao suporte, FPR e recall.\n'
        'Average precision não é a integral trapezoidal da curva PR.\n'
        'Latência local não inclui espera da janela, rede, LLM ou executor.\n'
        'Resultados de dados artificiais não são evidência de eficácia no TCC.\n',encoding='utf-8')
    return metrics

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ['model','input','out']: p.add_argument('--'+arg,required=True)
    p.add_argument('--repeats',type=int,default=50)
    a=p.parse_args()
    report(load_bundle(a.model),read_csv(a.input),a.out,a.repeats)
    (Path(a.out)/'dataset_sha256.txt').write_text(digest(a.input)+'\n',encoding='utf-8')
