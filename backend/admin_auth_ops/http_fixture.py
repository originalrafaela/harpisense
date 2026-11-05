"""Disposable browser fixture, NOT an installer or operational bootstrap.

Only mfa_http_fixture. Requires explicit reset flag to reset identity state.
Secrets are generated in a private local directory and never printed.
"""
import argparse
import json
import os
import secrets
from pathlib import Path

import psycopg
import uvicorn
from cryptography.fernet import Fernet

from admin_auth import AdminAuth
from admin_auth.mfa import MFAAdminAuth
from admin_auth_ops.mfa_local import create_private, private_file
from config_manager.schema import Capabilities
from config_manager.setup import migrate_setup
from config_manager.store import ConfigStore, migrate

ROOT = Path(__file__).resolve().parents[2]
INSTALLATION = 'mfa-http-isolated'


def prepare_fixture(dsn):
    with psycopg.connect(dsn) as conn:
        if conn.info.dbname != 'mfa_http_fixture':
            raise RuntimeError('Only disposable mfa_http_fixture is accepted')
        conn.execute((ROOT/'backend/delivery/001_local.sql').read_text())
        if not conn.execute("SELECT to_regclass('hs_admin_schema_version')").fetchone()[0]:
            conn.execute((ROOT/'backend/admin_auth/001_admin_auth.sql').read_text())
        conn.execute((ROOT/'backend/admin_auth/002_admin_mfa.sql').read_text())
    connect = lambda: psycopg.connect(dsn)
    migrate(connect)
    migrate_setup(connect)
    ConfigStore(connect, Capabilities(revision='mfa-http-isolated')).provision_registry(INSTALLATION)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', required=True, type=Path)
    parser.add_argument('--scenario', choices=['new', 'existing'], default='new')
    parser.add_argument('--reset-auth', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    dsn = os.environ['ADMIN_MFA_HTTP_TEST_DATABASE_URL']
    prepare_fixture(dsn)
    if not args.private_dir.is_absolute() or args.private_dir == Path('/') or args.private_dir.is_symlink():
        raise ValueError('Absolute private fixture directory required')
    args.private_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    # This directory is an explicitly named disposable fixture volume only.
    args.private_dir.chmod(0o700)
    if args.reset_auth:
        for name in ('bootstrap.secret', 'legacy-password.secret'):
            path = args.private_dir/name
            if path.exists():
                private_file(path).unlink()
    keyfile = args.private_dir/'admin-mfa.key'
    with psycopg.connect(dsn) as conn:
        if args.reset_auth:
            conn.execute('TRUNCATE hs_admin_mfa_challenge,hs_admin_recovery_code,hs_admin_mfa,hs_admin_local_grant, '
                         'hs_admin_session,hs_admin_account,hs_admin_audit')
            conn.execute("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity'")
        present = conn.execute('SELECT 1 FROM hs_admin_account').fetchone()
        encrypted = conn.execute('SELECT 1 FROM hs_admin_mfa WHERE secret_cipher IS NOT NULL').fetchone()
    if not keyfile.exists():
        if encrypted:
            raise RuntimeError('Restore original private key before serving this fixture')
        create_private(keyfile, Fernet.generate_key())
    key = private_file(keyfile).read_bytes()
    if not present:
        if args.scenario == 'existing':
            password = secrets.token_urlsafe(32)
            AdminAuth(dsn).provision('browser-fixture-owner', password)
            create_private(args.private_dir/'legacy-password.secret', password.encode())
        else:
            grantfile = args.private_dir/'bootstrap.secret'
            if not grantfile.exists():
                grant = MFAAdminAuth(dsn, protection_key=key).issue_local_grant()
                create_private(grantfile, grant.encode())
    if args.prepare_only:
        return
    os.environ['ADMIN_MFA_KEY_FILE'] = str(keyfile)
    os.environ['ADMIN_MFA_HTTP_INSTALLATION_ID'] = INSTALLATION
    os.environ.setdefault('ADMIN_MFA_HTTP_ORIGINS', json.dumps(['http://127.0.0.1:5174', 'http://127.0.0.1:4174']))
    os.environ.setdefault('HARPISENSE_ADMIN_USER', 'technical-http-fixture')
    os.environ.setdefault('HARPISENSE_ADMIN_PASSWORD', secrets.token_urlsafe(32))
    os.environ.setdefault('HARPISENSE_PROJECTION_SERVICE_TOKEN', secrets.token_urlsafe(32))
    host = '0.0.0.0' if os.environ.get('ADMIN_MFA_HTTP_CONTAINER') == '1' else '127.0.0.1'
    from admin_auth_ops.http_candidate import build_http_candidate
    uvicorn.run(build_http_candidate(), host=host, port=8086, access_log=False)


if __name__ == '__main__':
    main()
