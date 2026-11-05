"""Diagnósticos de referência; não são SHAP nem evidência causal."""
import argparse
import json
from pathlib import Path
import numpy as np
from harpisense_if.isolation_forest import validate, read_csv, load_bundle, predict_windows


def deviations(bundle, frame, top=5):
    x=validate(frame,bundle['features'],bundle['profile'],bundle['window_seconds'])
    output=[]
    for _,row in x.iterrows():
        details=[]
        for col in bundle['features']:
            ref=bundle['baseline'][col]; value=float(row[col])
            distance=abs(value-ref['median'])/max(ref['iqr'],abs(ref['median'])*.01,1e-6)
            details.append(dict(feature=col,value=value,reference_median=ref['median'],
                reference_q01=ref['q01'],reference_q99=ref['q99'],
                outside_reference=bool(value<ref['q01'] or value>ref['q99']),
                robust_deviation=distance))
        output.append(sorted(details,key=lambda d:d['robust_deviation'],reverse=True)[:top])
    return output


def monitor(bundle,frame):
    x=validate(frame,bundle['features'],bundle['profile'],bundle['window_seconds'])
    rows=predict_windows(bundle,frame)
    details={}
    for col in bundle['features']:
        ref=bundle['baseline'][col]
        outside=float(((x[col]<ref['q01'])|(x[col]>ref['q99'])).mean())
        details[col]={'outside_reference_fraction':outside,
            'median':float(x[col].median()),'training_median':ref['median'],
            'constant_feature_changed':bool(col in bundle['constant_features'] and
                                          (x[col]!=ref['median']).any())}
    return {'model_version':bundle['model_version'],'windows':len(frame),
            'anomaly_rate':float(np.mean([r['is_anomaly'] for r in rows])),
            'features':details,'automatic_retraining':False,
            'interpretation':'Desvio pode ser ataque, mudanca legitima ou falha de coleta; revisar antes de retreinar.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['model','input','out']: p.add_argument('--'+name,required=True)
    a=p.parse_args(); result=monitor(load_bundle(a.model),read_csv(a.input))
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    with open(a.out,'x',encoding='utf-8') as f: json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
