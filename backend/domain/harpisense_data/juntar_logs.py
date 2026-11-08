"""Join exato de contagens de logs já agregadas; ausência nunca vira zero."""
import argparse
from pathlib import Path
import pandas as pd
from .windows import OPTIONAL_FEATURES, FEATURES, validate, read_csv

KEYS=['collection_session_id','window_id']

def join_logs(windows,logs):
    features=[c for c in OPTIONAL_FEATURES if c in logs]
    if not features: raise ValueError('Nenhuma feature de log informada')
    if not set(KEYS+['logs_complete'])<=set(logs): raise ValueError('Chaves ou logs_complete ausentes')
    if logs[KEYS].isna().any().any() or logs.duplicated(KEYS).any():
        raise ValueError('Chave de log nula ou duplicada')
    if not logs.logs_complete.map(lambda x: str(x).lower()=='true').all():
        raise ValueError('Cobertura de logs incompleta')
    if set(features)&set(windows): raise ValueError('Features de logs ja existem')
    merged=windows.merge(logs[KEYS+features],on=KEYS,how='outer',indicator=True,validate='one_to_one')
    if not merged['_merge'].eq('both').all(): raise ValueError('Cobertura deve corresponder exatamente as janelas')
    merged=merged.drop(columns='_merge')
    validate(merged,FEATURES+features,windows.traffic_profile.iloc[0],float(windows.window_seconds.iloc[0]))
    return merged

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['windows','logs','out']: p.add_argument('--'+key,required=True)
    a=p.parse_args(); result=join_logs(read_csv(a.windows),pd.read_csv(a.logs,dtype={k:str for k in KEYS}))
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    with open(a.out,'x',encoding='utf-8',newline='') as f: result.to_csv(f,index=False)
