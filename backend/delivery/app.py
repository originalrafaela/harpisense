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
    install_deterministic_harpia(app, store)
    install_controls(app, Controls(PostgresControls(dsn), OperationalQueue()))
    return app


def build_candidate_app(*, installation_id, capabilities, allowed_origins,
                        technical_credentials=(), presentation_directory=None,
                        presentation_fault=None):
    """Installer-supplied scope and trusted manifest; no migrations or seeds.

    Explicit candidate factory: existing build_app callers remain compatible.
    Authentication and configuration share the existing PostgreSQL connection.
    """
    from admin_auth import AdminAuth, install_admin_auth
    from config_manager.store import ConfigStore
    from config_manager.api import install_config_api

    if not installation_id:
        raise ValueError('Installer installation identity required')
    app = build_app()
    dsn = os.environ['DATABASE_URL']
    store = PostgresStore(dsn)
    install_admin_auth(app, AdminAuth(dsn, technical_credentials=technical_credentials),
                       allowed_origins=allowed_origins)
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
    return app
