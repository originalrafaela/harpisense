"""HarpiSense: Isolation Forest em janelas agregadas, sem bloqueio direto."""
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

ARTIFACT_VERSION = 2
from harpisense_data.windows import (SCHEMA_VERSION,FEATURES,OPTIONAL_FEATURES,COUNT_FEATURES,LABELS,META,
    versions,digest,read_csv,validate,_separate)


def train_model(train, calibration, *, profile, window_seconds=10.0,
                features=None, target_fpr=0.01, n_estimators=200, seed=42):
    features = list(FEATURES if features is None else features)
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        raise ValueError('window_seconds deve ser positivo')
    if not math.isfinite(target_fpr) or not 0 < target_fpr <= 0.2:
        raise ValueError('target_fpr deve estar entre 0 e 0.2')
    if not 10 <= n_estimators <= 2000:
        raise ValueError('n_estimators deve estar entre 10 e 2000')
    x_train = validate(train, features, profile, window_seconds, labelled=True)
    x_cal = validate(calibration, features, profile, window_seconds, labelled=True)
    if not train.label.eq('normal').all() or not calibration.label.eq('normal').all():
        raise ValueError('Treino e calibracao devem conter apenas normal revisado')
    if len(train) < 256 or len(calibration) < max(200, math.ceil(1 / target_fpr)):
        raise ValueError('Exigem-se 256 janelas de treino e >=200 de calibracao; '
                         'calibracao tambem deve ter pelo menos 1/target_fpr janelas')
    if min(train.collection_session_id.nunique(),
           calibration.collection_session_id.nunique()) < 2:
        raise ValueError('Exigem-se ao menos duas sessoes em cada conjunto')
    _separate(train, calibration)
    if x_train.drop_duplicates().shape[0] < 10:
        raise ValueError('Baseline sem diversidade suficiente para ajuste')
    model = IsolationForest(n_estimators=n_estimators, max_samples='auto',
        contamination='auto', random_state=seed, n_jobs=1)
    model.fit(x_train)
    # score_samples menor = mais anomalo; inverter facilita o contrato do Risk.
    scores = -model.score_samples(x_cal)
    # Limiar externo, independente do offset padrao do estimador.
    threshold = float(np.quantile(scores, 1 - target_fpr, method='higher'))
    created_at = datetime.now(timezone.utc).isoformat()
    return dict(artifact_version=ARTIFACT_VERSION, model=model, features=features,
        feature_schema_version=SCHEMA_VERSION, profile=profile,
        window_seconds=float(window_seconds), threshold=threshold,
        target_fpr=target_fpr, observed_calibration_fpr=float((scores > threshold).mean()),
        created_at=created_at, model_version='if-' + created_at,
        versions=versions(), seed=seed,
        counts={'train': len(train), 'calibration': len(calibration)},
        fitted_window_ids=sorted(set(train.window_id) | set(calibration.window_id)),
        fitted_sessions=sorted(set(train.collection_session_id) |
                               set(calibration.collection_session_id)),
        baseline={c: {'median': float(x_train[c].median()),
            'q01': float(x_train[c].quantile(.01)),
            'q99': float(x_train[c].quantile(.99)),
            'iqr': float(x_train[c].quantile(.75)-x_train[c].quantile(.25))}
            for c in features},
        calibration_scores=sorted(float(v) for v in scores),
        constant_features=[c for c in features if x_train[c].nunique() == 1])


def predict_windows(bundle, frame):
    x = validate(frame, bundle['features'], bundle['profile'], bundle['window_seconds'])
    scores = -bundle['model'].score_samples(x)
    threshold = bundle['threshold']
    rows = []
    for (_, source), score in zip(frame.iterrows(), scores):
        anomalous = bool(score > threshold)
        rows.append(dict(window_id=source.window_id,
            collection_session_id=source.collection_session_id,
            detector='isolation_forest', model_version=bundle['model_version'],
            feature_schema_version=SCHEMA_VERSION, traffic_profile=bundle['profile'],
            anomaly_score=float(score), anomaly_threshold=threshold,
            anomaly_margin=float(score - threshold), is_anomaly=anomalous,
            normal_reference_percentile=float(np.searchsorted(
                bundle['calibration_scores'], score, side='right') /
                len(bundle['calibration_scores'])),
            suggested_action='ALERT' if anomalous else 'MONITOR',
            predicted_class=None, severity=None, block_authorized=False))
    return rows


