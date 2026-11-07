"""Actual calibrated RF/IF on explicitly artificial data; no statistical claims."""
import hashlib
from pathlib import Path

import pandas as pd
from harpisense_data.windows import FEATURES
from harpisense_rf.demo_sintetico import make_session as rf_session
from harpisense_rf.random_forest import train_model as train_rf, save_bundle as save_rf
from harpisense_if.demo_sintetico import make_session as if_session
from harpisense_if.isolation_forest import train_model as train_if, save_bundle as save_if
from harpisense_xai.core import create_reference
from detection_composition.core import Composition

NOW = '2026-11-07T03:00:11+00:00'


def models(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    train = pd.concat([rf_session('train-'+str(i), 12, i) for i in range(2)])
    cal = pd.concat([rf_session('cal-'+str(i), 12, 10+i) for i in range(2)])
    train, cal = [frame[frame.label.isin(['normal','C01'])] for frame in (train, cal)]
    normal = pd.concat([if_session('normal-'+str(i), 150, 20+i) for i in range(2)])
    normal_cal = pd.concat([if_session('normal-cal-'+str(i), 150, 30+i) for i in range(2)])
    rf = train_rf(train, cal, features=FEATURES, classes=['normal','C01'], profile='demo_tcp_ingress', trees=20)
    isolation = train_if(normal, normal_cal, features=FEATURES, profile='demo_tcp_ingress', n_estimators=20)
    path = directory/'normal-training.csv'
    normal.to_csv(path, index=False)
    isolation['dataset_sha256'] = {'train':hashlib.sha256(path.read_bytes()).hexdigest()}
    save_rf(rf, directory/'rf'); save_if(isolation, directory/'if')
    args = dict(rf_directory=directory/'rf', if_directory=directory/'if',
                rf_sha256=hashlib.sha256((directory/'rf/model.joblib').read_bytes()).hexdigest(),
                if_sha256=hashlib.sha256((directory/'if/model.joblib').read_bytes()).hexdigest())
    refs = {'random_forest':create_reference(rf, max_rows=8),
            'isolation_forest':create_reference(isolation, training=path, max_rows=8)}
    return args, refs


def window(index=1, label='C01'):
    frame = rf_session('xai-http-'+str(index), 1, 90+index)
    row = frame[frame.label==label].iloc[0].to_dict()
    result = {k:v for k,v in row.items() if k in FEATURES or k in ('window_id','collection_session_id',
              'feature_schema_version','window_seconds','traffic_profile')}
    result.update(sensor_id='sensor-fixture', device_id='poste-1',
                  window_start='2026-11-07T03:00:00+00:00', window_end='2026-11-07T03:00:10+00:00')
    return result


def process(store, args, refs, index=1, label='C01'):
    return Composition(store, **args, xai_references=refs, xai_permutations=8).process_synthetic(
        window(index, label), now=NOW, asset={'asset_ref':'poste-1','criticality':50,
        'scope_ref':'synthetic-fixture','inventory_version':'synthetic-fixture-v1'})
