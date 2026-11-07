"""Focused TCP acceptance of the existing MFA candidate and real composition.

Never TestClient. Only disposable mfa_http_fixture and explicit reset consent.
Output contains assertions/metadata only, never responses or fixture credentials.
"""
import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/domain'), str(ROOT/'genai')]

import httpx
import psycopg
import pyotp
from cryptography.fernet import Fernet
from jsonschema import Draft202012Validator, ValidationError

from admin_auth import AdminAuth
from admin_auth.mfa import MFAAdminAuth
from admin_auth.service import token_hash
from admin_auth_ops.mfa_local import create_private
from admin_auth_ops.http_fixture import prepare_fixture

PREFIX = '/api/v1/admin-auth'
ORIGIN = 'http://127.0.0.1:5174'
PREVIEW_ORIGIN = 'http://127.0.0.1:4174'
INSTALLATION = 'mfa-http-isolated'
PROTECTED = [('GET', '/api/v1/p11/health'), ('GET', '/api/v1/p11/incident'),
             ('GET', '/api/v1/config/current'), ('GET', '/api/v1/config/catalog'),
             ('GET', '/api/v1/config/setup'), ('PUT', '/api/v1/config/setup'),
             ('POST', '/api/v1/config/proposals'), ('GET', '/api/v1/config/history'),
             ('GET', '/api/v1/security/settings/mode/default'),
             ('PUT', '/api/v1/security/settings/mode/default'),
             ('POST', '/api/v1/security/emergency-stop'), ('GET', '/api/v1/security/audit')]


