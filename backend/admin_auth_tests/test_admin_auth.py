"""Real isolated PostgreSQL required. No SQLite or production DSN fallback."""
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/domain'), str(ROOT/'genai')]

import psycopg
from fastapi import Depends
from fastapi.testclient import TestClient

from admin_auth import AdminAuth, AuthError, install_admin_auth
from admin_auth.passwords import password_hash, verify
from admin_auth.service import token_hash
from delivery.projections import create_app, Record
from delivery.postgres_store import PostgresStore
from delivery.control_store import PostgresControls
from delivery.controls import Controls
from delivery.routes import install_controls
from harpia.p11 import install_deterministic_harpia

PASSWORD = 'isolated correct horse battery staple'
TECHNICAL = ('technical-writer', 'separate-technical-only')
TOKEN = 'technical-projection-fixture-only'
PREFIX = '/api/v1/admin-auth'


class PasswordTests(unittest.TestCase):
    def test_password_length_boundaries_in_service_and_api(self):
        from admin_auth.service import valid_password
        from admin_auth.api import PasswordChange
        from pydantic import ValidationError
        for size in (8, 128):
            value = 'x' * size
            self.assertEqual(valid_password(value), value)
            self.assertEqual(PasswordChange(current_password='existing', new_password=value).new_password.get_secret_value(), value)
        for size in (7, 129):
            with self.assertRaises(AuthError):
                valid_password('x' * size)
            with self.assertRaises(ValidationError):
                PasswordChange(current_password='existing', new_password='x' * size)

    def test_scrypt_salt_unicode_and_wrong_password(self):
        first, second = password_hash(PASSWORD+'ç'), password_hash(PASSWORD+'ç')
        self.assertNotEqual(first, second)
        self.assertNotIn(PASSWORD, first)
        self.assertTrue(verify(PASSWORD+'ç', first))
        self.assertFalse(verify('incorrect', first))


