"""Executa treino, recarga, métricas, explicação e sinal; apenas dados artificiais."""
import argparse,json
from pathlib import Path
from harpisense_data.windows import FEATURES,OPTIONAL_FEATURES,read_csv,digest
from harpisense_rf.demo_sintetico import generate
from harpisense_rf.random_forest import train_model,save_bundle,load_bundle
from harpisense_rf.relatorio import report
from harpisense_xai import create_reference,detection,explain
from harpisense_rf.monitoramento import monitor
from harpisense_rf.worker import Worker


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',default='demo_execucao')
    out=Path(p.parse_args().out); out.mkdir(parents=True,exist_ok=False); generate(out/'data')
    train,cal,test=[read_csv(out/'data'/f'{n}.csv') for n in ['train','calibration','test']]
    b=train_model(train,cal,profile='demo_tcp_ingress',features=FEATURES+OPTIONAL_FEATURES)
    b['dataset_sha256']={n:digest(out/'data'/f'{n}.csv') for n in ['train','calibration']}
    save_bundle(b,out/'model'); b=load_bundle(out/'model')
    m=report(b,test,out/'report')
    (out/'monitoring.json').write_text(json.dumps(monitor(b,test),indent=2),encoding='utf-8')
    row=dict(test.iloc[0].to_dict(),sensor_id='demo-edge',src_ip='192.0.2.1',dst_ip='192.0.2.2',
        window_start='2026-01-01T00:00:00Z',window_end='2026-01-01T00:00:10Z')
    ref=create_reference(b)
    det=detection(b,row,created_at='2026-01-01T00:00:15Z')
    exp,diag=explain(b,ref,det,permutations=16,created_at='2026-01-01T00:00:16Z')
    for name,value in [('background',ref),('detection',det),('explanation',exp),('diagnostics',diag)]:
        (out/(name+'.json')).write_text(json.dumps(value,indent=2))
    (out/'window.jsonl').write_text(json.dumps(row)+'\n')
    w=Worker(b,str(out/'state.db')); signal=w.process(row,now='2026-01-01T00:00:15Z'); w.close()
    (out/'risk_signal.json').write_text(json.dumps(signal,indent=2),encoding='utf-8')
    (out/'SOMENTE_DEMONSTRACAO.txt').write_text('Dados artificiais; metricas nao comprovam eficacia contra ataques reais.\n')
    print(json.dumps({'synthetic_only':True,'test_windows':m['windows'],'classes':len(b['classes']),'output':str(out)}))

if __name__=='__main__': main()
