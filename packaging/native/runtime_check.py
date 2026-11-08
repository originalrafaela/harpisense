"""Import-only gate: no state, credentials, database connection or migration writes."""
import importlib
from pathlib import Path
import sys


def check_runtime():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])).resolve()
    for module in ('harpisense_catalog', 'harpisense_contracts',
                   'harpisense_contracts.canonical', 'config_manager.setup',
                   'config_manager.store', 'admin_auth.mfa', 'native_server.runtime',
                   'delivery.app', 'delivery.mqtt_consumer', 'xai_api.native',
                   'delivery.incident_dossier', 'harpisense_xai.shap_library',
                   'detection_composition.core', 'provision'):
        loaded = importlib.import_module(module)
        origin = Path(loaded.__file__).resolve()
        if not origin.is_relative_to(root):
            raise RuntimeError('RUNTIME_MODULE_OUTSIDE_PACKAGE:' + module)
    import shap
    if not callable(shap.TreeExplainer) or not callable(shap.PermutationExplainer):
        raise RuntimeError('SHAP_LIBRARY_EXPLAINERS_UNAVAILABLE')
    print('RUNTIME_IMPORTS_OK', flush=True)
