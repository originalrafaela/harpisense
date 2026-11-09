"""Local composition of approved P11, PostgreSQL and deterministic HarpIA.

No automatic migrations, fake login, synthetic seed or production executor.
Run from repository root with PYTHONPATH=backend/domain;backend;genai.
"""
import os
from fastapi import HTTPException
from fastapi.routing import APIRoute
from harpia.p11 import install_deterministic_harpia
from .postgres_store import PostgresStore
from .projections import create_app
from .control_store import PostgresControls
from .controls import Controls
from .routes import install_controls
from .operational_queue import OperationalQueue
from .linked_cases import LinkedOperationalQueue,CaseSnapshotControls


def build_app():
    dsn = os.environ['DATABASE_URL']
    if not dsn.startswith(('postgresql://', 'postgres://', 'host=')):
        raise RuntimeError('PostgreSQL required')
    store = PostgresStore(dsn)
    app = create_app(store)
    health = next(r for r in app.routes if isinstance(r, APIRoute) and r.path == '/api/v1/p11/health')
    original = health.dependant.call

    def checked_health(**kwargs):
        try:
            with store._connect() as conn:
                conn.execute('SELECT 1 FROM projections LIMIT 1')
        except Exception as exc:
            raise HTTPException(503, 'PostgreSQL/projeções indisponíveis') from exc
        return {**original(**kwargs), 'database': 'available', 'executor': 'not_configured'}

    health.dependant.call = checked_health
    bitnet_client = None
    if os.environ.get('HARPISENSE_BITNET_ENABLED', '0') == '1':
        from harpia.client import Client, endpoint_url
        # Never send incident context to an external URL or an environment proxy.
        url = endpoint_url(os.environ.get('HARPIA_URL', 'http://127.0.0.1:8091'), loopback=True)
        bitnet_client = Client(url=url)
    install_deterministic_harpia(app, store, bitnet_client=bitnet_client)
    controls=CaseSnapshotControls(PostgresControls(dsn),LinkedOperationalQueue())
    install_controls(app,controls)
    app.state.operational_controls=controls
    return app


def build_candidate_app(*, installation_id, capabilities, allowed_origins,
                        technical_credentials=(), presentation_directory=None,
                        presentation_fault=None, protection_key=None, initial_access=None):
    """Installer-supplied scope and trusted manifest; no migrations or seeds.

    Explicit candidate factory: existing build_app callers remain compatible.
    Authentication and configuration share the existing PostgreSQL connection.
    """
    if protection_key is None:
        raise RuntimeError('MFA_COMPOSITION_REQUIRED')
    from admin_auth.candidate import install_candidate_admin_auth
    from config_manager.store import ConfigStore
    from config_manager.api import install_config_api

    if not installation_id:
        raise ValueError('Installer installation identity required')
    app = build_app()
    dsn = os.environ['DATABASE_URL']
    store = PostgresStore(dsn)
    install_candidate_admin_auth(app, dsn, protection_key=protection_key,
                                 technical_credentials=technical_credentials,
                                 allowed_origins=allowed_origins, initial_access=initial_access)
    config = ConfigStore(store._connect, capabilities)
    presentation = None
    if presentation_directory is not None:
        from config_manager.presentation import PresentationApplicator
        presentation = PresentationApplicator(config, installation_id,
            presentation_directory, fault=presentation_fault)
        try:
            presentation.recover()
        except Exception:
            pass  # Unknown remains visible and blocks further application.
        app.state.presentation = presentation
    install_config_api(app, config, installation_id=installation_id,
                       presentation=presentation)
    from xai_api import install_xai_api
    from .incident_dossier import install_incident_api
    install_xai_api(app, store, installation_id=installation_id, asset_identifier_column='device_id')
    install_incident_api(app, store, installation_id)
    return app
