"""Library SHAP adapters. Historical permutation implementation stays unchanged.

TreeExplainer explains the uncalibrated RF; PermutationExplainer explains the
actual serving function. Neither method authorizes an operational action.
"""
from datetime import datetime, timezone
import csv
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd

from harpisense_contracts import fingerprint, validate, validate_links
from harpisense_contracts.validation import timestamp
from .core import check_reference, kind

VERSION = 'harpisense.xai.shap.v1'
TREE = 'SHAP_TREE_EXPLAINER'
PERMUTATION = 'SHAP_PERMUTATION_EXPLAINER'


def explain(bundle, reference, record, *, method=PERMUTATION, target_class=None,
            permutations=32, seed=42, created_at=None):
    """Return a canonical persisted record using the real SHAP library.

    RF Tree SHAP is intentionally *not* an attribution of calibrated Risk input.
    IsolationForest Tree SHAP explains path length in supported SHAP versions,
    which is not additive in -score_samples; this adapter explicitly refuses it.
    """
    if method not in (TREE, PERMUTATION):
        raise ValueError('Unknown library SHAP method')
    if type(permutations) is not int or not 2 <= permutations <= 256 or type(seed) is not int:
        raise ValueError('Invalid SHAP permutation parameters')
    validate(record)
    background = check_reference(bundle, reference)
    detector = kind(bundle)
    if record['model']['detector'] != detector or record['model']['model_version'] != bundle['model_version']:
        raise ValueError('Detection model mismatch')
    window = record['window']
    if (window['feature_schema_version'] != bundle['feature_schema_version']
            or window['traffic_profile'] != bundle['profile']
            or abs((timestamp(window['end'])-timestamp(window['start'])).total_seconds()-bundle['window_seconds']) > 1e-6):
        raise ValueError('Detection window mismatch')
    if set(record['features']) != set(bundle['features']):
        raise ValueError('Detection features mismatch')
    x = np.asarray([[record['features'][name] for name in bundle['features']]], dtype=np.float32)
    if detector == 'random_forest':
        if list(bundle['model'].classes_) != bundle['classes']:
            raise ValueError('Calibrated class order mismatch')
        label = target_class or record['classification']['predicted_class']
        if label not in bundle['classes']:
            raise ValueError('Unknown explained class')
        index = bundle['classes'].index(label)
        def score(values):
            return bundle['model'].predict_proba(pd.DataFrame(np.asarray(values, dtype=np.float32), columns=bundle['features']))[:, index]
        operational = record['classification']['probabilities'][label]
        output = 'CALIBRATED_CLASS_PROBABILITY'
    else:
        if target_class is not None:
            raise ValueError('IsolationForest has no class probability')
        if method == TREE:
            raise ValueError('TREE_IF_OUTPUT_NOT_OPERATIONAL: path length is not additive in -score_samples')
        if abs(record['anomaly']['anomaly_threshold']-bundle['threshold']) > 1e-12:
            raise ValueError('Operational threshold mismatch')
        label = None
        def score(values):
            return -bundle['model'].score_samples(pd.DataFrame(np.asarray(values, dtype=np.float32), columns=bundle['features']))
        operational = record['anomaly']['anomaly_score']
        output = 'ANOMALY_SCORE'
    actual_operational = float(score(x)[0])
    if abs(actual_operational-operational) > 1e-6:
        raise ValueError('Detection does not match the loaded serving model')
    # Lazy import: read-only HTTP does not load estimators or invoke explainers.
    import shap
    started = time.perf_counter()
    if method == TREE:
        raw = bundle['raw_model']
        if list(raw.classes_) != bundle['classes']:
            raise ValueError('Uncalibrated forest class order mismatch')
        explainer = shap.TreeExplainer(raw, data=background, model_output='raw',
            feature_perturbation='interventional', feature_names=bundle['features'])
        explanation = explainer(x, check_additivity=True)
        values = np.asarray(explanation.values[0, :, index], dtype=np.float64)
        base = float(explanation.base_values[0, index])
        actual = float(raw.predict_proba(pd.DataFrame(x, columns=bundle['features']))[0, index])
        output = 'RAW_CLASS_PROBABILITY'
    else:
        masker = shap.maskers.Independent(background, max_samples=len(background))
        explainer = shap.PermutationExplainer(score, masker, feature_names=bundle['features'], seed=seed)
        explanation = explainer(x, max_evals=permutations*(2*x.shape[1]+1), silent=True)
        values = np.asarray(explanation.values[0], dtype=np.float64)
        base = float(explanation.base_values[0])
        actual = actual_operational
    residual = actual-base-math.fsum(map(float, values))
    if values.shape != (len(bundle['features']),) or not np.isfinite(values).all() or not math.isfinite(base) or abs(residual) > 1e-5:
        raise ValueError('Library SHAP additivity failed')
    params = dict(seed=seed, permutations=permutations if method == PERMUTATION else None,
        background_rows=len(background), library_version=shap.__version__,
        output_space='raw_pre_calibration' if method == TREE else 'operational',
        operational_output_value=actual_operational)
    limitations = [
        'Attribution is not proof of causality or detector accuracy.',
        'Feature interventions may break correlations; interpretation depends on the recorded background.',
        'TreeExplainer explains the original RF probability before calibration, not the calibrated probability supplied to Risk.'
        if method == TREE else 'PermutationExplainer explains the serving function; contributions do not explain the total Risk score.',
    ]
    result = dict(schema_version='1.0.0', record_type='explanation',
        explanation_id='exp-'+fingerprint([record['detection_id'], VERSION, method, reference['reference_id'], label, params]),
        created_at=created_at or datetime.now(timezone.utc).isoformat(), detection_id=record['detection_id'],
        window_id=window['window_id'], collection_session_id=window['collection_session_id'],
        model_version=bundle['model_version'], input_fingerprint=record['input_fingerprint'], method=method,
        explainer_version=VERSION+'+shap.'+shap.__version__, reference_ref=reference['reference_id'],
        target=dict(output=output, class_label=label), base_value=base, output_value=actual,
        contributions=[dict(feature=name, value=float(x[0, i]), contribution=float(values[i]))
                       for i, name in enumerate(bundle['features'])],
        additivity_residual=residual, parameters=params, limitations=limitations)
    validate_links(detections=[record], explanations=[result], incidents=[], decisions=[])
    return result, dict(explanation_id=result['explanation_id'], elapsed_ms=(time.perf_counter()-started)*1000,
        reference_id=reference['reference_id'], method=method, library_version=shap.__version__,
        operational_output=actual_operational, explained_output=actual, output_space=params['output_space'])


def write_results(directory, detection, explanation, diagnostics):
    """Machine-readable files, no matplotlib/browser/network dependency."""
    path=Path(directory)
    path.mkdir(parents=True,exist_ok=False)
    for name,document in (('detection',detection),('explanation',explanation),('diagnostics',diagnostics)):
        (path/(name+'.json')).write_text(json.dumps(document,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    with (path/'contributions.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['feature','value','contribution'])
        writer.writeheader();writer.writerows(explanation['contributions'])
