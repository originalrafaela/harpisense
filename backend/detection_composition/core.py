"""Compose the approved estimators and engines, without dispatch capability.

The only currently executable lane is explicitly synthetic. The P08 lane calls
the delivered gate, which remains closed until certified counts are available.
No public HTTP inference endpoint accepts client-supplied coverage flags.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json

from harpisense_contracts import fingerprint, validate_links
from harpisense_contracts.validation import timestamp
from harpisense_engines.core import decide
from harpisense_xai.core import detection, kind
from harpisense_rf.random_forest import load_bundle as load_rf
from harpisense_if.isolation_forest import load_bundle as load_if


class DependencyBlocked(ValueError):
    def __init__(self, reasons, diagnostic=None):
        super().__init__('; '.join(reasons))
        self.reasons = reasons
        self.diagnostic = diagnostic


def load_artifact(directory, *, expected_sha256, detector):
    """Pin a trusted artifact before executing joblib; hash is installer supplied."""
    directory = Path(directory)
    if detector not in ('random_forest', 'isolation_forest'):
        raise ValueError('Unknown detector')
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError('Installer-pinned SHA256 required')
    missing = [str(directory / name) for name in ('metadata.json', 'model.joblib')
               if not (directory / name).is_file()]
    if missing:
        raise DependencyBlocked(['Missing artifact: ' + name for name in missing])
    meta = json.loads((directory / 'metadata.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256((directory / 'model.joblib').read_bytes()).hexdigest()
    if digest != expected_sha256 or meta.get('artifact_sha256') != digest:
        raise ValueError('Artifact SHA256 mismatch')
    bundle = (load_rf if detector == 'random_forest' else load_if)(directory)
    if kind(bundle) != detector or bundle['model_version'] != meta['model_version']:
        raise ValueError('Artifact detector/version mismatch')
    # The ordered transform and serving metadata must match the pinned manifest.
    for key in ('features', 'profile', 'window_seconds', 'feature_schema_version', 'versions'):
        if bundle[key] != meta[key]:
            raise ValueError('Artifact metadata mismatch: ' + key)
    return bundle, {'sha256': digest, 'model_version': bundle['model_version'],
                    'features': bundle['features'], 'profile': bundle['profile'],
                    'window_seconds': bundle['window_seconds'], 'versions': bundle['versions']}


class Composition:
    def __init__(self, store, *, rf_directory, rf_sha256, if_directory, if_sha256):
        self.store = store
        self.rf, rf = load_artifact(rf_directory, expected_sha256=rf_sha256, detector='random_forest')
        self.iforest, isolation = load_artifact(if_directory, expected_sha256=if_sha256, detector='isolation_forest')
        self.artifacts = {'random_forest': rf, 'isolation_forest': isolation}
        for key in ('profile', 'window_seconds', 'feature_schema_version'):
            if self.rf[key] != self.iforest[key]:
                raise ValueError('RF/IF incompatible: ' + key)

    def process_p08(self, *, base_dir, session_name, events, window,
                    coverage_records, required_sources, batch_path=None, now=None, mode=1):
        from p08_p09_pipeline import run_pipeline
        gate = run_pipeline(base_dir, session_name, events, [window],
                            coverage_records, required_sources, batch_path=batch_path)
        # This delivered version deliberately never authorizes inference.
        # Do not invent a feature bridge or promote UNKNOWN while it is closed.
        raise DependencyBlocked(gate['reasons'] or ['P08 feature certification unavailable'], gate)

    def process_synthetic(self, window, *, now, mode=1, asset=None, target=None,
                          evidence=None, trusted_sources=None, config=None):
        """Real model execution on explicitly artificial input, never lab acceptance.

        Context is installer/service supplied. Models infer the candidate scenario;
        the caller cannot replace RF probability, IF score or computed Risk.
        """
        timestamp(now)
        window = deepcopy(window)
        if timestamp(window['window_end']) > timestamp(now):
            raise ValueError('Window has not ended')
        if (timestamp(now) - timestamp(window['window_end'])).total_seconds() > 60:
            raise ValueError('Window expired')
        identity = [window['collection_session_id'], window['window_id'], window['sensor_id'],
                    [self.artifacts[k]['model_version'] for k in sorted(self.artifacts)]]
        run_id = 'composition-' + fingerprint(identity)
        request = dict(window=window, artifacts=self.artifacts, mode=mode, asset=asset,
                       target=target, evidence=evidence or [], trusted_sources=trusted_sources or {},
                       config=config, input_origin='synthetic')
        request_hash = fingerprint(request)

        def produce():
            detections = [detection(b, window, created_at=now) for b in (self.rf, self.iforest)]
            classification = detections[0]['classification']
            case = classification['accepted_class']
            if case == 'normal':
                case = None
            context = dict(scenario_id=case, detections=detections, explanations=[],
                           evidence=evidence or [], asset=asset, target=target,
                           trusted_sources=trusted_sources or {})
            result = decide(context, mode=mode, now=now, config=config)
            validate_links(detections=detections, explanations=[], incidents=[result['incident']],
                           decisions=[result['decision']])
            # Policy authorization is retained as a canonical result; execution
            # stays false and no executor is imported or called, even in M3.
            return dict(run_id=run_id, input_origin='synthetic', laboratory_validated=False,
                        execution_performed=False, artifacts=self.artifacts,
                        detections=detections, **result)

        return self.store.commit_composition(run_id, request_hash, window, produce)
