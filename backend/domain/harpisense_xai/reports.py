"""Relatórios locais e agregação apenas entre alvos comparáveis."""
import json
from pathlib import Path
import pandas as pd
from harpisense_contracts import validate


def write_results(directory,record,explanation,diagnostics):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    p=Path(directory);p.mkdir(parents=True,exist_ok=False)
    for name,value in [('detection',record),('explanation',explanation),('diagnostics',diagnostics)]:
        (p/(name+'.json')).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    rows=pd.DataFrame(explanation['contributions'])
    rows['monte_carlo_standard_error']=rows.feature.map(diagnostics['monte_carlo_standard_error'])
    rows.to_csv(p/'contributions.csv',index=False)
    rows=rows.sort_values('contribution',key=abs)
    fig,ax=plt.subplots(figsize=(10,max(4,len(rows)*.32)))
    ax.barh(rows.feature,rows.contribution,xerr=rows.monte_carlo_standard_error,
            color=['#b54840' if v>0 else '#317ca5' for v in rows.contribution])
    ax.axvline(0,color='#333333',linewidth=.7)
    target=explanation['target'];label=target['class_label'] or 'IF: -score_samples'
    ax.set_title(f'{label}\nBase {explanation["base_value"]:.6f} → saída {explanation["output_value"]:.6f}')
    ax.set_xlabel('Contribuição Shapley estimada; barras: ±1 erro padrão Monte Carlo')
    fig.tight_layout();fig.savefig(p/'contributions.png',dpi=160);plt.close(fig)


def aggregate(explanations):
    """Média |phi| por alvo/modelo/referência; não mistura classes nem escalas."""
    rows=[];seen=set()
    for e in explanations:
        validate(e)
        if e['explanation_id'] in seen: raise ValueError('Explicação repetida')
        seen.add(e['explanation_id'])
        for c in e['contributions']:
            rows.append(dict(model_version=e['model_version'],reference_ref=e['reference_ref'],
                explainer_version=e['explainer_version'],method=e['method'],
                output=e['target']['output'],class_label=e['target']['class_label'] or '',
                feature=c['feature'],absolute_contribution=abs(c['contribution'])))
    if not rows: raise ValueError('Nenhuma explicação')
    keys=['model_version','reference_ref','explainer_version','method','output','class_label','feature']
    return pd.DataFrame(rows).groupby(keys,dropna=False).absolute_contribution.agg(
        mean_absolute_contribution='mean',n_explanations='count').reset_index()
