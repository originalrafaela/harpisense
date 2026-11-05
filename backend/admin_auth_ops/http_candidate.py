"""Real isolated HTTP composition; never imported by the operational bootstrap.

Explicit installer preparation is required. No migration, grant or account on
startup. Only disposable mfa_http_fixture is accepted by this browser/test entry.
Run: uvicorn admin_auth_ops.http_candidate:build_http_candidate --factory
"""
import json
import os

import psycopg
from fastapi.middleware.cors import CORSMiddleware

from admin_auth.candidate import install_candidate_admin_auth
from admin_auth_ops.mfa_local import private_file
from config_manager.api import install_config_api
from config_manager.schema import Capabilities
from config_manager.store import ConfigStore
from delivery.app import build_app
from delivery.postgres_store import PostgresStore


def build_http_candidate():
    dsn = os.environ['ADMIN_MFA_HTTP_TEST_DATABASE_URL']
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        if conn.info.dbname != 'mfa_http_fixture':
            raise RuntimeError('Only disposable mfa_http_fixture is accepted')
    origins = json.loads(os.environ['ADMIN_MFA_HTTP_ORIGINS'])
    if not isinstance(origins, list) or not origins or any(not isinstance(x, str) for x in origins):
        raise ValueError('Explicit exact browser origins required')
    installation = os.environ['ADMIN_MFA_HTTP_INSTALLATION_ID']
    # Existing build_app is reused, including real P11/store/HarpIA/controls.
    os.environ['DATABASE_URL'] = dsn
    app = build_app()
    technical = ((os.environ['HARPISENSE_ADMIN_USER'], os.environ['HARPISENSE_ADMIN_PASSWORD']),)
    key = private_file(os.environ['ADMIN_MFA_KEY_FILE']).read_bytes().strip()
    install_candidate_admin_auth(app, dsn, protection_key=key, allowed_origins=origins,
                                 technical_credentials=technical)
    store = PostgresStore(dsn)
    config = ConfigStore(store._connect, Capabilities(revision='mfa-http-isolated'))
    install_config_api(app, config, installation_id=installation)
    # Bearer tokens only: no cookies, no wildcard, preflight Authorization allowed.
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                       allow_methods=['GET', 'POST', 'PUT'],
                       allow_headers=['Authorization', 'Content-Type'],
                       expose_headers=['Retry-After'], max_age=600)
    return app
