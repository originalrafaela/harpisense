"""Import-only gate: no state, credentials, database connection or migration writes."""
import importlib
from pathlib import Path
import sys


def check_runtime():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])).resolve()
    for module in ('harpisense_catalog', 'harpisense_contracts',
                   'harpisense_contracts.canonical', 'config_manager.setup',
                   'config_manager.store', 'admin_auth.mfa', 'native_server.runtime',
                   'delivery.app', 'delivery.mqtt_consumer', 'delivery.action_review', 'xai_api.native',
                   'delivery.incident_dossier', 'harpisense_xai.shap_library',
                   'detection_composition.core', 'local_activation.client',
                   'local_activation.initial_access', 'local_activation.ipc', 'provision'):
        loaded = importlib.import_module(module)
        origin = Path(loaded.__file__).resolve()
        if not origin.is_relative_to(root):
            raise RuntimeError('RUNTIME_MODULE_OUTSIDE_PACKAGE:' + module)
    import shap
    if not callable(shap.TreeExplainer) or not callable(shap.PermutationExplainer):
        raise RuntimeError('SHAP_LIBRARY_EXPLAINERS_UNAVAILABLE')
    # Exercise the compiled bindings, not only their Python wrappers.
    from argon2 import PasswordHasher, Type
    from argon2.low_level import hash_secret_raw
    digest = hash_secret_raw(b'native-runtime-check', b'0123456789abcdef',
                             time_cost=1, memory_cost=8192, parallelism=1,
                             hash_len=32, type=Type.ID)
    if len(digest) != 32 or PasswordHasher().type != Type.ID:
        raise RuntimeError('ARGON2ID_RUNTIME_UNAVAILABLE')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.generate()
    challenge = b'HarpiSense/runtime-check/v1'
    key.public_key().verify(key.sign(challenge), challenge)
    print('RUNTIME_IMPORTS_OK', flush=True)
