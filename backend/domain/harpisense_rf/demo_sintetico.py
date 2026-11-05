"""Padrões artificiais para exercitar dez rótulos; não reproduzem ataques reais."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from harpisense_data.windows import SCHEMA_VERSION,OPTIONAL_FEATURES


def make_session(session,n=30,seed=42):
    rng=np.random.default_rng(seed); rows=[]
    for k,label in enumerate(['normal']+[f'C{i:02}' for i in range(1,10)]):
        for j in range(n):
            packets=int(rng.integers(40+80*k,80+80*k)); size=int(rng.integers(60+20*k,90+20*k))
            syn=int(rng.integers(0,4)) if k!=8 else packets//2
            row=dict(window_id=f'{session}-{label}-{j}',collection_session_id=session,
                feature_schema_version=SCHEMA_VERSION,window_seconds=10.,traffic_profile='demo_tcp_ingress',
                packet_count=packets,bytes_total=packets*size,packets_per_second=packets/10,
                connections_per_second=syn/10,syn_count=syn,rst_count=int(rng.integers(0,3)),
                unique_dst_ports=int(rng.integers(1,4)) if k!=1 else 20,
                avg_packet_size=size,mean_interarrival_ms=10000/packets,label=label)
            row.update({f:0 for f in OPTIONAL_FEATURES})
            mapping={2:'mqtt_acl_denials',3:'api_auth_failures',4:'admin_auth_failures',5:'auth_failures',
                     6:'mqtt_acl_denials',7:'telemetry_identifier_conflicts',9:'mqtt_publish_count'}
            if k in mapping: row[mapping[k]]=int(rng.integers(10,40))
            rows.append(row)
    return pd.DataFrame(rows)


def generate(directory):
    out=Path(directory); out.mkdir(parents=True,exist_ok=False)
    for i,name in enumerate(['train','calibration','test']):
        pd.concat([make_session(f'{name}-{j}',40 if name=='train' else 25,100*i+j) for j in range(2)],ignore_index=True).to_csv(out/f'{name}.csv',index=False)
    (out/'SINTETICO.txt').write_text('Padrões artificiais construidos por rotulo. Nao sao ataques nem evidencia de desempenho real.\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',default='dados_demo')
    generate(p.parse_args().out)
