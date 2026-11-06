"""Import-only gate: no state, credentials, database connection or migration writes."""
import importlib
from pathlib import Path
import sys


def check_runtime():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])).resolve()
    for module in ('harpisense_catalog', 'harpisense_contracts',
                   'harpisense_contracts.canonical', 'config_manager.setup',
                   'config_manager.store', 'admin_auth.mfa', 'native_server.runtime',
                   'delivery.app', 'delivery.mqtt_consumer', 'provision'):
        loaded = importlib.import_module(module)
        origin = Path(loaded.__file__).resolve()
        if not origin.is_relative_to(root):
            raise RuntimeError('RUNTIME_MODULE_OUTSIDE_PACKAGE:' + module)
    print('RUNTIME_IMPORTS_OK', flush=True)