class Probe:
    def __init__(self, dsn, root):
        self.dsn, self.root = dsn, Path(root)
        self.checks, self.sensitive = [], set()
        self.logfile = self.root/'uvicorn.log'
        self.keyfile = self.root/'admin-mfa.key'
        create_private(self.keyfile, Fernet.generate_key())
        self.sensitive.add(self.keyfile.read_text())
        self.password = secrets.token_urlsafe(32)
        self.sensitive.add(self.password)
        self.username = 'http-fixture-owner'
        self.auth = MFAAdminAuth(dsn, protection_key=self.keyfile.read_bytes())
        self.process = None
        self.openapi = None

    def check(self, condition, label):
        if not condition:
            raise AssertionError(label)  # No response/body in exceptions.
        self.checks.append(label)

    def sql(self, statement, params=()):
        with psycopg.connect(self.dsn) as conn:
            result = conn.execute(statement, params)
            return result.fetchall() if result.description else None

    def reset(self):
        self.sql('TRUNCATE hs_admin_password_reset_code,hs_admin_mfa_challenge,hs_admin_recovery_code,hs_admin_mfa,hs_admin_local_grant, '
                 'hs_admin_session,hs_admin_account,hs_admin_audit')
        self.reset_throttle()

    def reset_throttle(self):
        self.sql("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity'")

    def remember(self, value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {'access_token', 'challenge_token', 'manual_key', 'provisioning_uri', 'qr_svg'}:
                    self.sensitive.add(item)
                elif key == 'recovery_codes':
                    self.sensitive.update(item)
        return value

    def start(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.url = 'http://127.0.0.1:'+str(port)
        env = {**os.environ, 'PYTHONPATH': os.pathsep.join(map(str, [ROOT/'backend', ROOT/'backend/domain', ROOT/'genai'])),
               'ADMIN_MFA_HTTP_TEST_DATABASE_URL': self.dsn, 'ADMIN_MFA_KEY_FILE': str(self.keyfile),
               'ADMIN_MFA_HTTP_ORIGINS': json.dumps([ORIGIN, PREVIEW_ORIGIN]), 'ADMIN_MFA_HTTP_INSTALLATION_ID': INSTALLATION,
               'HARPISENSE_ADMIN_USER': 'technical-http-fixture',
               'HARPISENSE_ADMIN_PASSWORD': secrets.token_urlsafe(32),
               'HARPISENSE_PROJECTION_SERVICE_TOKEN': secrets.token_urlsafe(32)}
        self.sensitive.update([env['HARPISENSE_ADMIN_PASSWORD'], env['HARPISENSE_PROJECTION_SERVICE_TOKEN']])
        self.technical = (env['HARPISENSE_ADMIN_USER'], env['HARPISENSE_ADMIN_PASSWORD'])
        self.technical_token = env['HARPISENSE_PROJECTION_SERVICE_TOKEN']
        self.log = self.logfile.open('ab')
        self.process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'admin_auth_ops.http_candidate:build_http_candidate',
            '--factory', '--host', '127.0.0.1', '--port', str(port), '--no-access-log'],
            env=env, cwd=ROOT, stdout=self.log, stderr=subprocess.STDOUT)
        self.client = httpx.Client(base_url=self.url, timeout=15, trust_env=False)
        for _ in range(150):
            if self.process.poll() is not None:
                raise AssertionError('Isolated HTTP server exited before readiness')
            try:
                if self.client.get(PREFIX+'/session').status_code == 401:
                    return
            except httpx.TransportError:
                pass
            time.sleep(.1)
        raise AssertionError('Isolated HTTP readiness timeout')

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            self.client.close()
            self.log.close()
            self.process = None

    def call(self, method, path, body=None, token=None, status=200, error=None, headers=None):
        supplied = dict(headers or {})
        if token:
            supplied['Authorization'] = 'Bearer '+token
        response = self.client.request(method, PREFIX+path, json=body, headers=supplied)
        self.check(response.status_code == status, method+' '+path+' status '+str(status))
        self.check(response.headers.get('cache-control') == 'no-store', method+' '+path+' no-store')
        if status == 204:
            return None
        value = self.remember(response.json())
        if error:
            self.check(value == {'error': {'code': error}}, path+' sanitized '+error)
        if self.openapi:
            operation = self.openapi['paths'][PREFIX+path][method.lower()]
            contract = operation['responses'][str(status)]['content']['application/json']['schema']
            try:
                Draft202012Validator({**contract, 'components': self.openapi['components']}).validate(value)
            except ValidationError:
                raise AssertionError('Published response schema mismatch: '+method+' '+path) from None
        return value

    def blocked(self, token=None):
        for method, path in PROTECTED:
            headers = {'Authorization': 'Bearer '+token} if token else {}
            response = self.client.request(method, path, headers=headers, json={} if method != 'GET' else None)
            self.check(response.status_code == 401, 'partial/anonymous denied '+method+' '+path)

    def full(self, token):
        for path in ['/api/v1/p11/health', '/api/v1/config/catalog', '/api/v1/config/current',
                     '/api/v1/config/setup', '/api/v1/security/settings/mode/default', '/api/v1/security/audit']:
            response = self.client.get(path, headers={'Authorization': 'Bearer '+token})
            self.check(response.status_code == 200, 'full session admitted '+path)

    def code(self, secret, offset=0):
        now = int(self.sql('SELECT EXTRACT(EPOCH FROM clock_timestamp())')[0][0])
        code = pyotp.TOTP(secret).at(now+offset)
        self.sensitive.add(code)
        return code

    def wait_unused_step(self):
        # Real time progression, never rewind last_step to manufacture success.
        for _ in range(330):
            now, used = self.sql('SELECT EXTRACT(EPOCH FROM clock_timestamp()),last_step FROM hs_admin_mfa WHERE account_id=1')[0]
            if int(now)//30 > used:
                return
            time.sleep(.1)
        raise AssertionError('Clock did not advance to a fresh TOTP step')

    def login(self):
        return self.call('POST', '/login', dict(username=self.username, password=self.password))

    def enroll(self, challenge):
        payload = self.call('POST', '/mfa/enrollment/begin', dict(challenge_token=challenge))
        completed = self.call('POST', '/mfa/enrollment/confirm', dict(challenge_token=challenge, code=self.code(payload['manual_key'])))
        return payload['manual_key'], completed

    def run_new_installation(self):
        self.reset()
        self.start()
        self.check(self.sql('SELECT count(*) FROM hs_admin_account')[0][0] == 0, 'fresh installation without admin')
        self.blocked()
        self.openapi = self.client.get('/openapi.json').json()
        self.check('oneOf' in self.openapi['paths'][PREFIX+'/login']['post']['responses']['200']['content']['application/json']['schema'],
                   'OpenAPI publishes exact login response union')
        preflight = self.client.options(PREFIX+'/login', headers={'Origin': ORIGIN,
            'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type'})
        self.check(preflight.status_code == 200 and preflight.headers.get('access-control-allow-origin') == ORIGIN,
                   'browser Authorization preflight exact origin')
        self.check('access-control-allow-credentials' not in preflight.headers, 'CORS no cookie credentials')
        preview = self.client.options(PREFIX+'/login', headers={'Origin': PREVIEW_ORIGIN,
            'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type'})
        self.check(preview.status_code == 200 and preview.headers.get('access-control-allow-origin') == PREVIEW_ORIGIN,
                   'preview origin explicitly allowed')
        denied = self.client.options(PREFIX+'/login', headers={'Origin': 'https://denied.invalid',
                                    'Access-Control-Request-Method': 'POST'})
        self.check(denied.status_code == 400 and 'access-control-allow-origin' not in denied.headers, 'CORS denied origin')
        self.call('POST', '/login', dict(username=self.username, password=self.password), status=403,
                  error='ORIGIN_DENIED', headers={'Origin': 'https://denied.invalid'})
        grant = self.auth.issue_local_grant()
        self.sensitive.add(grant)
        self.sql("UPDATE hs_admin_local_grant SET expires_at=clock_timestamp()-interval '1 second'")
        body = dict(bootstrap_secret=grant, username=self.username, password=self.password)
        self.call('POST', '/bootstrap', body, status=401, error='GRANT_INVALID')
        self.reset_throttle()
        body['bootstrap_secret'] = self.auth.issue_local_grant()
        self.sensitive.add(body['bootstrap_secret'])
        def bootstrap(_):
            return httpx.post(self.url+PREFIX+'/bootstrap', json=body, timeout=15, trust_env=False)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(bootstrap, range(2)))
        self.check(sorted(r.status_code for r in results) == [200, 409], 'TCP bootstrap concurrency exactly one account')
        challenge = self.remember(next(r.json() for r in results if r.status_code == 200))['challenge_token']
        self.call('POST', '/bootstrap', body, status=409, error='ALREADY_PROVISIONED')
        self.blocked(challenge)
        payload = self.call('POST', '/mfa/enrollment/begin', dict(challenge_token=challenge))
        self.call('POST', '/mfa/enrollment/begin', dict(challenge_token=challenge), status=409, error='ENROLLMENT_ALREADY_STARTED')
        self.call('POST', '/mfa/enrollment/confirm', dict(challenge_token=challenge, code='nototp'), status=401, error='FACTOR_INVALID')
        self.call('POST', '/mfa/enrollment/confirm', dict(challenge_token=challenge, code=self.code(payload['manual_key'], -90)),
                  status=401, error='FACTOR_INVALID')
        self.check(self.sql('SELECT enabled_at FROM hs_admin_mfa')[0][0] is None, 'wrong/expired enrollment code does not activate MFA')
        session = self.call('POST', '/mfa/enrollment/confirm', dict(challenge_token=challenge, code=self.code(payload['manual_key'])))
        self.full(session['access_token'])
        self.call('POST', '/mfa/enrollment/confirm', dict(challenge_token=challenge, code=self.code(payload['manual_key'])),
                  status=401, error='CHALLENGE_INVALID')
        # Partial challenge cannot reach any P11/config/control route after first factor.
        first, second = self.login(), self.login()
        self.check('access_token' not in first and first['next_step'] == 'login', 'first factor never emits full session')
        self.blocked(first['challenge_token'])
        self.call('POST', '/mfa/verify', dict(challenge_token=first['challenge_token'], code=self.code(payload['manual_key'])),
                  status=401, error='FACTOR_INVALID')
        self.wait_unused_step()
        code = self.code(payload['manual_key'])
        def verify(token):
            return httpx.post(self.url+PREFIX+'/mfa/verify', json=dict(challenge_token=token, code=code), timeout=15, trust_env=False)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(verify, [first['challenge_token'], second['challenge_token']]))
        self.check(sorted(r.status_code for r in results) == [200, 401], 'TCP concurrent TOTP accepts once')
        verified = self.remember(next(r.json() for r in results if r.status_code == 200))
        self.full(verified['access_token'])
        self.call('POST', '/logout', token=verified['access_token'], status=204)
        self.call('GET', '/session', token=verified['access_token'], status=401, error='SESSION_REVOKED')
        expiry = self.login()['challenge_token']
        self.sql("UPDATE hs_admin_mfa_challenge SET expires_at=clock_timestamp()-interval '1 second' WHERE token_hash=%s", (token_hash(expiry),))
        self.call('POST', '/mfa/verify', dict(challenge_token=expiry, code=self.code(payload['manual_key'])), status=401, error='CHALLENGE_INVALID')
        self.reset_throttle()
        exhausted = self.login()['challenge_token']
        for _ in range(5):
            self.call('POST', '/mfa/verify', dict(challenge_token=exhausted, code='nototp'), status=401, error='FACTOR_INVALID')
        response = self.client.post(PREFIX+'/login', json=dict(username=self.username, password=self.password))
        self.check(response.status_code == 429 and int(response.headers['retry-after']) > 0, 'global throttle persists across valid first factor')
        time.sleep(int(response.headers['retry-after'])+.1)
        self.call('POST', '/mfa/verify', dict(challenge_token=exhausted, code=self.code(payload['manual_key'])), status=401, error='CHALLENGE_INVALID')
        self.check(self.sql('SELECT attempts FROM hs_admin_mfa_challenge WHERE token_hash=%s', (token_hash(exhausted),))[0][0] == 5,
                   'challenge attempt budget persists over HTTP')
        self.reset_throttle()
        recovery_challenges = [self.login()['challenge_token'] for _ in range(2)]
        recovery_code = session['recovery_codes'][0]
        def recover(token):
            return httpx.post(self.url+PREFIX+'/mfa/recover', json=dict(challenge_token=token, code=recovery_code), timeout=15, trust_env=False)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(recover, recovery_challenges))
        self.check(sorted(r.status_code for r in results) == [200, 401], 'TCP recovery concurrency consumes exactly once')
        recovered = self.remember(next(r.json() for r in results if r.status_code == 200))
        self.check(recovered['next_step'] == 'enroll' and 'access_token' not in recovered, 'recovery grants replacement only')
        self.blocked(recovered['challenge_token'])
        self.call('GET', '/session', token=session['access_token'], status=401, error='SESSION_REVOKED')
        retry = self.login()['challenge_token']
        self.call('POST', '/mfa/recover', dict(challenge_token=retry, code=recovery_code), status=401, error='FACTOR_INVALID')
        _, replaced = self.enroll(recovered['challenge_token'])
        self.full(replaced['access_token'])
        # Exercise actual installer CLI with no secret in argv or stdout.
        env = {**os.environ, 'PYTHONPATH': os.pathsep.join(map(str, [ROOT/'backend', ROOT/'backend/domain', ROOT/'genai'])), 'DATABASE_URL': self.dsn}
        grant_file = self.root/'local-recovery.secret'
        process = subprocess.run([sys.executable, '-m', 'admin_auth_ops.mfa_local', 'recover', '--key-file', str(self.keyfile),
                                  '--grant-file', str(grant_file)], env=env, capture_output=True)
        self.check(process.returncode == 0 and not process.stdout and not process.stderr, 'installer recovery CLI has no secret output')
        grant = grant_file.read_text()
        self.sensitive.add(grant)
        body = dict(bootstrap_secret=grant, username=self.username, password=self.password)
        local = self.call('POST', '/local-recovery', body)
        self.check(local['next_step'] == 'enroll' and 'access_token' not in local, 'local recovery requires enrollment before access')
        self.call('POST', '/local-recovery', body, status=401, error='GRANT_INVALID')
        self.call('GET', '/session', token=replaced['access_token'], status=401, error='SESSION_REVOKED')
        self.blocked(local['challenge_token'])
        _, session = self.enroll(local['challenge_token'])
        pending = self.login()['challenge_token']
        new_password = secrets.token_urlsafe(32)
        self.sensitive.add(new_password)
        self.call('PUT', '/password', dict(current_password=self.password, new_password=new_password), token=session['access_token'])
        self.call('GET', '/session', token=session['access_token'], status=401, error='SESSION_REVOKED')
        self.call('POST', '/mfa/verify', dict(challenge_token=pending, code='123456'), status=401, error='CHALLENGE_INVALID')
        self.stop()

    def run_existing_installation(self):
        # First application of 002 to a genuinely pre-MFA account/session.
        # A new isolated schema avoids dropping any previous test artifacts.
        schema = 'mfa_http_legacy_'+secrets.token_hex(4)
        with psycopg.connect(self.dsn) as conn:
            conn.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
        self.dsn += ('&' if '?' in self.dsn else '?')+urlencode({'options': '-csearch_path='+schema})
        self.sql((ROOT/'backend/delivery/001_local.sql').read_text())
        self.sql((ROOT/'backend/admin_auth/001_admin_auth.sql').read_text())
        legacy = AdminAuth(self.dsn)
        legacy.provision(self.username, self.password)
        old = legacy.login(self.username, self.password)['access_token']
        self.sensitive.add(old)
        before = self.sql('SELECT username,password_hash,credential_revision FROM hs_admin_account')
        sessions_before = self.sql('SELECT token_hash,revoked_at FROM hs_admin_session')
        self.check(self.sql("SELECT to_regclass('hs_admin_mfa')")[0][0] is None,
                   'legacy fixture has no MFA tables before first additive migration')
        self.sql((ROOT/'backend/admin_auth/002_admin_mfa.sql').read_text())
        self.sql((ROOT/'backend/admin_auth/003_password_reset.sql').read_text())
        self.check(before == self.sql('SELECT username,password_hash,credential_revision FROM hs_admin_account') and
                   sessions_before == self.sql('SELECT token_hash,revoked_at FROM hs_admin_session'), 'additive migration preserves existing identity and sessions')
        self.start()
        if self.openapi is None:
            self.openapi = self.client.get('/openapi.json').json()
        state = self.call('GET', '/session', token=old)
        self.check(not state['mfa_enabled'], 'existing session works before opt-in')
        self.full(old)
        self.check('access_token' in self.login(), 'existing password login works before opt-in')
        enrollment = self.call('POST', '/mfa/enrollment/authorize', dict(current_password=self.password), token=old)
        details = self.call('POST', '/mfa/enrollment/begin', dict(challenge_token=enrollment['challenge_token']))
        self.call('POST', '/mfa/enrollment/confirm', dict(challenge_token=enrollment['challenge_token'], code='nototp'), status=401, error='FACTOR_INVALID')
        self.call('GET', '/session', token=old)
        self.check(before == self.sql('SELECT username,password_hash,credential_revision FROM hs_admin_account'), 'pending adoption never resets password')
        complete = self.call('POST', '/mfa/enrollment/confirm', dict(challenge_token=enrollment['challenge_token'], code=self.code(details['manual_key'])))
        self.call('GET', '/session', token=old, status=401, error='SESSION_REVOKED')
        self.check(before == self.sql('SELECT username,password_hash,credential_revision FROM hs_admin_account'), 'confirmed adoption preserves identity and password')
        self.full(complete['access_token'])
        self.stop()
        # Same protected key restored separately from database, then a real restart.
        backup = self.keyfile.read_bytes()
        self.keyfile.unlink()
        create_private(self.keyfile, backup)
        self.start()
        challenge = self.login()
        self.check(challenge['next_step'] == 'login' and 'access_token' not in challenge, 'restart and restored key preserve MFA enforcement')
        self.blocked(challenge['challenge_token'])
        self.wait_unused_step()
        session = self.call('POST', '/mfa/verify', dict(challenge_token=challenge['challenge_token'], code=self.code(details['manual_key'])))
        self.full(session['access_token'])
        self.call('POST', '/logout', token=session['access_token'], status=204)
        self.call('GET', '/session', token=session['access_token'], status=401, error='SESSION_REVOKED')
        self.stop()

    def sanitized(self):
        audit = json.dumps(self.sql('SELECT event,result,account_id FROM hs_admin_audit'))
        logs = self.logfile.read_text()
        self.check(all(value not in logs and value not in audit for value in self.sensitive), 'server logs and audit contain no supplied/generated secrets')


