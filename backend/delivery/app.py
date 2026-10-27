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
    install_controls(app, Controls(PostgresControls(dsn)))
    return app
