"""Security-boundary tests against a disposable PostgreSQL, never SQLite.

ADMIN_MFA_TEST_DATABASE_URL must name auth_fixture; no production DSN fallback.
No sleep/time mocks in service: expired challenges and steps tested explicitly.
"""
import os
import secrets
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/domain'), str(ROOT/'genai')]

import psycopg
import pyotp
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from admin_auth import AdminAuth, AuthError
from admin_auth.candidate import install_candidate_admin_auth
from admin_auth.mfa import MFAAdminAuth
from admin_auth.service import token_hash
from delivery.projections import create_app
from delivery.postgres_store import PostgresStore

PASSWORD = 'human owner password fixture only'
TECHNICAL = ('technical-writer', 'technical-password-fixture-only')
PREFIX = '/api/v1/admin-auth'


@unittest.skipUnless(os.getenv('ADMIN_MFA_TEST_DATABASE_URL'), 'Isolated PostgreSQL not configured')
class MFATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['ADMIN_MFA_TEST_DATABASE_URL']
        with psycopg.connect(cls.dsn) as conn:
            if conn.execute('SELECT current_database()').fetchone()[0] != 'auth_fixture':
                raise RuntimeError('Dedicated disposable auth_fixture required')
            conn.execute((ROOT/'backend/delivery/001_local.sql').read_text())
            if not conn.execute("SELECT to_regclass('hs_admin_schema_version')").fetchone()[0]:
                conn.execute((ROOT/'backend/admin_auth/001_admin_auth.sql').read_text())
            conn.execute((ROOT/'backend/admin_auth/002_admin_mfa.sql').read_text())
            conn.execute((ROOT/'backend/admin_auth/003_password_reset.sql').read_text())
            conn.execute((ROOT/'backend/admin_auth/004_first_access.sql').read_text())

    def sql(self, statement, params=()):
        with psycopg.connect(self.dsn) as conn:
            result = conn.execute(statement, params)
            return result.fetchall() if result.description else None

    def setUp(self):
        self.sql('TRUNCATE hs_admin_first_access,hs_admin_password_reset_code,hs_admin_mfa_challenge,hs_admin_recovery_code,hs_admin_mfa,hs_admin_local_grant, '
                 'hs_admin_session,hs_admin_account,hs_admin_audit')
        self.sql("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity'")
        self.key = Fernet.generate_key()
        self.app = create_app(PostgresStore(self.dsn), username=TECHNICAL[0], password=TECHNICAL[1], service_token='fixture-ingest-token')
        self.auth = install_candidate_admin_auth(self.app, self.dsn, protection_key=self.key,
                                                technical_credentials=[TECHNICAL], allowed_origins=['https://dashboard.example'])
        self.client = TestClient(self.app)

    def assert_error(self, code, function, *args, **kwargs):
        with self.assertRaises(AuthError) as ctx:
            function(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def bootstrap(self):
        grant = self.auth.issue_local_grant()
        challenge = self.auth.bootstrap(grant, 'owner', PASSWORD)['challenge_token']
        return grant, challenge

    def now(self):
        return int(self.sql('SELECT EXTRACT(EPOCH FROM clock_timestamp())')[0][0])

    def enroll(self):
        grant, challenge = self.bootstrap()
        payload = self.auth.begin_enrollment(challenge)
        secret = payload['manual_key']
        session = self.auth.confirm_enrollment(challenge, pyotp.TOTP(secret).at(self.now()))
        return grant, challenge, secret, session

    def allow_next_totp(self):
        # Model a later unused step without sleeping; production never rewinds it.
        self.sql('UPDATE hs_admin_mfa SET last_step=-1')

    def test_bootstrap_requires_local_secret_and_never_emits_admin_session(self):
        self.assert_error('GRANT_INVALID', self.auth.bootstrap, secrets.token_urlsafe(32), 'owner', PASSWORD)
        grant, challenge = self.bootstrap()
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_session')[0][0], 0)
        self.assert_error('SESSION_INVALID', self.auth.current, challenge)
        self.assert_error('ALREADY_PROVISIONED', self.auth.bootstrap, grant, 'second', PASSWORD)
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_account')[0][0], 1)
        self.assert_error('PROTECTED_BOOTSTRAP_REQUIRED', self.auth.provision, 'second', PASSWORD)
        self.assertNotIn('access_token', self.auth.login('owner', PASSWORD))

    def test_expired_reissued_and_consumed_grants(self):
        expired = self.auth.issue_local_grant()
        self.sql("UPDATE hs_admin_local_grant SET expires_at=clock_timestamp()-interval '1 second'")
        self.assert_error('GRANT_INVALID', self.auth.bootstrap, expired, 'owner', PASSWORD)
        replaced = self.auth.issue_local_grant()
        current = self.auth.issue_local_grant()
        self.assert_error('GRANT_INVALID', self.auth.bootstrap, replaced, 'owner', PASSWORD)
        self.auth.bootstrap(current, 'owner', PASSWORD)
        self.assertIsNotNone(self.sql('SELECT consumed_at FROM hs_admin_local_grant')[0][0])
        self.assert_error('ALREADY_PROVISIONED', self.auth.bootstrap, current, 'owner', PASSWORD)

    def test_concurrent_bootstrap_only_one_account_and_challenge(self):
        grant = self.auth.issue_local_grant()
        def attempt(name):
            try:
                self.auth.bootstrap(grant, name, PASSWORD)
                return 'OK'
            except AuthError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ['first', 'second']))
        self.assertCountEqual(results, ['OK', 'ALREADY_PROVISIONED'])
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_account')[0][0], 1)

    def test_confirm_only_activates_after_valid_code_and_protects_secret(self):
        _, challenge = self.bootstrap()
        payload = self.auth.begin_enrollment(challenge)
        secret = payload['manual_key']
        self.assertIn('<svg', payload['qr_svg'])
        self.assertIn('otpauth://totp/', payload['provisioning_uri'])
        self.assertIsNone(self.sql('SELECT enabled_at FROM hs_admin_mfa')[0][0])
        self.assert_error('FACTOR_INVALID', self.auth.confirm_enrollment, challenge, 'bad')
        old = pyotp.TOTP(secret).at(self.now()-90)
        self.assert_error('FACTOR_INVALID', self.auth.confirm_enrollment, challenge, old)
        session = self.auth.confirm_enrollment(challenge, pyotp.TOTP(secret).at(self.now()))
        self.assertTrue(self.auth.current(session['access_token'])['mfa_enabled'])
        self.assertEqual(len(session['recovery_codes']), 10)
        self.assert_error('CHALLENGE_INVALID', self.auth.confirm_enrollment, challenge, pyotp.TOTP(secret).at(self.now()))
        rows = str(self.sql('SELECT secret_cipher FROM hs_admin_mfa') + self.sql('SELECT code_hash FROM hs_admin_recovery_code'))
        self.assertNotIn(secret, rows)
        for code in session['recovery_codes']:
            self.assertNotIn(code, rows)

    def test_login_second_factor_and_replay_across_challenges(self):
        _, _, secret, session = self.enroll()
        first = self.auth.login('owner', PASSWORD)
        self.assertEqual(first['next_step'], 'login')
        self.assertNotIn('access_token', first)
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_session')[0][0], 1)
        self.assert_error('FACTOR_INVALID', self.auth.verify_login, first['challenge_token'], pyotp.TOTP(secret).at(self.now()))
        self.allow_next_totp()
        success = self.auth.verify_login(first['challenge_token'], pyotp.TOTP(secret).at(self.now()))
        self.assertTrue(self.auth.current(success['access_token'])['authenticated'])
        second = self.auth.login('owner', PASSWORD)['challenge_token']
        self.assert_error('FACTOR_INVALID', self.auth.verify_login, second, pyotp.TOTP(secret).at(self.now()))
        self.auth.logout(success['access_token'])
        self.assert_error('SESSION_REVOKED', self.auth.current, success['access_token'])

    def test_expired_challenge_wrong_codes_and_attempt_budget(self):
        _, _, secret, _ = self.enroll()
        challenge = self.auth.login('owner', PASSWORD)['challenge_token']
        self.sql("UPDATE hs_admin_mfa_challenge SET expires_at=clock_timestamp()-interval '1 second'")
        self.assert_error('CHALLENGE_INVALID', self.auth.verify_login, challenge, pyotp.TOTP(secret).at(self.now()))
        self.sql("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity'")
        challenge = self.auth.login('owner', PASSWORD)['challenge_token']
        for _ in range(5):
            self.sql("UPDATE hs_admin_throttle SET blocked_until='-infinity'")
            self.assert_error('FACTOR_INVALID', self.auth.verify_login, challenge, 'wrong')
        self.sql("UPDATE hs_admin_throttle SET blocked_until='-infinity'")
        self.assert_error('CHALLENGE_INVALID', self.auth.verify_login, challenge, pyotp.TOTP(secret).at(self.now()))
        self.assertEqual(self.sql('SELECT attempts FROM hs_admin_mfa_challenge WHERE token_hash=%s', (token_hash(challenge),))[0][0], 5)
        self.assertGreater(self.sql('SELECT failures FROM hs_admin_throttle')[0][0], 0)

    def test_global_throttle_survives_rollback_and_alternate_challenges(self):
        self.bootstrap()
        for _ in range(5):
            self.assert_error('INVALID_CREDENTIALS', self.auth.login, 'owner', 'wrong')
        self.assert_error('TRY_LATER', self.auth.login, 'owner', PASSWORD)
        self.assertGreater(self.sql("SELECT EXTRACT(EPOCH FROM blocked_until-clock_timestamp()) FROM hs_admin_throttle")[0][0], 0)

    def test_recovery_is_one_use_replacement_only_and_revokes_sessions(self):
        _, _, _, session = self.enroll()
        challenge = self.auth.login('owner', PASSWORD)['challenge_token']
        code = session['recovery_codes'][0]
        limited = self.auth.verify_login(challenge, code, recovery=True)
        self.assertEqual(limited['next_step'], 'enroll')
        self.assertNotIn('access_token', limited)
        self.assert_error('SESSION_REVOKED', self.auth.current, session['access_token'])
        retry = self.auth.login('owner', PASSWORD)['challenge_token']
        self.assert_error('FACTOR_INVALID', self.auth.verify_login, retry, code, recovery=True)
        payload = self.auth.begin_enrollment(limited['challenge_token'])
        replacement = self.auth.confirm_enrollment(limited['challenge_token'], pyotp.TOTP(payload['manual_key']).at(self.now()))
        self.assertTrue(self.auth.current(replacement['access_token'])['mfa_enabled'])
        self.assertNotIn(code, replacement['recovery_codes'])
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_recovery_code WHERE revoked_at IS NULL')[0][0], 10)

    def test_existing_account_migration_does_not_reset_password_or_revoke_session(self):
        legacy = AdminAuth(self.dsn)
        legacy.provision('owner', PASSWORD)
        session = legacy.login('owner', PASSWORD)
        before = self.sql('SELECT password_hash,credential_revision FROM hs_admin_account')
        self.sql((ROOT/'backend/admin_auth/002_admin_mfa.sql').read_text())
        self.assertEqual(before, self.sql('SELECT password_hash,credential_revision FROM hs_admin_account'))
        self.assertTrue(self.auth.current(session['access_token'])['authenticated'])
        self.assertIn('access_token', self.auth.login('owner', PASSWORD))
        self.assert_error('REAUTHENTICATION_REQUIRED', self.auth.authorize_enrollment, session['access_token'], 'wrong')
        challenge = self.auth.authorize_enrollment(session['access_token'], PASSWORD)['challenge_token']
        payload = self.auth.begin_enrollment(challenge)
        self.assertTrue(self.auth.current(session['access_token'])['authenticated'])
        self.auth.confirm_enrollment(challenge, pyotp.TOTP(payload['manual_key']).at(self.now()))
        self.assertEqual(before, self.sql('SELECT password_hash,credential_revision FROM hs_admin_account'))
        self.assert_error('SESSION_REVOKED', self.auth.current, session['access_token'])
        self.assertEqual(self.auth.login('owner', PASSWORD)['next_step'], 'login')

    def test_replacement_requires_password_and_current_totp_and_keeps_old_until_confirm(self):
        _, _, secret, session = self.enroll()
        self.assert_error('REAUTHENTICATION_REQUIRED', self.auth.authorize_enrollment, session['access_token'], 'wrong', '000000')
        self.assert_error('FACTOR_INVALID', self.auth.authorize_enrollment, session['access_token'], PASSWORD, None)
        self.allow_next_totp()
        challenge = self.auth.authorize_enrollment(session['access_token'], PASSWORD, pyotp.TOTP(secret).at(self.now()))['challenge_token']
        original = self.sql('SELECT secret_cipher FROM hs_admin_mfa')
        self.auth.begin_enrollment(challenge)
        self.assertEqual(original, self.sql('SELECT secret_cipher FROM hs_admin_mfa'))
        self.auth.cancel_challenge(challenge)
        self.assert_error('CHALLENGE_INVALID', self.auth.begin_enrollment, challenge)
        self.assertTrue(self.auth.current(session['access_token'])['authenticated'])

    def test_local_recovery_requires_operator_grant_and_password_without_reset(self):
        _, _, _, session = self.enroll()
        before = self.sql('SELECT password_hash FROM hs_admin_account')
        grant = self.auth.issue_local_grant('recover')
        self.assertTrue(self.auth.current(session['access_token'])['authenticated'])
        self.assert_error('INVALID_CREDENTIALS', self.auth.local_recover, grant, 'owner', 'wrong')
        limited = self.auth.local_recover(grant, 'owner', PASSWORD)
        self.assertNotIn('access_token', limited)
        self.assert_error('GRANT_INVALID', self.auth.local_recover, grant, 'owner', PASSWORD)
        self.assertEqual(before, self.sql('SELECT password_hash FROM hs_admin_account'))

    def test_credential_change_revokes_sessions_and_invalidates_pending_challenges(self):
        _, _, secret, session = self.enroll()
        challenge = self.auth.login('owner', PASSWORD)['challenge_token']
        self.auth.change(session['access_token'], PASSWORD, password=PASSWORD+' changed')
        self.assert_error('SESSION_REVOKED', self.auth.current, session['access_token'])
        self.assert_error('CHALLENGE_INVALID', self.auth.verify_login, challenge, pyotp.TOTP(secret).at(self.now()))

    def test_wrong_encryption_key_fails_closed(self):
        _, _, secret, _ = self.enroll()
        wrong = MFAAdminAuth(self.dsn, protection_key=Fernet.generate_key())
        challenge = wrong.login('owner', PASSWORD)['challenge_token']
        self.assert_error('MFA_KEY_UNAVAILABLE', wrong.verify_login, challenge, pyotp.TOTP(secret).at(self.now()))
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_session')[0][0], 1)

    def test_audit_contains_no_secrets(self):
        grant, challenge, secret, session = self.enroll()
        audit = str(self.sql('SELECT * FROM hs_admin_audit'))
        for sensitive in [PASSWORD, grant, challenge, secret, session['access_token'], *session['recovery_codes']]:
            self.assertNotIn(sensitive, audit)

    def test_http_private_routes_no_cache_origin_validation_and_no_public_register(self):
        grant = self.auth.issue_local_grant()
        body = dict(bootstrap_secret=grant, username='owner', password=PASSWORD)
        denied = self.client.post(PREFIX+'/bootstrap', json=body, headers={'Origin': 'https://evil.example'})
        self.assertEqual(denied.status_code, 403)
        bad = self.client.post(PREFIX+'/bootstrap', json={**body, 'extra': 'never echo secret'})
        self.assertEqual(bad.status_code, 422)
        self.assertNotIn(PASSWORD, bad.text)
        self.assertNotIn(grant, bad.text)
        response = self.client.post(PREFIX+'/bootstrap', json=body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        challenge = response.json()['challenge_token']
        headers = {'Authorization': 'Bearer '+challenge}
        self.assertEqual(self.client.get('/api/v1/p11/health', headers=headers).status_code, 401)
        self.assertEqual(self.client.post(PREFIX+'/register', json=body).status_code, 404)
        payload = self.client.post(PREFIX+'/mfa/enrollment/begin', json={'challenge_token': challenge}).json()
        result = self.client.post(PREFIX+'/mfa/enrollment/confirm', json={'challenge_token': challenge,
                                  'code': pyotp.TOTP(payload['manual_key']).at(self.now())})
        self.assertEqual(result.status_code, 200)
        headers = {'Authorization': 'Bearer '+result.json()['access_token']}
        self.assertEqual(self.client.get('/api/v1/p11/health', headers=headers).status_code, 200)
        self.assertEqual(self.client.post(PREFIX+'/logout', headers=headers).status_code, 204)
        self.assertEqual(self.client.get(PREFIX+'/session', headers=headers).status_code, 401)

    def test_technical_credentials_stay_separate(self):
        grant = self.auth.issue_local_grant()
        self.assert_error('TECHNICAL_CREDENTIAL_REUSE', self.auth.bootstrap, grant, 'owner', TECHNICAL[1])
        self.assert_error('TECHNICAL_CREDENTIAL_REUSE', self.auth.bootstrap, grant, TECHNICAL[0], PASSWORD)

    def test_http_login_two_stages_recovery_and_technical_ingest(self):
        _, _, secret, session = self.enroll()
        response = self.client.post(PREFIX+'/login', json=dict(username='owner', password=PASSWORD))
        self.assertEqual(response.status_code, 200)
        challenge = response.json()['challenge_token']
        self.assertNotIn('access_token', response.json())
        self.allow_next_totp()
        verified = self.client.post(PREFIX+'/mfa/verify', json=dict(challenge_token=challenge, code=pyotp.TOTP(secret).at(self.now())))
        self.assertEqual(verified.status_code, 200)
        full = verified.json()['access_token']
        self.assertEqual(self.client.get(PREFIX+'/session', headers={'Authorization': 'Bearer '+full}).status_code, 200)
        # Same technical Basic + service token, never human bearer for ingestion.
        record = dict(id='mfa-fixture-'+secrets.token_hex(8), source='trusted-service', data={})
        path = '/api/v1/p11/ingest/telemetry'
        self.assertEqual(self.client.post(path, json=record, headers={'Authorization': 'Bearer '+full}).status_code, 401)
        self.assertEqual(self.client.post(path, json=record, auth=TECHNICAL).status_code, 403)
        self.assertEqual(self.client.post(path, json=record, auth=TECHNICAL,
                         headers={'X-Service-Token': 'fixture-ingest-token'}).status_code, 201)
        challenge = self.client.post(PREFIX+'/login', json=dict(username='owner', password=PASSWORD)).json()['challenge_token']
        recovered = self.client.post(PREFIX+'/mfa/recover', json=dict(challenge_token=challenge, code=session['recovery_codes'][0]))
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json()['next_step'], 'enroll')
        self.assertNotIn('access_token', recovered.json())

    def test_concurrent_recovery_code_consumption(self):
        _, _, _, session = self.enroll()
        challenges = [self.auth.login('owner', PASSWORD)['challenge_token'] for _ in range(2)]
        def attempt(token):
            try:
                self.auth.verify_login(token, session['recovery_codes'][0], recovery=True)
                return 'OK'
            except AuthError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, challenges))
        self.assertCountEqual(results, ['OK', 'CHALLENGE_INVALID'])
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_recovery_code WHERE used_at IS NOT NULL')[0][0], 1)

    def test_concurrent_totp_accepts_exactly_once(self):
        _, _, secret, _ = self.enroll()
        self.allow_next_totp()
        challenges = [self.auth.login('owner', PASSWORD)['challenge_token'] for _ in range(2)]
        code = pyotp.TOTP(secret).at(self.now())
        def attempt(token):
            try:
                self.auth.verify_login(token, code)
                return 'OK'
            except AuthError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, challenges))
        self.assertCountEqual(results, ['OK', 'FACTOR_INVALID'])

    def test_confirm_invalidates_unused_operator_grants(self):
        _, challenge = self.bootstrap()
        payload = self.auth.begin_enrollment(challenge)
        stale = self.auth.issue_local_grant('recover')
        self.auth.confirm_enrollment(challenge, pyotp.TOTP(payload['manual_key']).at(self.now()))
        self.assert_error('GRANT_INVALID', self.auth.local_recover, stale, 'owner', PASSWORD)

    def test_pending_bootstrap_can_resume_without_public_or_operator_bypass(self):
        _, original = self.bootstrap()
        self.auth.begin_enrollment(original)
        self.auth.cancel_challenge(original)
        self.assert_error('CHALLENGE_INVALID', self.auth.begin_enrollment, original)
        resumed = self.auth.login('owner', PASSWORD)
        self.assertEqual(resumed['next_step'], 'enroll')
        payload = self.auth.begin_enrollment(resumed['challenge_token'])
        self.assertIn('manual_key', payload)
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_session')[0][0], 0)

    def test_audit_failure_rolls_back_activation(self):
        _, challenge = self.bootstrap()
        payload = self.auth.begin_enrollment(challenge)
        self.sql("CREATE FUNCTION hs_mfa_fixture_fail() RETURNS trigger LANGUAGE plpgsql AS $$ "
                 "BEGIN RAISE EXCEPTION 'fixture audit failure'; END $$")
        self.sql('CREATE TRIGGER hs_mfa_fixture_failure BEFORE INSERT ON hs_admin_audit '
                 'FOR EACH ROW EXECUTE FUNCTION hs_mfa_fixture_fail()')
        try:
            self.assert_error('AUTH_UNAVAILABLE', self.auth.confirm_enrollment, challenge, pyotp.TOTP(payload['manual_key']).at(self.now()))
        finally:
            self.sql('DROP TRIGGER hs_mfa_fixture_failure ON hs_admin_audit')
            self.sql('DROP FUNCTION hs_mfa_fixture_fail()')
        self.assertIsNone(self.sql('SELECT enabled_at FROM hs_admin_mfa')[0][0])
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_session')[0][0], 0)
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_recovery_code')[0][0], 0)


if __name__ == '__main__':
    unittest.main()
