"""Incerteza por reamostragem de sessões, sem assumir janelas independentes."""
import numpy as np
from sklearn.metrics import confusion_matrix


def binary_metrics(y, p):
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel()
    return dict(precision=float(tp/(tp+fp)) if tp+fp else None,
                recall=float(tp/(tp+fn)) if tp+fn else None,
                f1=float(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else None,
                fpr=float(fp/(fp+tn)) if fp+tn else None)


def per_session_metrics(frame, predictions):
    return {str(s): {'windows': int(len(indices)),
            **binary_metrics(frame.iloc[indices].label.ne('normal').to_numpy(int),
                             predictions[indices])}
            for s, indices in frame.groupby('collection_session_id').indices.items()}


def session_bootstrap(frame, predictions, repeats=500, seed=42):
    groups=list(frame.groupby('collection_session_id').indices.values())
    if len(groups)<2:
        return {'available':False,'reason':'Ao menos duas sessoes de teste necessarias'}
    rng=np.random.default_rng(seed)
    truth=frame.label.ne('normal').to_numpy(int)
    samples={k:[] for k in ['precision','recall','f1','fpr']}
    for _ in range(repeats):
        indices=np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))])
        for k,v in binary_metrics(truth[indices],predictions[indices]).items():
            if v is not None: samples[k].append(v)
    return {'available':True,'repeats':repeats,'seed':seed,'unit':'collection_session_id',
            'warning':'IC exploratorio; poucas sessoes e dependencia entre campanhas limitam validade.',
            'metrics': {k:{'low':float(np.quantile(v,.025)) if v else None,
                           'high':float(np.quantile(v,.975)) if v else None,
                           'valid_resamples':len(v)} for k,v in samples.items()}}
