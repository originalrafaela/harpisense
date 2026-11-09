"""Explicit, reversible upgrade of the previously provisioned HarpiServer.

prepare/rehearse run as its service user. apply/rollback require operator root.
No VPN, MQTT, firewall, human password or license is created or changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
PG = Path('/usr/lib/postgresql/18/bin')
DROPIN = Path('/etc/systemd/system/harpisense-p11.service.d/initial-auth.conf')


def write(path, data):
    with Path(path).open('x', encoding='utf-8') as stream:
        os.chmod(path, 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if os.geteuid() == 0 and Path(path).resolve().is_relative_to(ROOT):
        owner = ROOT.stat()
        os.chown(path, owner.st_uid, owner.st_gid)


def checked():
    manifest = json.loads((ROOT/'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError('RELEASE_CHECKSUM_MISMATCH')
    return json.loads((ROOT/'settings.json').read_text())


def environment(settings):
    return dict(line.split('=', 1) for line in (Path(settings['base'])/'.env').read_text().splitlines()
                if '=' in line and not line.startswith('#'))


def run(args, **kwargs):
    result = subprocess.run([str(a) for a in args], capture_output=True, timeout=180, **kwargs)
    if result.returncode:
        # stderr may include credentials/data: private file, never terminal/report.
        path = ROOT/'failure.private.log'
        path.write_bytes(result.stderr)
        os.chmod(path, 0o600)
        raise RuntimeError('UPGRADE_SUBPROCESS_FAILED:' + Path(str(args[0])).name)
    return result


def scripts():
    return [ROOT/'backend'/p for p in (
        'delivery/001_local.sql', 'delivery/002_operational_authority.sql',
        'delivery/003_incident_assessment.sql', 'delivery/004_activity_decision_snapshot.sql',
        'delivery/006_action_review.sql', 'admin_auth/002_admin_mfa.sql',
        'admin_auth/003_password_reset.sql', 'admin_auth/004_first_access.sql',
        'admin_auth/005_initial_auth_v2.sql')]


def migration_sql(role):
    from psycopg import sql
    import re
    quoted = sql.Identifier(role).as_string()
    # Root migration owns new tables; the runtime receives DML, never DDL grants.
    # Existing table owners and identity credentials are not changed.
    public = '\n'.join(path.read_text() for path in scripts())
    assets = (ROOT/'backend/config_manager/003_assets.sql').read_text()
    tables = sorted(set(re.findall(r'CREATE TABLE IF NOT EXISTS ([a-z_0-9]+)', public)))
    grants = '\n'.join(f'GRANT SELECT,INSERT,UPDATE,DELETE ON public.{table} TO {quoted};' for table in tables)
    return (public + '\nBEGIN;\n' + assets + '\n' + grants +
            f'\nGRANT USAGE ON SEQUENCE public.hs_control_audit_id_seq,public.hs_incident_assessment_id_seq,public.hs_activity_event_id_seq TO {quoted};' +
            f'\nGRANT SELECT,INSERT,UPDATE ON hs_config.asset,hs_config.asset_audit TO {quoted};'
            f'\nGRANT USAGE ON SEQUENCE hs_config.asset_audit_id_seq TO {quoted};\nCOMMIT;\n')


def prepare():
    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from cryptography.fernet import Fernet
    settings = checked()
    env = environment(settings)
    with psycopg.connect(env['HARPISENSE_DATABASE_URL']) as conn:
        if conn.execute('SELECT count(*) FROM hs_admin_account').fetchone()[0] != 1:
            raise RuntimeError('EXISTING_SINGLE_ADMIN_REQUIRED')
        if conn.execute("SELECT to_regclass('hs_admin_mfa')").fetchone()[0]:
            raise RuntimeError('MFA_ALREADY_PRESENT_REQUIRES_KEY_REVIEW')
    if hashlib.sha256((Path(settings['base'])/'app.py').read_bytes()).hexdigest() != settings['expected_app_sha256']:
        raise RuntimeError('ACTIVE_BOOTSTRAP_DRIFT')
    private = Path(settings['key_file']).parent
    private.mkdir(mode=0o700, exist_ok=True)
    if os.geteuid() == 0:
        owner = Path(settings['base']).stat()
        os.chown(private, owner.st_uid, owner.st_gid)
    if private.is_symlink() or private.stat().st_mode & 0o077:
        raise RuntimeError('PRIVATE_DIRECTORY_PERMISSIONS')
    if not Path(settings['key_file']).exists():
        write(settings['key_file'], Fernet.generate_key().decode())
        if os.geteuid() == 0:
            os.chown(settings['key_file'], owner.st_uid, owner.st_gid)
    # Complete original DB, including owners/ACL. Key stays outside this backup.
    parameters = conninfo_to_dict(env['HARPISENSE_DATABASE_URL'])
    dump = ROOT/'before.dump'
    if dump.exists():
        raise RuntimeError('BACKUP_ALREADY_EXISTS')
    # The runtime has USAGE but deliberately not SELECT on config sequences.
    # Never broaden its grants just to obtain a backup. Operator postgres must
    # make the complete dump (owners, ACL and exact sequence positions).
    if os.geteuid() != 0:
        raise RuntimeError('OPERATOR_ROOT_REQUIRED_FOR_COMPLETE_BACKUP')
    with dump.open('xb') as stream:
        os.chmod(dump, 0o600)
        result = subprocess.run(['/usr/sbin/runuser','-u','postgres','--',str(PG/'pg_dump'),
                                 '-Fc','--dbname',parameters['dbname']], stdout=stream,
                                stderr=subprocess.PIPE, timeout=180)
    if result.returncode:
        raise RuntimeError('COMPLETE_DATABASE_BACKUP_FAILED')
    os.chown(dump, ROOT.stat().st_uid, ROOT.stat().st_gid)
    write(ROOT/'prepared.json', json.dumps({'backup_sha256': hashlib.sha256(dump.read_bytes()).hexdigest(),
        'source_app_unchanged': True, 'services_restarted': False}))
    print('PREPARED; original services unchanged; key outside database backup')


def rehearse():
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    from psycopg import sql
    settings = checked()
    expected = json.loads((ROOT/'prepared.json').read_text())['backup_sha256']
    if hashlib.sha256((ROOT/'before.dump').read_bytes()).hexdigest() != expected:
        raise RuntimeError('BACKUP_CHECKSUM_MISMATCH')
    role = conninfo_to_dict(environment(settings)['HARPISENSE_DATABASE_URL'])['user']
    # Private Unix socket only: no TCP listener, no changes to installed PostgreSQL.
    # Keep the Unix socket pathname below Linux's sockaddr_un length limit.
    with tempfile.TemporaryDirectory(prefix='hs-rehearsal-') as directory:
        temp = Path(directory)
        run([PG/'initdb', '-D', temp/'pg', '-U', 'postgres', '-A', 'trust', '--no-locale'])
        run([PG/'pg_ctl', '-D', temp/'pg', '-l', temp/'pg.log', '-o', f"-k {temp} -c listen_addresses=''", '-w', 'start'])
        try:
            dsn = f'host={temp} dbname=postgres user=postgres'
            with psycopg.connect(dsn, autocommit=True) as conn:
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN').format(sql.Identifier(role)))
            run([PG/'pg_restore', '-h', temp, '-U', 'postgres', '-d', 'postgres', ROOT/'before.dump'])
            with psycopg.connect(dsn, autocommit=True) as conn:
                before = conn.execute('SELECT id,username,password_hash,credential_revision FROM hs_admin_account').fetchall()
                projections = conn.execute('SELECT count(*) FROM projections').fetchone()
                conn.execute(migration_sql(role))
                assert before == conn.execute('SELECT id,username,password_hash,credential_revision FROM hs_admin_account').fetchall()
                assert projections == conn.execute('SELECT count(*) FROM projections').fetchone()
            # Exercise the exact release factory against the restored + migrated DB.
            from gateway_entry import build_app
            from fastapi.testclient import TestClient
            from psycopg.conninfo import make_conninfo
            candidate = dict(settings, rehearsal_dsn=make_conninfo(dsn, user=role), presentation_directory=str(temp/'presentation'))
            app = build_app(candidate)
            with TestClient(app) as client:
                checks = {}
                for path in ('/api/v1/p11/health','/api/v1/security/settings/mode/default',
                             '/api/v1/p11/incidents/check/explanations','/api/v1/p11/incidents/check/dossier'):
                    checks[path] = client.get(path).status_code
                    assert checks[path] == 401
                checks['mfa'] = client.post('/api/v1/admin-auth/mfa/verify', json={}).status_code
                assert checks['mfa'] == 422
                assert client.post('/api/v1/admin-auth/bootstrap', json={'username':'forbidden','password':'forbidden-password'}).status_code == 403
                # Independent Argon2id create/verify, never change the real account.
                from admin_auth.passwords import password_hash, verify
                hashed = password_hash('isolated-rehearsal-password')
                assert hashed.startswith('$argon2id$') and verify('isolated-rehearsal-password', hashed)
            write(ROOT/'rehearsal.json', json.dumps({'passed': True, 'http': checks,
                'administrator_preserved': True, 'projections_preserved': True,
                'bootstrap_blocked': True, 'argon2id_verified': True, 'live_database_modified': False}))
        finally:
            run([PG/'pg_ctl', '-D', temp/'pg', '-m', 'fast', '-w', 'stop'])
    print('REHEARSAL_PASSED; restored database only; no live services changed')


def apply():
    from psycopg.conninfo import conninfo_to_dict
    settings = checked()
    if os.geteuid() != 0:
        raise RuntimeError('OPERATOR_ROOT_REQUIRED')
    if not json.loads((ROOT/'rehearsal.json').read_text())['passed'] or DROPIN.exists():
        raise RuntimeError('REHEARSAL_REQUIRED_OR_EXISTING_OVERRIDE')
    if hashlib.sha256((Path(settings['base'])/'app.py').read_bytes()).hexdigest() != settings['expected_app_sha256']:
        raise RuntimeError('ACTIVE_BOOTSTRAP_DRIFT')
    values = conninfo_to_dict(environment(settings)['HARPISENSE_DATABASE_URL'])
    run(['/usr/sbin/runuser','-u','postgres','--', PG/'psql','-X','--set','ON_ERROR_STOP=1','--dbname',values['dbname']],
        input=migration_sql(values['user']).encode())
    DROPIN.parent.mkdir(parents=True, exist_ok=True)
    write(DROPIN, '[Service]\nExecStart=\nExecStart=' + str(ROOT/'venv/bin/python') + ' ' + str(ROOT/'gateway_entry.py') + '\n')
    run(['systemctl','daemon-reload'])
    try:
        run(['systemctl','restart','harpisense-p11.service'])
        import urllib.request
        for attempt in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=1) as response:
                    paths = json.load(response)['paths']
                    assert '/api/v1/admin-auth/mfa/verify' in paths
                    assert '/api/v1/p11/incidents/{incident_id}/explanations' in paths
                    break
            except Exception:
                if attempt == 29:
                    raise RuntimeError('LIVE_ROUTE_CHECK_FAILED') from None
                time.sleep(1)
    except Exception:
        DROPIN.unlink()
        run(['systemctl','daemon-reload'])
        run(['systemctl','restart','harpisense-p11.service'])
        raise
    print('APPLIED; MFA/XAI routes verified; existing administrator preserved; BitNet remains hardware-gated')


def deploy():
    """Single reviewed operator command; rehearsal runs unprivileged."""
    import pwd
    checked()
    if os.geteuid() != 0:
        raise RuntimeError('OPERATOR_ROOT_REQUIRED')
    prepare()
    account = pwd.getpwuid(ROOT.stat().st_uid).pw_name
    run(['/usr/sbin/runuser','-u',account,'--',ROOT/'venv/bin/python',
         ROOT/'upgrade_gateway.py','rehearse'])
    apply()


def smoke():
    """Check built web/API and Linux dependencies before administrative work.

    Uses an unreachable fixture DSN and a temporary cipher key. No DB touched.
    This is intentionally not reported as migrated/live acceptance.
    """
    settings = checked()
    from cryptography.fernet import Fernet
    from gateway_entry import build_web_app
    from fastapi.testclient import TestClient
    from admin_auth.passwords import password_hash, verify
    with tempfile.TemporaryDirectory(prefix='smoke-', dir=ROOT) as directory:
        key = Path(directory)/'fixture.key'
        write(key, Fernet.generate_key().decode())
        candidate = dict(settings, rehearsal_dsn='postgresql://unused@127.0.0.1:9/unreachable',
                         key_file=str(key), presentation_directory=None)
        app = build_web_app(candidate)
        with TestClient(app) as client:
            assert client.get('/').status_code == 200
            assert client.get('/api/v1/p11/health').status_code == 401
            assert client.get('/p11-api/api/v1/p11/incidents/check/explanations').status_code == 401
            assert client.post('/p11-api/api/v1/admin-auth/mfa/verify', json={}).status_code == 422
            assert client.post('/p11-api/api/v1/admin-auth/bootstrap', json={'username':'forbidden','password':'forbidden-password'}).status_code == 403
            assert client.post('/p11-api/api/v1/p11/ingest/asset', json={}).status_code == 404
        hashed = password_hash('isolated-linux-smoke-password')
        assert hashed.startswith('$argon2id$') and verify('isolated-linux-smoke-password', hashed)
        assert not verify('wrong-password', hashed)
    write(ROOT/'smoke.json', json.dumps({'passed':True,'platform':sys.platform,
        'built_frontend':True,'mfa_route_present':True,'xai_route_protected':True,
        'argon2id_create_verify':True,'live_database_touched':False,'live_service_updated':False}))
    print('SMOKE_PASSED; built UI/MFA/XAI/Argon2id; no database connection or live update')


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare','rehearse','apply','deploy','smoke'])
    try:
        {'prepare':prepare,'rehearse':rehearse,'apply':apply,'deploy':deploy,'smoke':smoke}[parser.parse_args().command]()
    except Exception as error:
        # Deliberately avoid repr/traceback, which could disclose database credentials.
        print('UPGRADE_FAILED:' + (str(error) if isinstance(error, (RuntimeError, AssertionError)) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
