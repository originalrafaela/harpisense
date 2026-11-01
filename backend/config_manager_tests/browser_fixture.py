"""Explicit disposable browser fixture. Never accepts an operational database."""
import argparse
import os
from pathlib import Path

import psycopg
from admin_auth import AdminAuth
from config_manager.schema import Capabilities
from config_manager.store import ConfigStore, migrate
from config_manager.setup import migrate_setup
from delivery.app import build_candidate_app

INSTALLATION = 'browser-local-20261101'
CAPABILITIES = Capabilities(revision='browser-fixture-only-1',
    mqtt_hosts=frozenset({'broker.browser.invalid'}),
    ca_refs=frozenset({'browser-ca'}),
    secret_refs=frozenset({'secret://fixture/mqtt'}),
    mqtt_topics=frozenset({'fixture/telemetry'}))


def connect():
    conn = psycopg.connect(os.environ['DATABASE_URL'])
    if (conn.info.dbname != 'config_fixture' or conn.info.host != '127.0.0.1'
            or conn.info.port != 55444):
        conn.close()
        raise RuntimeError('Only isolated loopback fixture on port 55444 allowed')
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
        AdminAuth(os.environ['DATABASE_URL']).provision(
            'browser-admin', os.environ['HARPISENSE_BROWSER_FIXTURE_PASSWORD'])
    ConfigStore(connect, CAPABILITIES).provision_registry(INSTALLATION)


def app():
    with connect():
        pass
    return build_candidate_app(installation_id=INSTALLATION,
        capabilities=CAPABILITIES, allowed_origins=['http://127.0.0.1:5174'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        import uvicorn
        uvicorn.run(app(), host='127.0.0.1', port=18001)