@unittest.skipUnless(os.getenv('ADMIN_AUTH_TEST_DATABASE_URL'), 'Isolated PostgreSQL not configured')
class PostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['ADMIN_AUTH_TEST_DATABASE_URL']
        # Prevent accidentally invoking destructive fixture reset against a normal DB.
        with psycopg.connect(cls.dsn) as conn:
            if conn.execute('SELECT current_database()').fetchone()[0] != 'auth_fixture':
                raise RuntimeError('Tests require dedicated disposable auth_fixture database')
            conn.execute((ROOT/'backend/delivery/001_local.sql').read_text())
            if conn.execute("SELECT to_regclass('hs_admin_schema_version')").fetchone()[0] is None:
                conn.execute((ROOT/'backend/admin_auth/001_admin_auth.sql').read_text())
        cls.auth = AdminAuth(cls.dsn, technical_credentials=[TECHNICAL])

    def sql(self, query, params=()):
        with psycopg.connect(self.dsn) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall() if cursor.description else None

    def setUp(self):
        self.sql('TRUNCATE hs_admin_session,hs_admin_account,hs_admin_audit')
        self.sql("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity'")
        self.auth.provision('owner', PASSWORD)
        self.store = PostgresStore(self.dsn)
        self.app = create_app(self.store, username=TECHNICAL[0], password=TECHNICAL[1], service_token=TOKEN)
        install_deterministic_harpia(self.app, self.store)
        install_controls(self.app, Controls(PostgresControls(self.dsn)))
        self.require = install_admin_auth(self.app, self.auth, allowed_origins=['https://dashboard.example'])
        self.client = TestClient(self.app)

    def login(self, username='owner', password=PASSWORD):
        return self.client.post(PREFIX+'/login', json=dict(username=username,password=password))

    def headers(self):
        return {'Authorization': 'Bearer '+self.login().json()['access_token']}

    def test_provision_is_singleton_hashed_and_not_public(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.provision('another', PASSWORD)
        self.assertEqual(ctx.exception.code, 'ALREADY_PROVISIONED')
        self.assertEqual(len(self.sql('SELECT * FROM hs_admin_account')), 1)
        self.assertNotIn(PASSWORD, str(self.sql('SELECT password_hash FROM hs_admin_account')))
        self.assertEqual(self.client.post(PREFIX+'/provision', json={}).status_code, 404)
        self.assertEqual(self.client.post(PREFIX+'/register', json={}).status_code, 404)

    def test_login_invalid_valid_and_no_account_are_generic(self):
        invalid = self.login(password='wrong')
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.json(), self.login(username='unknown').json())
        ok = self.login()
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.headers['cache-control'], 'no-store')
        self.assertNotIn('set-cookie', ok.headers)
        token = ok.json()['access_token']
        saved = self.sql('SELECT token_hash FROM hs_admin_session')[0][0]
        self.assertEqual(saved, token_hash(token))
        self.assertNotEqual(saved, token)
        self.sql('TRUNCATE hs_admin_session,hs_admin_account')
        self.assertEqual(self.login().json(), invalid.json())

    def test_session_expiration_idle_absolute_invalid_and_revocation(self):
        for update in ["expires_at=clock_timestamp()-interval '1 second'",
                       "last_seen_at=clock_timestamp()-interval '31 minutes'",
                       'revoked_at=clock_timestamp()']:
            headers = self.headers()
            self.sql('UPDATE hs_admin_session SET '+update)
            r = self.client.get(PREFIX+'/session', headers=headers)
            self.assertEqual(r.status_code, 401)
            self.assertIn(r.json()['error']['code'], ['SESSION_EXPIRED','SESSION_REVOKED'])
        self.assertEqual(self.client.get(PREFIX+'/session',headers={'Authorization':'Bearer '+'a'*43}).json()['error']['code'], 'SESSION_INVALID')
        self.assertEqual(self.client.get(PREFIX+'/session').json()['error']['code'], 'AUTH_REQUIRED')

    def test_restart_persistence_logout_and_audit(self):
        headers = self.headers()
        token = headers['Authorization'].split()[1]
        self.assertEqual(AdminAuth(self.dsn).current(token)['username'], 'owner')
        state = self.client.get(PREFIX+'/session', headers=headers).json()
        self.assertFalse(state['mfa_available'])
        self.assertFalse(state['email_recovery_available'])
        r = self.client.post(PREFIX+'/logout', headers=headers)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.client.get(PREFIX+'/session',headers=headers).status_code, 401)
        self.assertIn(('LOGOUT','OK'), self.sql('SELECT event,result FROM hs_admin_audit'))

    def test_password_change_reauth_revokes_all_sessions(self):
        first, second = self.headers(), self.headers()
        r = self.client.put(PREFIX+'/password',headers=first,
                            json=dict(current_password='wrong',new_password='a fresh independent password'))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['error']['code'], 'REAUTHENTICATION_REQUIRED')
        self.assertEqual(self.client.get(PREFIX+'/session',headers=first).status_code, 200)
        r = self.client.put(PREFIX+'/password',headers=first,
                            json=dict(current_password=PASSWORD,new_password='a fresh independent password'))
        self.assertEqual(r.status_code, 200)
        for headers in [first,second]:
            self.assertEqual(self.client.get(PREFIX+'/session',headers=headers).status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login(password='a fresh independent password').status_code, 200)

    def test_username_change_reauth_and_revocation(self):
        headers = self.headers()
        r = self.client.put(PREFIX+'/username',headers=headers,json=dict(current_password='wrong',new_username='new.owner'))
        self.assertEqual(r.status_code, 403)
        r = self.client.put(PREFIX+'/username',headers=headers,json=dict(current_password=PASSWORD,new_username='new.owner'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(PREFIX+'/session',headers=headers).status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login(username='new.owner').status_code, 200)

    def test_throttle_global_bounded_persisted_and_reauth(self):
        headers = self.headers()
        for n in range(5):
            self.assertEqual(self.login(username='invented-'+str(n), password='bad').status_code, 401)
        limited = self.login()
        self.assertEqual(limited.status_code, 429)
        self.assertGreaterEqual(int(limited.headers['retry-after']), 1)
        self.assertLessEqual(int(limited.headers['retry-after']), 60)
        # Throttling must not disable an existing valid session.
        self.assertEqual(self.client.get(PREFIX+'/session',headers=headers).status_code, 200)
        self.assertEqual(self.client.put(PREFIX+'/username',headers=headers,
                          json=dict(current_password=PASSWORD,new_username='new')).status_code, 429)
        with self.assertRaises(AuthError) as ctx:
            AdminAuth(self.dsn).login('owner',PASSWORD)
        self.assertEqual(ctx.exception.status, 429)
        self.sql("UPDATE hs_admin_throttle SET blocked_until=clock_timestamp()-interval '1 second'")
        self.assertEqual(self.login().status_code, 200)

    def test_p11_harpia_controls_and_technical_separation(self):
        headers = self.headers()
        for path in ['/api/v1/p11/health','/api/v1/p11/telemetry','/api/v1/security/settings/mode/default',
                     '/api/v1/security/audit','/api/v1/p11/explain/absent']:
            self.assertEqual(self.client.get(path).status_code, 401)
            self.assertEqual(self.client.get(path,auth=TECHNICAL).status_code, 401)
        self.assertEqual(self.login(*TECHNICAL).status_code, 401)
        health = self.client.get('/api/v1/p11/health', headers=headers).json()
        self.assertFalse(health['harpia']['generation_enabled'])
        self.assertEqual(self.client.get('/api/v1/security/settings/mode/default',headers=headers).status_code, 200)
        self.store.insert('telemetry',Record(id='auth-fixture-telemetry',source='synthetic',
                                           data={'device_id':'poste2','temperatura':25}))
        rows = self.client.get('/api/v1/p11/telemetry',headers=headers).json()
        self.assertTrue(any(row['data'].get('device_id') == 'poste2' for row in rows))
        payload = dict(id='auth-service-record',revision=1,source='trusted-service',data={'device_id':'poste2'})
        path = '/api/v1/p11/ingest/telemetry'
        self.assertEqual(self.client.post(path,auth=TECHNICAL,json=payload).status_code, 403)
        self.assertEqual(self.client.post(path,headers={**headers,'X-Service-Token':TOKEN},json=payload).status_code, 401)
        response = self.client.post(path,auth=TECHNICAL,headers={'X-Service-Token':TOKEN},json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.post(path,auth=TECHNICAL,headers={'X-Service-Token':TOKEN},json=payload).json()['created'], False)
        self.assertEqual(self.client.get('/api/v1/p11/telemetry',headers={'X-Service-Token':TOKEN}).status_code, 401)

    def test_actual_deterministic_explanation_preserves_contract(self):
        self.store.insert('incident', Record(id='auth-fixture-incident',source='synthetic',
                                            data={'incident_id':'auth-fixture-incident','revision':1,'status':'OPEN'}))
        result = self.client.get('/api/v1/p11/explain/auth-fixture-incident',headers=self.headers())
        self.assertEqual(result.status_code, 200)
        self.assertIn('limitations', result.json())

    def test_origin_and_validation_do_not_disclose_secrets(self):
        headers = self.headers()
        r = self.client.get(PREFIX+'/session',headers={**headers,'Origin':'https://evil.example'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.post(PREFIX+'/login',headers={'Origin':'https://evil.example'},
                         json=dict(username='owner',password=PASSWORD)).status_code, 403)
        r = self.client.post(PREFIX+'/login',json=dict(username='owner',password=PASSWORD,extra=PASSWORD))
        self.assertEqual(r.status_code, 422)
        self.assertNotIn(PASSWORD, r.text)
        r = self.client.put(PREFIX+'/password',headers=headers,json=dict(current_password=PASSWORD,new_password='short'))
        self.assertEqual(r.status_code, 422)
        audit = str(self.sql('SELECT * FROM hs_admin_audit'))
        self.assertNotIn(PASSWORD, audit)
        self.assertNotIn(headers['Authorization'].split()[1], audit)

    def test_future_route_dependency_and_double_install_refusal(self):
        @self.app.get('/future-private')
        def future(actor=Depends(self.require)):
            return {'actor':actor}
        self.assertEqual(self.client.get('/future-private',auth=TECHNICAL).status_code, 401)
        self.assertEqual(self.client.get('/future-private',headers=self.headers()).json(), {'actor':'owner'})
        with self.assertRaises(RuntimeError):
            install_admin_auth(self.app,self.auth,allowed_origins=['https://dashboard.example'])

    def test_concurrent_provision_and_credential_updates(self):
        self.sql('TRUNCATE hs_admin_session,hs_admin_account')
        def provision(n):
            try:
                self.auth.provision('owner',PASSWORD)
                return 'OK'
            except AuthError as exc:
                return exc.code
        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(provision,[1,2])), ['OK','ALREADY_PROVISIONED'])
        headers = self.headers()
        token = headers['Authorization'].split()[1]
        def change(n):
            try:
                self.auth.change(token,PASSWORD,username='new-'+str(n))
                return 'OK'
            except AuthError as exc:
                return exc.code
        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(change,[1,2])), ['OK','SESSION_REVOKED'])

    def test_unavailable_database_is_safe_503(self):
        broken = AdminAuth('host=127.0.0.1 port=1 dbname=auth_fixture user=fixture connect_timeout=1')
        app = create_app(self.store,username=TECHNICAL[0],password=TECHNICAL[1])
        install_admin_auth(app,broken,allowed_origins=['https://dashboard.example'])
        r = TestClient(app).post(PREFIX+'/login',json=dict(username='owner',password=PASSWORD))
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json(), {'error': {'code':'AUTH_UNAVAILABLE'}})

    def test_uninstalled_p11_remains_unchanged(self):
        original = TestClient(create_app(self.store,username=TECHNICAL[0],password=TECHNICAL[1]))
        self.assertEqual(original.get('/api/v1/p11/telemetry',auth=TECHNICAL).status_code, 200)
        self.assertEqual(original.post(PREFIX+'/login',json={}).status_code, 404)

    def test_technical_credential_reuse_rejected(self):
        for change in [dict(username=TECHNICAL[0]),dict(password=TECHNICAL[1])]:
            with self.assertRaises(AuthError) as ctx:
                self.auth.separate_credentials(**change)
            self.assertEqual(ctx.exception.code, 'TECHNICAL_CREDENTIAL_REUSE')
        headers = self.headers()
        r = self.client.put(PREFIX+'/username',headers=headers,
                            json=dict(current_password=PASSWORD,new_username=TECHNICAL[0]))
        self.assertEqual(r.status_code, 422)
        r = self.client.put(PREFIX+'/password',headers=headers,
                            json=dict(current_password=PASSWORD,new_password=TECHNICAL[1]))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.client.get(PREFIX+'/session',headers=headers).status_code, 200)

    def test_oversized_body_and_secret_validation_are_private(self):
        r = self.client.post(PREFIX+'/login',content='x'*4097,headers={'Content-Type':'application/json'})
        self.assertEqual(r.status_code, 413)
        self.assertNotIn('xxx', r.text)
        for password in ['', 'x'*129, {'secret':PASSWORD}]:
            r = self.client.post(PREFIX+'/login',json=dict(username='owner',password=password))
            self.assertEqual(r.status_code, 422)
            self.assertNotIn(PASSWORD, r.text)

    def test_sql_rerun_refuses_without_touching_existing_account(self):
        before = self.sql('SELECT username,password_hash,credential_revision FROM hs_admin_account')
        with self.assertRaises(psycopg.errors.DuplicateTable):
            with psycopg.connect(self.dsn) as conn:
                conn.execute((ROOT/'backend/admin_auth/001_admin_auth.sql').read_text())
        self.assertEqual(self.sql('SELECT username,password_hash,credential_revision FROM hs_admin_account'),before)

    def test_missing_auth_migration_returns_503_without_leaking_sql(self):
        # Explicit isolated schema with no auth tables; never a second operational database.
        isolated = AdminAuth(self.dsn+'?options=-csearch_path%3Dpg_catalog' if '?' not in self.dsn else self.dsn)
        if '?' in self.dsn:
            self.skipTest('Test expects a fixture URL without query')
        with self.assertRaises(AuthError) as ctx:
            isolated.current('a'*43)
        self.assertEqual(ctx.exception.code,'AUTH_UNAVAILABLE')

    def test_corrupt_password_hash_is_unavailable_not_invalid_login(self):
        self.sql("UPDATE hs_admin_account SET password_hash='unsupported-version'")
        r = self.login()
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json(), {'error': {'code':'AUTH_UNAVAILABLE'}})
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_session')[0][0], 0)

    def test_audit_failure_rolls_back_credentials_and_session_revocation(self):
        headers = self.headers()
        self.sql("CREATE FUNCTION hs_auth_fixture_fail() RETURNS trigger LANGUAGE plpgsql AS $$ "
                 "BEGIN RAISE EXCEPTION 'isolated audit fixture failure'; END $$")
        try:
            self.sql('CREATE TRIGGER hs_auth_fixture_failure BEFORE INSERT ON hs_admin_audit '
                     'FOR EACH ROW EXECUTE FUNCTION hs_auth_fixture_fail()')
            r = self.client.put(PREFIX+'/username',headers=headers,
                                json=dict(current_password=PASSWORD,new_username='must-rollback'))
            self.assertEqual(r.status_code, 503)
            self.assertEqual(self.sql('SELECT username,credential_revision FROM hs_admin_account'), [('owner',1)])
            self.assertEqual(self.client.get(PREFIX+'/session',headers=headers).status_code, 200)
        finally:
            self.sql('DROP TRIGGER IF EXISTS hs_auth_fixture_failure ON hs_admin_audit')
            self.sql('DROP FUNCTION hs_auth_fixture_fail()')


if __name__ == '__main__':
    unittest.main()
