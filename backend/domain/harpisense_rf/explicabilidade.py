"""API legada de compatibilidade. Novos consumidores devem usar harpisense_xai."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from harpisense_data.windows import validate,read_csv
from harpisense_rf.random_forest import load_bundle


def explain(bundle,frame,*,target_class=None,permutations=32,seed=42):
    if len(frame)!=1: raise ValueError('Explicar uma janela por chamada')
    if type(permutations) is not int or not 2<=permutations<=256: raise ValueError('Permutacoes entre 2 e 256')
    x=validate(frame,bundle['features'],bundle['profile'],bundle['window_seconds']).iloc[0].to_numpy()
    model=bundle['model']; features=bundle['features']; classes=bundle['classes']
    p=model.predict_proba(pd.DataFrame([x],columns=features))[0]
    target=target_class or classes[int(np.argmax(p))]
    if target not in classes: raise ValueError('Classe desconhecida')
    from harpisense_xai.core import estimate,create_reference,check_reference
    idx=classes.index(target)
    background=check_reference(bundle,create_reference(bundle))
    def score(a):return model.predict_proba(pd.DataFrame(a,columns=features))[:,idx]
    actual,base,contributions,residual,runs=estimate(score,x,background,permutations=permutations,seed=seed)
    if abs(residual)>1e-6:raise ValueError('Falha de aditividade')
    return {'model_version':bundle['model_version'],'window_id':frame.iloc[0].window_id,
        'method':'interventional_shapley_permutation_monte_carlo',
        'output':'calibrated_class_probability','class':target,'base_value':base,
        'predicted_probability':float(p[idx]),'additivity_residual':residual,
        'permutations':permutations,'background_rows':len(background),'seed':seed,
        'contributions':[{ 'feature':f,'value':float(x[i]),'shapley_estimate':float(contributions[i]),
            'monte_carlo_standard_error':float(runs[:,i].std(ddof=1)/np.sqrt(permutations))}
            for i,f in enumerate(features)],
        'caveat':'Estimativa dependente da referencia; combinacoes artificiais podem violar correlacoes. Nao causal; executar fora do caminho critico.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['model','input','out']: p.add_argument('--'+key,required=True)
    p.add_argument('--row',type=int,default=0); p.add_argument('--permutations',type=int,default=32)
    a=p.parse_args(); result=explain(load_bundle(a.model),read_csv(a.input).iloc[[a.row]],permutations=a.permutations)
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    with open(a.out,'x',encoding='utf-8') as f: json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
