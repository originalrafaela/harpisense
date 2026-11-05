"""Dados artificiais apenas para verificar o funcionamento do codigo."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
from harpisense_if.isolation_forest import SCHEMA_VERSION


def make_session(session, n, seed, label='normal'):
    rng = np.random.default_rng(seed)
    packets = rng.integers(30, 100, n)
    size = rng.integers(80, 300, n)
    syn = rng.integers(0, 4, n)
    if label != 'normal':
        packets = rng.integers(1000, 5000, n)
        syn = packets // 2
    total = packets * size
    return pd.DataFrame({
        'window_id': [f'{session}-{i}' for i in range(n)],
        'collection_session_id': session,
        'feature_schema_version': SCHEMA_VERSION,
        'window_seconds': 10.0,
        'traffic_profile': 'demo_tcp_ingress',
        'packet_count': packets, 'bytes_total': total,
        'packets_per_second': packets / 10,
        'connections_per_second': syn / 10,
        'syn_count': syn, 'rst_count': rng.integers(0, 3, n),
        'unique_dst_ports': rng.integers(1, 4, n),
        'avg_packet_size': size,
        'mean_interarrival_ms': 10000 / packets,
        'label': label,
    })


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', default='dados_demo')
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    for name, sessions in {
        'train': [make_session(f'train-{i}', 150, i) for i in range(3)],
        'calibration': [make_session(f'cal-{i}', 150, 10+i) for i in range(2)],
        'test': [make_session('test-normal', 150, 20),
                 make_session('test-carga', 100, 21, 'C08')],
    }.items():
        pd.concat(sessions, ignore_index=True).to_csv(out / f'{name}.csv', index=False)
    print('Dados SINTETICOS criados. Nao representam resultados do TCC.')

if __name__ == '__main__':
    main()