def prepare(dsn):
    with psycopg.connect(dsn) as conn:
        if conn.info.dbname != 'mfa_http_fixture' or os.environ.get('ADMIN_MFA_HTTP_ALLOW_RESET') != 'yes':
            raise RuntimeError('Explicit disposable mfa_http_fixture and reset consent required')
    prepare_fixture(dsn)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--openapi-output', type=Path)
    parser.add_argument('--report-output', type=Path)
    parser.add_argument('--phase', choices=['all', 'existing'], default='all')
    args = parser.parse_args()
    dsn = os.environ['ADMIN_MFA_HTTP_TEST_DATABASE_URL']
    prepare(dsn)
    with tempfile.TemporaryDirectory(prefix='mfa-http-') as directory:
        probe = Probe(dsn, directory)
        try:
            if args.phase == 'all':
                probe.run_new_installation()
            probe.run_existing_installation()
            probe.sanitized()
            schema = json.dumps(probe.openapi, ensure_ascii=False, indent=2)+'\n'
            if args.openapi_output:
                args.openapi_output.write_text(schema, encoding='utf-8')
            report = {'transport': 'Uvicorn HTTP over TCP loopback', 'database': 'mfa_http_fixture',
                      'phase': args.phase,
                      'postgresql': probe.sql('SHOW server_version')[0][0], 'checks_passed': len(probe.checks),
                      'checks': probe.checks, 'openapi_sha256': hashlib.sha256(schema.encode()).hexdigest(),
                      'operational_deployment': False}
            if args.report_output:
                args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps({key: value for key, value in report.items() if key != 'checks'}, ensure_ascii=False))
        finally:
            probe.stop()


if __name__ == '__main__':
    main()
