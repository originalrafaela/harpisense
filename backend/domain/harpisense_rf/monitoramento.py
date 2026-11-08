"""Distribuição observada e taxa de revisão; não retreina automaticamente."""
import argparse,json
from pathlib import Path
from harpisense_data.windows import read_csv,validate
from harpisense_rf.random_forest import load_bundle,predict_windows


def monitor(bundle,frame):
    x=validate(frame,bundle['features'],bundle['profile'],bundle['window_seconds'])
    rows=predict_windows(bundle,frame)
    return {'model_version':bundle['model_version'],'windows':len(frame),'automatic_retraining':False,
        'review_rate':sum(r['needs_review'] for r in rows)/len(rows),
        'predicted_class_fraction':{c:sum(r['predicted_class']==c for r in rows)/len(rows) for c in bundle['classes']},
        'features':{c:{'outside_reference_fraction':float(((x[c]<b['q01'])|(x[c]>b['q99'])).mean()),
            'constant_feature_changed':bool(c in bundle['constant_features'] and (x[c]!=b['median']).any())}
            for c,b in bundle['baseline'].items()},
        'note':'Referencia inclui todas as classes de treino; diagnostico nao prova drift nem ataque. Revisar coleta e rotulos.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['model','input','out']: p.add_argument('--'+key,required=True)
    a=p.parse_args(); result=monitor(load_bundle(a.model),read_csv(a.input)); Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    with open(a.out,'x') as f: json.dump(result,f,indent=2,allow_nan=False)
