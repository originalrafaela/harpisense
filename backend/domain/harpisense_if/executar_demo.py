"""Demonstração reproduzível completa. Nunca corresponde a resultados reais do TCC."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
import pandas as pd
from harpisense_if.isolation_forest import train_model, save_bundle, load_bundle, read_csv, predict_windows, digest
from harpisense_if.relatorio import report
from harpisense_if.monitoramento import monitor
from harpisense_if.worker import Worker


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',default='demo_execucao')
    a=p.parse_args(); out=Path(a.out); out.mkdir(parents=True,exist_ok=False)
    subprocess.run([sys.executable,'-m','harpisense_if.demo_sintetico','--out',str(out/'data')],check=True)
    train,cal,test=[read_csv(out/'data'/f'{name}.csv') for name in ['train','calibration','test']]
    bundle=train_model(train,cal,profile='demo_tcp_ingress')
    bundle['dataset_sha256']={name:digest(out/'data'/f'{name}.csv') for name in ['train','calibration']}
    save_bundle(bundle,out/'model'); bundle=load_bundle(out/'model')
    metrics=report(bundle,test,out/'report',repeats=20)
    (out/'monitoring.json').write_text(json.dumps(monitor(bundle,test),indent=2),encoding='utf-8')
    row=dict(test.iloc[0].to_dict(),sensor_id='demo-edge',src_ip='192.0.2.10',dst_ip='192.0.2.20',
        window_start='2026-01-01T00:00:00Z',window_end='2026-01-01T00:00:10Z')
    with (out/'window.jsonl').open('w') as f: f.write(json.dumps(row)+'\n')
    w=Worker(bundle,str(out/'state.db'))
    signal=w.process(row,now='2026-01-01T00:00:15Z'); w.close()
    (out/'risk_signal.json').write_text(json.dumps(signal,indent=2),encoding='utf-8')
    (out/'SOMENTE_DEMONSTRACAO.txt').write_text('Dados artificiais. Nao usar metricas como resultados experimentais do TCC.\n')
    print(json.dumps({'synthetic_only':True,'windows':metrics['windows'],'report':str(out/'report')}))

if __name__=='__main__': main()
