"""Controlled P11 account deployment. Run only as the existing service operator.

No secrets in arguments, output, new environment files or browser configuration.
This tool never restarts services, changes networking, drops tables or restores DBs.
"""
import argparse
import base64
import getpass
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict

BASE = Path('/opt/harpisense/staging/p11-postgresql')
PACKAGE = Path('/opt/harpisense/integration-v2/HarpiSense_Pacote13_Integracao_Testes_v2')
RELEASE = Path(__file__).resolve().parents[1]
MANIFEST = RELEASE / 'release.json'
sys.path.insert(0, str(RELEASE))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration():
    # Same environment parser as the deployed service; do not print values.
    values = dict(line.split('=', 1) for line in (BASE/'.env').read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    os.environ.update(values)
    return values


def atomic(path, content):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.auth-install-', delete=False) as stream:
        temporary = Path(stream.name)
        os.chmod(temporary, 0o600)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def manifest():
    value = json.loads(MANIFEST.read_text())
    for name, expected in value['files'].items():
        path = (RELEASE/name).resolve()
        if not path.is_relative_to(RELEASE) or digest(path) != expected:
            raise RuntimeError('Release file mismatch: '+name)
    return value


def baseline(value):
    for relative, expected in value['baseline'].items():
        path = PACKAGE/relative[8:] if relative.startswith('package/') else BASE/relative
        if digest(path) != expected:
            raise RuntimeError('Active file changed; stop and compare: '+relative)


def projection_receipt(conn):
    # Canonical representation across source/restore server timezone settings.
    conn.execute("SET LOCAL TIME ZONE 'UTC'")
    return conn.execute("SELECT count(*),md5(COALESCE(string_agg(md5(row_to_json(p)::text),'' "
                        "ORDER BY kind,id,revision),'')) FROM projections p").fetchone()


def backup(value, config):
    baseline(value)
    destination = BASE/'.admin-auth-backups'/value['release']
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(destination.parent, 0o700)
    os.chmod(destination, 0o700)
    shutil.copy2(BASE/'app.py', destination/'app.original.py')
    os.chmod(destination/'app.original.py', 0o600)
    parameters = conninfo_to_dict(config['HARPISENSE_DATABASE_URL'])
    variables = dict(os.environ)
    for key, env_key in [('host','PGHOST'),('port','PGPORT'),('user','PGUSER'),
                         ('password','PGPASSWORD'),('dbname','PGDATABASE'),('sslmode','PGSSLMODE')]:
        if key in parameters:
            variables[env_key] = parameters[key]
    # No DSN or password in argv, stdout, stderr, shell history or the receipt.
    dump = destination/'p11.before.dump'
    with psycopg.connect(config['HARPISENSE_DATABASE_URL']) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        receipt = projection_receipt(conn)
        snapshot = conn.execute('SELECT pg_export_snapshot()').fetchone()[0]
        result = subprocess.run(['/usr/bin/pg_dump','--format=custom','--snapshot',snapshot,'--file',str(dump)],
                                env=variables, capture_output=True)
    if result.returncode:
        raise RuntimeError('pg_dump failed; no installation performed')
    os.chmod(dump, 0o600)
    result = subprocess.run(['/usr/bin/pg_restore','--list',str(dump)], capture_output=True)
    if result.returncode:
        raise RuntimeError('Backup archive cannot be listed')
    atomic(destination/'backup.json', json.dumps(dict(release=value['release'],
           created_at=datetime.now(timezone.utc).isoformat(), dump_sha256=digest(dump),
           projection_count=receipt[0], projection_digest=receipt[1],
           baseline=value['baseline']), indent=2))
    # Guarded rollback closes administrative access instead of reviving technical Basic.
    guarded = (BASE/'app.py').read_text()+'''\n
# Recovery mode: administrative API CLOSED; technical ingestion contract preserved.
from fastapi.responses import JSONResponse
@app.middleware("http")
async def recovery_guard(request, call_next):
    technical = (request.method == "POST" and
                 request.url.path.startswith("/api/v1/p11/ingest/") and
                 len(request.url.path.split("/")) == 6)
    if request.url.path.startswith("/api/") and not technical:
        return JSONResponse({"error":{"code":"ADMIN_RECOVERY_REQUIRED"}},
                            status_code=503, headers={"Cache-Control":"no-store"})
    return await call_next(request)
'''
    atomic(destination/'app.recovery.py', guarded)
    print(json.dumps(dict(backup=str(destination), dump_sha256=digest(dump),
                          projection_count=receipt[0], projection_digest=receipt[1])))


def migrate(value, config):
    baseline(value)
    saved = BASE/'.admin-auth-backups'/value['release']
    if not (saved/'restore-verified.json').is_file():
        raise RuntimeError('Isolated backup restoration receipt required before migration')
    receipt = json.loads((saved/'restore-verified.json').read_text())
    original = json.loads((saved/'backup.json').read_text())
    if any(receipt.get(key) != original[key] for key in
           ['dump_sha256','projection_count','projection_digest']):
        raise RuntimeError('Restoration receipt does not match backup')
    with psycopg.connect(config['HARPISENSE_DATABASE_URL']) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        if conn.execute("SELECT to_regclass('hs_admin_schema_version')").fetchone()[0]:
            raise RuntimeError('Auth schema exists; compare it explicitly instead of reapplying')
        before = projection_receipt(conn)
        sql = (RELEASE/'admin_auth/001_admin_auth.sql').read_text()
        if sql.count('\nBEGIN;\n') != 1 or not sql.endswith('COMMIT;\n'):
            raise RuntimeError('Unexpected migration transaction boundaries')
        conn.execute(sql.replace('\nBEGIN;\n','\n',1).removesuffix('COMMIT;\n'))
        after = projection_receipt(conn)
        if before != after:
            raise RuntimeError('Unexpected projection change during migration; inspect receipt')
    atomic(saved/'migration.json', json.dumps(dict(version=1, projection_count=after[0],
           projection_digest=after[1], applied_at=datetime.now(timezone.utc).isoformat()), indent=2))
    print('Auth schema version 1 applied; projections preserved.')


def provision(config):
    from admin_auth import AdminAuth
    if not sys.stdin.isatty():
        raise RuntimeError('Interactive operator terminal required')
    username = input('Novo usuário administrativo HarpiSense: ')
    password = getpass.getpass('Nova senha própria (8–128 caracteres): ')
    confirm = getpass.getpass('Confirme a nova senha: ')
    if password != confirm:
        raise RuntimeError('Passwords do not match')
    mqtt_password = (BASE/'.mqtt_password').read_text().strip() if (BASE/'.mqtt_password').exists() else ''
    AdminAuth(config['HARPISENSE_DATABASE_URL'],
              technical_credentials=[('harpisense_mqtt',mqtt_password)]).provision(username,password)
    password = confirm = mqtt_password = ''
    print('Conta própria provisionada; nenhuma sessão criada. Senha não foi salva em arquivo.')


def activate(value, config):
    baseline(value)
    with psycopg.connect(config['HARPISENSE_DATABASE_URL']) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        if conn.execute('SELECT count(*) FROM hs_admin_account').fetchone()[0] != 1:
            raise RuntimeError('Provision the administrative account before activation')
    saved = BASE/'.admin-auth-backups'/value['release']
    if not (saved/'migration.json').is_file():
        raise RuntimeError('Migration receipt missing')
    original = (saved/'app.original.py').read_text()
    needle = '    install_deterministic_harpia(app, store)\n'
    if original.count(needle) != 1:
        raise RuntimeError('Unexpected bootstrap; refusing blind replacement')
    code = original.replace(needle, needle+f'''    # Administrative release: {value['release']}
    sys.path.insert(0, {str(RELEASE)!r})
    from admin_auth import AdminAuth, install_admin_auth
    from pathlib import Path
    mqtt_file = Path({str(BASE/'.mqtt_password')!r})
    mqtt_password = mqtt_file.read_text().strip() if mqtt_file.exists() else ''
    install_admin_auth(app, AdminAuth(conninfo, technical_credentials=[('harpisense_mqtt', mqtt_password)]),
                       allowed_origins=['http://127.0.0.1:4174', 'http://127.0.0.1:5174'])
    app.state.admin_auth_release = {value['release']!r}
''')
    compile(code, str(BASE/'app.py'), 'exec')
    atomic(BASE/'app.py', code)
    atomic(saved/'activation.json',json.dumps(dict(release=value['release'],bootstrap_sha256=digest(BASE/'app.py'),
           activated_at=datetime.now(timezone.utc).isoformat()),indent=2))
    print('Bootstrap preparado. Reinicie SOMENTE harpisense-p11.service com sudo interativo.')


def http(method, path, *, body=None, token=None, authorization=None):
    headers = {'Origin':'http://127.0.0.1:4174'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    if authorization:
        headers['Authorization'] = authorization
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request('http://127.0.0.1:8000'+path,method=method,headers=headers,data=data)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except urllib.error.HTTPError as error:
        content = error.read()
        return error.code, json.loads(content) if content else None


def verify(value, config):
    if not sys.stdin.isatty():
        raise RuntimeError('Interactive operator terminal required')
    username = input('Usuário administrativo próprio: ')
    password = getpass.getpass('Senha administrativa (somente nesta execução): ')
    prefix = '/api/v1/admin-auth'
    receipt = dict(release=value['release'],observed_at=datetime.now(timezone.utc).isoformat(),checks={})
    checks = receipt['checks']

    def check(name, actual, expected):
        checks[name] = actual
        if actual != expected:
            raise RuntimeError('Verification failed: '+name)

    token = None
    issued = []
    try:
        check('anonymous_telemetry',http('GET','/api/v1/p11/telemetry')[0],401)
        technical = base64.b64encode((config['HARPISENSE_ADMIN_USER']+':'+config['HARPISENSE_ADMIN_PASSWORD']).encode()).decode()
        check('technical_basic_refused',http('GET','/api/v1/p11/telemetry',authorization='Basic '+technical)[0],401)
        status, result = http('POST',prefix+'/login',body={'username':username,'password':password})
        check('valid_login',status,200)
        token = result['access_token']
        issued.append(token)
        # Separate sessions used only for controlled expiration checks.
        expiration_tokens = []
        for _ in range(2):
            status, result = http('POST',prefix+'/login',body={'username':username,'password':password})
            check('expiration_session_'+str(len(expiration_tokens)+1),status,200)
            expiration_tokens.append(result['access_token'])
            issued.append(result['access_token'])
        password = ''
        check('session',http('GET',prefix+'/session',token=token)[0],200)
        check('health',http('GET','/api/v1/p11/health',token=token)[0],200)
        status, rows = http('GET','/api/v1/p11/telemetry?limit=3&offset=0',token=token)
        check('telemetry',status,200)
        receipt['telemetry_ids'] = [row['id'] for row in rows]
        check('invalid_login',http('POST',prefix+'/login',body={'username':username,'password':'invalid-'+os.urandom(12).hex()})[0],401)
        check('invalid_session',http('GET',prefix+'/session',token='z'*43)[0],401)
        check('logout',http('POST',prefix+'/logout',token=token)[0],204)
        check('logout_replay_refused',http('GET','/api/v1/p11/telemetry',token=token)[0],401)
        token = None
        from admin_auth.service import token_hash
        for name, expiry_token, assignment in [
            ('absolute_expiration',expiration_tokens[0],"expires_at=clock_timestamp()-interval '1 second'"),
            ('idle_expiration',expiration_tokens[1],"last_seen_at=clock_timestamp()-interval '31 minutes'")]:
            with psycopg.connect(config['HARPISENSE_DATABASE_URL']) as conn:
                # Whitelisted SQL assignment; affects this verifier's session only.
                conn.execute('UPDATE hs_admin_session SET '+assignment+' WHERE token_hash=%s',
                             (token_hash(expiry_token),))
            status, result = http('GET',prefix+'/session',token=expiry_token)
            check(name,status,401)
            check(name+'_code',result['error']['code'],'SESSION_EXPIRED')
        receipt.update(mfa_available=False,email_recovery_available=False)
        target = BASE/'.admin-auth-backups'/value['release']/'live-verification.json'
        atomic(target,json.dumps(receipt,indent=2))
        print(json.dumps(receipt,indent=2))
    finally:
        password = ''
        if issued:
            from admin_auth.service import token_hash
            with psycopg.connect(config['HARPISENSE_DATABASE_URL']) as conn:
                conn.execute('UPDATE hs_admin_session SET revoked_at=COALESCE(revoked_at,clock_timestamp()) '
                             'WHERE token_hash=ANY(%s)',([token_hash(item) for item in issued],))


def recover(value):
    saved = BASE/'.admin-auth-backups'/value['release']
    activation = json.loads((saved/'activation.json').read_text())
    if digest(BASE/'app.py') != activation['bootstrap_sha256']:
        raise RuntimeError('Bootstrap changed after activation; compare before recovery')
    atomic(BASE/'app.py',(saved/'app.recovery.py').read_text())
    print('Bootstrap de recuperação preparado: API administrativa fechada; banco e ingestão preservados.')
    print('Reinicie somente harpisense-p11.service. Não restaure o banco nem o Basic administrativo.')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['backup','migrate','provision','activate','verify','recover'])
    args = parser.parse_args()
    value = manifest()
    config = configuration()
    if args.command == 'backup': backup(value,config)
    elif args.command == 'migrate': migrate(value,config)
    elif args.command == 'provision': provision(config)
    elif args.command == 'activate': activate(value,config)
    elif args.command == 'verify': verify(value,config)
    else: recover(value)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Unexpected exceptions may contain a DSN. Do not dump traceback or DB detail.
        from admin_auth import AuthError
        print(error.code if isinstance(error,AuthError) else str(error) if isinstance(error,RuntimeError) else 'Operation failed: '+type(error).__name__+
              '. Inspect safe receipts and compare deployment files; no automatic fallback.',file=sys.stderr)
        raise SystemExit(1) from None
