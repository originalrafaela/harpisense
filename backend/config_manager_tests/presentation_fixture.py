"""Real HTTP/SQL presentation acceptance environment, never an operational DSN."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import psycopg

from admin_auth import AdminAuth
from config_manager.schema import Capabilities
from config_manager.store import ConfigStore, migrate
from config_manager.setup import migrate_setup
from delivery.app import build_candidate_app

INSTALLATION = 'presentation-local-20261101'
CAPABILITIES = Capabilities(revision='presentation-test-only-1')


def connect():
    conn = psycopg.connect(os.environ['DATABASE_URL'])
    if conn.info.dbname != 'config_fixture' or conn.info.host != '127.0.0.1' or conn.info.port != 55445:
        conn.close()
        raise RuntimeError('Only isolated config_fixture on loopback 55445 allowed')
    return conn


def prepare():
    with connect() as conn:
        root = Path(__file__).parents[1]
        conn.execute((root / 'delivery/001_local.sql').read_text())
        if not conn.execute("SELECT to_regclass('hs_admin_account')").fetchone()[0]:
            conn.execute((root / 'admin_auth/001_admin_auth.sql').read_text())
    migrate(connect)
    migrate_setup(connect)
    with connect() as conn:
        present = conn.execute('SELECT 1 FROM hs_admin_account').fetchone()
    if not present:
        AdminAuth(os.environ['DATABASE_URL']).provision('fixture-admin',
            os.environ['HARPISENSE_BROWSER_FIXTURE_PASSWORD'])
    ConfigStore(connect, CAPABILITIES).provision_registry(INSTALLATION)


def app():
    with connect(): pass
    directory = Path(os.environ['HARPISENSE_PRESENTATION_TEST_DIRECTORY']).resolve()

    def fault(stage):
        path = directory / 'test-fault.json'
        if path.exists() and stage in json.loads(path.read_text())['stages']:
            raise RuntimeError('Injected fixture fault')

    candidate = build_candidate_app(installation_id=INSTALLATION,
        capabilities=CAPABILITIES, allowed_origins=['http://127.0.0.1:4175'],
        presentation_directory=directory, presentation_fault=fault)

    @candidate.middleware('http')
    async def receipt(request, call_next):
        response = await call_next(request)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'http-receipt.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(),
                'method': request.method, 'path': request.url.path, 'status': response.status_code}) + '\n')
        return response
    return candidate


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    if parser.parse_args().prepare:
        prepare()
    else:
        import uvicorn
        uvicorn.run(app(), host='127.0.0.1', port=18002)
