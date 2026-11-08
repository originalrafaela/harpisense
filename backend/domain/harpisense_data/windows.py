"""Contrato compartilhado de janelas HarpiSense; schema legado IF v1 preservado."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import scipy
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (average_precision_score, confusion_matrix,
    precision_recall_fscore_support, roc_auc_score, accuracy_score, classification_report)

SCHEMA_VERSION = 'harpisense.if.window.v1'
FEATURES = [
    'packet_count', 'bytes_total', 'packets_per_second',
    'connections_per_second', 'syn_count', 'rst_count',
    'unique_dst_ports', 'avg_packet_size', 'mean_interarrival_ms',
]
OPTIONAL_FEATURES = ['connection_failures', 'auth_failures', 'auth_successes',
    'mqtt_publish_count', 'mqtt_acl_denials', 'api_auth_failures',
    'admin_auth_failures', 'telemetry_identifier_conflicts', 'telemetry_stale_count']
COUNT_FEATURES = {'packet_count', 'bytes_total', 'syn_count', 'rst_count',
    'unique_dst_ports', *OPTIONAL_FEATURES}
from harpisense_catalog import SCENARIOS
LABELS = {'normal', *SCENARIOS}
META = ['window_id', 'collection_session_id', 'feature_schema_version',
        'window_seconds', 'traffic_profile']


def versions():
    return {'python': platform.python_version(), 'scikit_learn': sklearn.__version__,
            'scipy': scipy.__version__, 'numpy': np.__version__, 'pandas': pd.__version__, 'joblib': joblib.__version__}


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as stream:
        header = next(csv.reader(stream), [])
    if not header or len(header) != len(set(header)):
        raise ValueError('Cabecalho vazio ou com colunas duplicadas')
    return pd.read_csv(path, dtype={c: str for c in META if c != 'window_seconds'})


def validate(frame, features, profile, window_seconds, *, labelled=False):
    """Falhar explicitamente em dados ausentes; zero nao substitui desconhecido."""
    if frame.empty or frame.columns.duplicated().any():
        raise ValueError('Dataset vazio ou com colunas duplicadas')
    if not features or len(features) != len(set(features)):
        raise ValueError('Lista de features vazia ou duplicada')
    if not set(features) <= set(FEATURES + OPTIONAL_FEATURES):
        raise ValueError('Feature nao permitida; IP, rotulo e IDs nunca entram no modelo')
    required = set(META + FEATURES + features + (['label'] if labelled else []))
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f'Colunas ausentes: {sorted(missing)}')
    for col in [c for c in META if c != 'window_seconds']:
        values = frame[col]
        if not values.map(lambda x: isinstance(x, str) and bool(x.strip())).all():
            raise ValueError(f'Metadado invalido: {col}')
    if frame['window_id'].duplicated().any():
        raise ValueError('window_id deve ser unico no arquivo')
    if not frame['feature_schema_version'].eq(SCHEMA_VERSION).all():
        raise ValueError('Versao de features incompatível')
    if not frame['traffic_profile'].eq(profile).all():
        raise ValueError('Nao misture perfis de trafego no mesmo modelo')
    duration = pd.to_numeric(frame['window_seconds'], errors='raise').to_numpy(float)
    if not np.isfinite(duration).all() or not np.allclose(duration, window_seconds):
        raise ValueError('Duracao da janela diferente da configuracao')
    cols = list(dict.fromkeys(FEATURES + features))
    for col in cols:
        if frame[col].map(lambda x: isinstance(x, (bool, np.bool_))).any():
            raise ValueError(f'Booleano nao aceito em {col}')
    numeric = frame[cols].apply(pd.to_numeric, errors='raise')
    values = numeric.to_numpy(dtype=np.float64)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('Features precisam ser numericas, finitas e nao negativas')
    if (values > np.finfo(np.float32).max).any():
        raise ValueError('Feature fora do intervalo numerico do estimador')
    for col in set(cols) & COUNT_FEATURES:
        if not np.equal(numeric[col], np.floor(numeric[col])).all():
            raise ValueError(f'Contagem fracionaria: {col}')
    packets = numeric['packet_count'].to_numpy()
    for col in ['syn_count', 'rst_count', 'unique_dst_ports']:
        if (numeric[col].to_numpy() > packets).any():
            raise ValueError(f'{col} maior que packet_count')
    if not np.allclose(numeric['packets_per_second'], packets / duration,
                       rtol=1e-4, atol=1e-6):
        raise ValueError('packets_per_second inconsistente com contagem e janela')
    if (numeric['connections_per_second'] * duration > numeric['syn_count'] + 1e-5).any():
        raise ValueError('Tentativas de conexao excedem SYN observado')
    expected_avg = np.divide(numeric['bytes_total'], packets,
                            out=np.zeros(len(frame)), where=packets > 0)
    if not np.allclose(numeric['avg_packet_size'], expected_avg,
                       rtol=1e-4, atol=1e-6):
        raise ValueError('avg_packet_size inconsistente')
    empty = packets == 0
    if (numeric.loc[empty, 'bytes_total'] != 0).any():
        raise ValueError('Janela sem pacotes com bytes positivos')
    if (numeric.loc[packets <= 1, 'mean_interarrival_ms'] != 0).any():
        raise ValueError('Intervalo medio deve ser zero quando ha ate um pacote')
    if (numeric['mean_interarrival_ms'] > window_seconds * 1000).any():
        raise ValueError('Intervalo medio maior que janela')
    if labelled and (frame['label'].isna().any() or
                     not set(frame['label']) <= LABELS):
        raise ValueError('Rotulos aceitos: normal ou C01 a C09')
    return numeric[features].astype(np.float32)


def _separate(train, calibration):
    for col in ['collection_session_id', 'window_id']:
        if set(train[col]) & set(calibration[col]):
            raise ValueError(f'Treino e calibracao compartilham {col}')

