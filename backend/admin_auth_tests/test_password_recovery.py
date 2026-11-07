"""Real PostgreSQL tests and a TCP HTTP acceptance check; never operational DB."""
import secrets
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pyotp
import uvicorn

import test_mfa
from test_mfa import PASSWORD, PREFIX
from admin_auth.service import AuthError
from admin_auth.password_recovery import RecoverableAdminAuth


class PasswordRecoveryTests(test_mfa.MFATests):
    def test_password_throttle_infinite_and_finite_sentinels(self):
        self.sql("UPDATE hs_admin_throttle SET blocked_until='-infinity'")
        with self.auth.transaction() as conn:
            self.assertIsNone(self.auth.throttle(conn))
        self.sql("UPDATE hs_admin_throttle SET blocked_until='infinity'")
        self.assert_error('AUTH_UNAVAILABLE', self.auth.validate_password_code, 'absent', 'invalid')
        self.sql("UPDATE hs_admin_throttle SET blocked_until=clock_timestamp()+interval '30 seconds'")
        self.assert_error('TRY_LATER', self.auth.validate_password_code, 'absent', 'invalid')

    def test_password_recovery_audit_failure_rolls_back_consumption_and_password(self):
        _, _, codes = self.codes()
        trigger = ("CREATE FUNCTION hs_password_fixture_fail() RETURNS trigger LANGUAGE plpgsql AS $$ "
                   "BEGIN RAISE EXCEPTION 'fixture audit failure'; END $$")
        def install():
            self.sql(trigger)
            self.sql('CREATE TRIGGER hs_password_fixture_failure BEFORE INSERT ON hs_admin_audit '
                     'FOR EACH ROW EXECUTE FUNCTION hs_password_fixture_fail()')
        def remove():
            self.sql('DROP TRIGGER hs_password_fixture_failure ON hs_admin_audit')
            self.sql('DROP FUNCTION hs_password_fixture_fail()')
        install()
        try:
            self.assert_error('AUTH_UNAVAILABLE', self.auth.validate_password_code, 'owner', codes[0])
        finally:
            remove()
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_password_grant')[0][0], 0)
        grant = self.auth.validate_password_code('owner', codes[0])['reset_token']
        before = self.sql('SELECT password_hash,credential_revision FROM hs_admin_account')
        install()
        try:
            self.assert_error('AUTH_UNAVAILABLE', self.auth.reset_password, grant, PASSWORD+' changed')
        finally:
            remove()
        self.assertEqual(before, self.sql('SELECT password_hash,credential_revision FROM hs_admin_account'))
        self.auth.reset_password(grant, PASSWORD+' changed')

    def codes(self):
        _, _, secret, session = self.enroll()
        self.allow_next_totp()
        codes = self.auth.issue_password_codes(session['access_token'], PASSWORD, pyotp.TOTP(secret).at(self.now()))
        return secret, session, codes['password_recovery_codes']

    def test_password_reset_preserves_mfa_and_revokes_all_authorizations(self):
        secret, session, codes = self.codes()
        before = self.sql('SELECT secret_cipher,required,enabled_at FROM hs_admin_mfa')
        grant = self.auth.validate_password_code('owner', codes[0])
        other = self.auth.validate_password_code('owner', codes[1])
        self.assertNotIn('access_token', grant)
        self.assert_error('SESSION_INVALID', self.auth.current, grant['reset_token'])
        self.assert_error('CHALLENGE_INVALID', self.auth.begin_enrollment, grant['reset_token'])
        self.assert_error('RECOVERY_INVALID', self.auth.validate_password_code, 'owner', codes[0])
        restarted = RecoverableAdminAuth(self.dsn, protection_key=self.key)
        restarted.reset_password(grant['reset_token'], PASSWORD+' changed')
        self.assertEqual(before, self.sql('SELECT secret_cipher,required,enabled_at FROM hs_admin_mfa'))
        self.assert_error('RECOVERY_INVALID', restarted.reset_password, other['reset_token'], PASSWORD+' again')
        self.assert_error('SESSION_REVOKED', restarted.current, session['access_token'])
        self.assert_error('INVALID_CREDENTIALS', restarted.login, 'owner', PASSWORD)
        challenge = restarted.login('owner', PASSWORD+' changed')
        self.assertEqual(challenge['next_step'], 'login')
        self.allow_next_totp()
        full = restarted.verify_login(challenge['challenge_token'], pyotp.TOTP(secret).at(self.now()))
        self.assertTrue(restarted.current(full['access_token'])['mfa_enabled'])

    def test_password_recovery_concurrent_code_and_grant_single_use(self):
        _, _, codes = self.codes()
        def consume(_):
            try:
                return self.auth.validate_password_code('owner', codes[0])
            except AuthError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(consume, range(4)))
        grants = [r for r in results if isinstance(r, dict)]
        self.assertEqual(len(grants), 1)
        self.assertEqual(results.count('RECOVERY_INVALID'), 3)
        def reset(_):
            try:
                self.auth.reset_password(grants[0]['reset_token'], PASSWORD+' changed')
                return 'OK'
            except AuthError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(reset, range(2))), ['OK', 'RECOVERY_INVALID'])

    def test_password_recovery_expiry_reissue_throttle_and_separation(self):
        secret, session, codes = self.codes()
        self.assert_error('REAUTHENTICATION_REQUIRED', self.auth.issue_password_codes, session['access_token'], 'wrong', None)
        self.assert_error('FACTOR_INVALID', self.auth.issue_password_codes, session['access_token'], PASSWORD, None)
        grant = self.auth.validate_password_code('owner', codes[0])['reset_token']
        self.sql("UPDATE hs_admin_password_grant SET expires_at=clock_timestamp()-interval '1 second'")
        self.assert_error('RECOVERY_INVALID', self.auth.reset_password, grant, PASSWORD+' changed')
        self.sql("UPDATE hs_admin_password_code SET expires_at=clock_timestamp()-interval '1 second'")
        self.assert_error('RECOVERY_INVALID', self.auth.validate_password_code, 'owner', codes[1])
        self.allow_next_totp()
        new = self.auth.issue_password_codes(session['access_token'], PASSWORD, pyotp.TOTP(secret).at(self.now()))
        self.assert_error('RECOVERY_INVALID', self.auth.validate_password_code, 'owner', codes[2])
        challenge = self.auth.login('owner', PASSWORD)['challenge_token']
        self.assert_error('FACTOR_INVALID', self.auth.verify_login, challenge, new['password_recovery_codes'][0], recovery=True)
        for name in ['absent', 'owner', 'absent', 'owner', 'absent']:
            self.sql("UPDATE hs_admin_throttle SET blocked_until='-infinity'")
            self.assert_error('RECOVERY_INVALID', self.auth.validate_password_code, name, secrets.token_urlsafe(32))
        self.assert_error('TRY_LATER', self.auth.validate_password_code, 'owner', new['password_recovery_codes'][0])
        audit = str(self.sql('SELECT * FROM hs_admin_audit'))
        for value in [*codes, *new['password_recovery_codes'], grant, PASSWORD]:
            self.assertNotIn(value, audit)
        database = str(self.sql('SELECT * FROM hs_admin_password_code') + self.sql('SELECT * FROM hs_admin_password_grant'))
        for value in [*codes, *new['password_recovery_codes'], grant]:
            self.assertNotIn(value, database)

    def test_password_recovery_reissue_invalidates_unused_codes_and_pending_grants(self):
        secret, session, codes = self.codes()
        grant = self.auth.validate_password_code('owner', codes[0])['reset_token']
        self.allow_next_totp()
        self.auth.issue_password_codes(session['access_token'], PASSWORD, pyotp.TOTP(secret).at(self.now()))
        self.assert_error('RECOVERY_INVALID', self.auth.validate_password_code, 'owner', codes[1])
        self.assert_error('RECOVERY_INVALID', self.auth.reset_password, grant, PASSWORD+' changed')

    def test_password_recovery_real_tcp_http(self):
        secret, session, _ = self.codes()
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(self.app, log_level='critical', access_log=False))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic()+10
            while not server.started and time.monotonic()<deadline:
                time.sleep(.01)
            self.assertTrue(server.started)
            with httpx.Client(base_url=f'http://127.0.0.1:{port}') as client:
                self.allow_next_totp()
                issued = client.post(PREFIX+'/password-recovery/codes', json={
                    'current_password': PASSWORD, 'code': pyotp.TOTP(secret).at(self.now())},
                    headers={'Authorization': 'Bearer '+session['access_token']})
                self.assertEqual(issued.status_code, 200)
                from jsonschema import Draft202012Validator
                schema = client.get('/openapi.json').json()
                Draft202012Validator(schema['components']['schemas']['PasswordCodes']).validate(issued.json())
                self.assertEqual(issued.headers['cache-control'], 'no-store')
                code = issued.json()['password_recovery_codes'][0]
                validated = client.post(PREFIX+'/password-recovery/validate', json={'username': 'owner', 'code': code})
                self.assertEqual(validated.status_code, 200)
                Draft202012Validator(schema['components']['schemas']['PasswordGrant']).validate(validated.json())
                token = validated.json()['reset_token']
                self.assertEqual(client.get(PREFIX+'/session', headers={'Authorization': 'Bearer '+token}).status_code, 401)
                response = client.post(PREFIX+'/password-recovery/reset', json={'reset_token': token, 'new_password': PASSWORD+' changed'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(client.post(PREFIX+'/password-recovery/reset', json={'reset_token': token, 'new_password': PASSWORD+' again'}).status_code, 401)
                self.assertEqual(client.post(PREFIX+'/login', json={'username': 'owner', 'password': PASSWORD+' changed'}).json()['next_step'], 'login')
                self.assertEqual(client.get(PREFIX+'/password-recovery/codes').status_code, 405)
        finally:
            server.should_exit = True
            thread.join(10)
            sock.close()