def evaluate(bundle, frame):
    validate(frame, bundle['features'], bundle['profile'],
             bundle['window_seconds'], labelled=True)
    if set(frame.collection_session_id) & set(bundle['fitted_sessions']):
        raise ValueError('Avaliacao precisa de sessoes fora de treino/calibracao')
    if set(frame.window_id) & set(bundle['fitted_window_ids']):
        raise ValueError('Avaliacao compartilha IDs de janelas usadas no ajuste')
    started = time.perf_counter()
    output = predict_windows(bundle, frame)
    elapsed_ms = (time.perf_counter() - started) * 1000
    y_true = frame.label.ne('normal').to_numpy(dtype=int)
    y_pred = np.array([row['is_anomaly'] for row in output], dtype=int)
    scores = np.array([row['anomaly_score'] for row in output])
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average='binary', zero_division=0)
    per_scenario = {}
    for label in sorted(LABELS - {'normal'}):
        mask = frame.label.eq(label).to_numpy()
        per_scenario[label] = {'windows': int(mask.sum()),
            'anomaly_detection_rate': float(y_pred[mask].mean()) if mask.any() else None}
    from harpisense_if.avaliacao import session_bootstrap, per_session_metrics
    both = len(np.unique(y_true)) == 2
    return dict(windows=len(frame), model_version=bundle['model_version'],
        threshold=bundle['threshold'], sessions=int(frame.collection_session_id.nunique()),
        accuracy=float(accuracy_score(y_true,y_pred)),
        classification_report=classification_report(y_true,y_pred,labels=[0,1],
            target_names=['normal','anomalia'],output_dict=True,zero_division=0),
        inference_batch_ms=elapsed_ms, inference_amortized_ms_per_window=elapsed_ms/len(frame),
        confusion_matrix={'tn':int(tn), 'fp':int(fp),
        'fn':int(fn), 'tp':int(tp)}, precision=float(precision), recall=float(recall),
        f1=float(f1),
        specificity=float(tn/(tn+fp)) if tn+fp else None,
        false_negative_rate=float(fn/(fn+tp)) if fn+tp else None,
        metric_convention='Precision/recall/F1 indefinidos retornam 0; conferir suporte.',
        false_positive_rate=float(fp/(fp+tn)) if fp+tn else None,
        roc_auc=float(roc_auc_score(y_true, scores)) if both else None,
        average_precision=float(average_precision_score(y_true, scores)) if both else None,
        per_scenario=per_scenario,
        session_bootstrap_95=session_bootstrap(frame, y_pred),
        per_session=per_session_metrics(frame, y_pred),
        balanced_accuracy=float((tp/(tp+fn)+tn/(tn+fp))/2) if both else None,
        note='Deteccao binaria de anomalia, nao classificacao do ataque.')


def save_bundle(bundle, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    joblib.dump(bundle, directory / 'model.joblib')
    public = {k:v for k,v in bundle.items() if k != 'model'}
    public['artifact_sha256'] = digest(directory / 'model.joblib')
    (directory / 'metadata.json').write_text(
        json.dumps(public, ensure_ascii=False, indent=2), encoding='utf-8')


def load_bundle(directory):
    """Apenas artefatos confiaveis: joblib pode executar codigo ao carregar."""
    directory = Path(directory)
    meta = json.loads((directory / 'metadata.json').read_text(encoding='utf-8'))
    if digest(directory / 'model.joblib') != meta['artifact_sha256']:
        raise ValueError('Hash do artefato divergente')
    if meta['versions'] != versions():
        raise ValueError('Ambiente diferente do treinamento; use as mesmas versoes')
    if meta['artifact_version'] != ARTIFACT_VERSION:
        raise ValueError('Versao de artefato incompatível')
    bundle = joblib.load(directory / 'model.joblib')
    if bundle['feature_schema_version'] != SCHEMA_VERSION:
        raise ValueError('Schema do modelo incompatível')
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    training = commands.add_parser('train')
    training.add_argument('--train', required=True)
    training.add_argument('--calibration', required=True)
    training.add_argument('--profile', required=True)
    training.add_argument('--window-seconds', type=float, default=10)
    training.add_argument('--target-fpr', type=float, default=0.01)
    training.add_argument('--trees', type=int, default=200)
    training.add_argument('--features', nargs='+', default=FEATURES)
    training.add_argument('--out', required=True)
    for name in ['predict', 'evaluate']:
        sub = commands.add_parser(name)
        sub.add_argument('--model', required=True)
        sub.add_argument('--input', required=True)
        sub.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command == 'train':
        bundle = train_model(read_csv(args.train), read_csv(args.calibration),
            profile=args.profile, window_seconds=args.window_seconds,
            features=args.features, target_fpr=args.target_fpr, n_estimators=args.trees)
        bundle['dataset_sha256'] = {'train': digest(args.train),
                                    'calibration': digest(args.calibration)}
        save_bundle(bundle, args.out)
        print(json.dumps({'model_directory': args.out,
            'threshold': bundle['threshold'],
            'calibration_fpr': bundle['observed_calibration_fpr']}))
    else:
        bundle = load_bundle(args.model)
        frame = read_csv(args.input)
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        result = evaluate(bundle, frame) if args.command == 'evaluate' else predict_windows(bundle, frame)
        # Evitar sobrescrever acidentalmente resultados ou o dataset de entrada.
        with output.open('x', encoding='utf-8') as stream:
            if args.command == 'evaluate':
                json.dump(result, stream, ensure_ascii=False, indent=2)
            else:
                for row in result:
                    stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(str(output))

if __name__ == '__main__':
    main()
