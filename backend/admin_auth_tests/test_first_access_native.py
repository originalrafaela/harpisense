"""Native PostgreSQL + authenticated HTTP. Never print enrollment/code payloads."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/p) for p in ('backend','backend/domain','genai','backend/delivery_tests')]
import httpx
import psycopg
import pyotp
import uvicorn
from admin_auth.mfa import MFAAdminAuth
from admin_auth.service import AuthError,token_hash
import test_incident_dossier as fixture

PREFIX='/api/v1/admin-auth'


class FirstAccessNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=fixture.IncidentDossierTests
        cls.fixture.setUpClass()
        cls.dsn=cls.fixture.state['dsn']
        cls.key=Path(cls.fixture.state['key_file']).read_bytes()
        cls.auth=cls.fixture.server.config.app.state.admin_auth

    @classmethod
    def tearDownClass(cls):cls.fixture.tearDownClass()

    def sql(self,query,params=()):
        with psycopg.connect(self.dsn) as conn:
            cur=conn.execute(query,params)
            return cur.fetchall() if cur.description else None

    def setUp(self):
        self.sql('TRUNCATE hs_admin_first_access,hs_admin_password_reset_code,hs_admin_mfa_challenge, '
            'hs_admin_recovery_code,hs_admin_mfa,hs_admin_local_grant,hs_admin_session,hs_admin_account,hs_admin_audit')
        self.sql("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity'")
        self.username='owner-'+secrets.token_hex(4)
        self.password=secrets.token_urlsafe(30)
        self.client=httpx.Client(base_url=self.fixture.url,trust_env=False)
        grant=self.auth.issue_local_grant()
        response=self.client.post(PREFIX+'/bootstrap',json={'bootstrap_secret':grant,'username':self.username,'password':self.password})
        self.assertEqual(response.status_code,200)
        challenge=response.json()['challenge_token']
        begin=self.client.post(PREFIX+'/mfa/enrollment/begin',json={'challenge_token':challenge})
        self.assertEqual(begin.status_code,200)
        enrollment=begin.json();self.secret=enrollment['manual_key']
        self.assertTrue('<svg' in enrollment['qr_svg'],'QR must be generated locally')
        response=self.client.post(PREFIX+'/mfa/enrollment/confirm',json={'challenge_token':challenge,
            'code':pyotp.TOTP(self.secret).at(self.now())})
        self.assertEqual(response.status_code,200)
        self.issued=response.json()
        self.token=self.issued['access_token']
        self.headers={'Authorization':'Bearer '+self.token}

    def tearDown(self):self.client.close()
    def now(self):return int(self.sql('SELECT extract(epoch FROM clock_timestamp())')[0][0])
    def next_totp(self):
        # Exercise the real clock/replay policy. Never rewind last_step.
        deadline=time.monotonic()+35
        while self.now()//30<=self.sql('SELECT last_step FROM hs_admin_mfa')[0][0]:
            if time.monotonic()>deadline:raise RuntimeError('TOTP_CLOCK_DID_NOT_ADVANCE')
            time.sleep(.1)
        return pyotp.TOTP(self.secret).at(self.now())
    def state(self):
        response=self.client.get(PREFIX+'/first-access',headers=self.headers)
        self.assertEqual(response.status_code,200)
        return response.json()
    def confirm(self,generation=1,**extra):
        return self.client.post(PREFIX+'/first-access/confirm',headers=self.headers,
            json={'password_reset_generation':generation,**extra})
    def reset(self,code,password=None):
        return self.client.post(PREFIX+'/password-reset/confirm',json={'username':self.username,
            'code':code,'new_password':password or secrets.token_urlsafe(30)})

    def test_issuance_hashes_purposes_and_no_secret_readback_or_audit(self):
        self.assertEqual(self.issued['username'],self.username)
        self.assertEqual(self.issued['first_access']['status'],'pending')
        self.assertEqual(len(self.issued['password_reset_codes']),10)
        self.assertEqual(len(self.issued['recovery_codes']),10)
        self.assertTrue(set(self.issued['password_reset_codes']).isdisjoint(self.issued['recovery_codes']))
        self.assertEqual(self.sql('SELECT DISTINCT purpose FROM hs_admin_password_reset_code'),[('password_reset',)])
        self.assertEqual(self.sql('SELECT DISTINCT purpose FROM hs_admin_recovery_code'),[('authenticator_recovery',)])
        persisted=str(self.sql('SELECT * FROM hs_admin_password_reset_code')+self.sql('SELECT * FROM hs_admin_recovery_code')+
                      self.sql('SELECT * FROM hs_admin_first_access')+self.sql('SELECT * FROM hs_admin_audit'))
        secrets_to_check=[*self.issued['password_reset_codes'],*self.issued['recovery_codes'],self.secret,self.password,self.token]
        self.assertTrue(all(value not in persisted for value in secrets_to_check),'Secret material must never be persisted in code/state/audit rows')
        response=self.client.get(PREFIX+'/first-access',headers=self.headers)
        self.assertTrue(all(value not in response.text for value in secrets_to_check),'Status must not recover original material')

    def test_confirmation_persists_idempotently_and_login_does_not_reissue(self):
        first=self.confirm();self.assertEqual(first.status_code,200)
        again=self.confirm();self.assertEqual(again.status_code,200)
        self.assertEqual(first.json(),again.json())
        restarted=MFAAdminAuth(self.dsn,protection_key=self.key)
        self.assertEqual(restarted.first_access_status(self.token)['first_access']['status'],'completed')
        self.auth.logout(self.token)
        challenge=restarted.login(self.username,self.password)
        self.assertTrue('access_token' not in challenge)
        logged=restarted.verify_login(challenge['challenge_token'],self.next_totp())
        self.assertEqual(logged['first_access']['status'],'completed')
        self.assertTrue('password_reset_codes' not in logged and 'recovery_codes' not in logged)

    def test_reset_code_consumed_once_concurrently_revokes_sessions_and_keeps_totp(self):
        self.assertEqual(self.confirm().status_code,200)
        before=self.sql('SELECT secret_cipher,required,enabled_at FROM hs_admin_mfa')
        code=self.issued['password_reset_codes'][0];new_password=secrets.token_urlsafe(30)
        restarted=MFAAdminAuth(self.dsn,protection_key=self.key)
        def attempt(_):
            try:restarted.reset_password(self.username,code,new_password);return 'OK'
            except AuthError as error:return error.code
        with ThreadPoolExecutor(2) as pool:outcomes=list(pool.map(attempt,range(2)))
        self.assertCountEqual(outcomes,['OK','PASSWORD_RESET_INVALID'])
        self.assertEqual(self.reset(code,new_password).status_code,401)
        self.assertEqual(self.sql('SELECT secret_cipher,required,enabled_at FROM hs_admin_mfa'),before)
        self.assertEqual(self.client.get(PREFIX+'/session',headers=self.headers).status_code,401)
        self.assertEqual(self.client.post(PREFIX+'/login',json={'username':self.username,'password':self.password}).status_code,401)
        challenge=self.client.post(PREFIX+'/login',json={'username':self.username,'password':new_password})
        self.assertEqual(challenge.status_code,200)
        self.assertTrue('access_token' not in challenge.json())
        verified=self.client.post(PREFIX+'/mfa/verify',json={'challenge_token':challenge.json()['challenge_token'],'code':self.next_totp()})
        self.assertEqual(verified.status_code,200)
        self.assertEqual(verified.json()['first_access']['status'],'completed')

    def test_two_purposes_cannot_substitute_for_each_other(self):
        self.assertEqual(self.reset(self.issued['recovery_codes'][0]).status_code,401)
        challenge=self.auth.login(self.username,self.password)['challenge_token']
        response=self.client.post(PREFIX+'/mfa/recover',json={'challenge_token':challenge,
            'code':self.issued['password_reset_codes'][0]})
        self.assertEqual(response.status_code,401)
        response=self.client.post(PREFIX+'/mfa/recover',json={'challenge_token':challenge,
            'code':self.issued['recovery_codes'][0]})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['next_step'],'enroll')
        self.assertTrue('access_token' not in response.json())

    def test_reissue_revokes_previous_generation_and_reopens_pending(self):
        self.assertEqual(self.confirm().status_code,200)
        response=self.client.post(PREFIX+'/first-access/codes',headers=self.headers,
            json={'current_password':self.password,'code':self.next_totp()})
        self.assertEqual(response.status_code,200)
        result=response.json()
        self.assertEqual(len(result['recovery_codes']),10)
        self.assertEqual(result['first_access']['password_reset_generation'],2)
        self.assertEqual(result['first_access']['status'],'pending')
        self.assertEqual(self.confirm(1).status_code,409)
        self.assertEqual(self.reset(self.issued['password_reset_codes'][0]).status_code,401)
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_password_reset_code WHERE revoked_at IS NOT NULL')[0][0],10)
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_recovery_code WHERE revoked_at IS NULL')[0][0],10)
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_recovery_code WHERE revoked_at IS NOT NULL')[0][0],10)
        self.assertTrue(set(result['recovery_codes']).isdisjoint(self.issued['recovery_codes']))
        challenge=self.auth.login(self.username,self.password)['challenge_token']
        recovery=self.client.post(PREFIX+'/mfa/recover',json={'challenge_token':challenge,
            'code':self.issued['recovery_codes'][0]})
        self.assertEqual(recovery.status_code,401)
        self.assertEqual(self.confirm(2).status_code,200)
        self.assertEqual(self.reset(result['password_reset_codes'][0]).status_code,200)

    def test_confirmation_is_scoped_to_authenticated_account_not_supplied_id(self):
        self.assertEqual(self.confirm(account_id=2).status_code,422)
        self.assertEqual(self.client.post(PREFIX+'/first-access/confirm',json={'password_reset_generation':1}).status_code,401)
        other_schema='other_account_'+secrets.token_hex(4)
        self.sql('CREATE SCHEMA '+other_schema)
        other_dsn=psycopg.conninfo.make_conninfo(self.dsn,options='-c search_path='+other_schema)
        with psycopg.connect(other_dsn) as conn:
            for name in ('001_admin_auth.sql','002_admin_mfa.sql','003_password_reset.sql','004_first_access.sql'):
                conn.execute((ROOT/'backend/admin_auth'/name).read_text(encoding='utf-8'))
        other=MFAAdminAuth(other_dsn,protection_key=self.key)
        challenge=other.bootstrap(other.issue_local_grant(),'other-owner',secrets.token_urlsafe(30))['challenge_token']
        enrollment=other.begin_enrollment(challenge)
        other_session=other.confirm_enrollment(challenge,pyotp.TOTP(enrollment['manual_key']).at(self.now()))
        try:
            other.confirm_first_access(self.token,1)
            accepted=True
        except AuthError:accepted=False
        self.assertFalse(accepted,'A different account session must not confirm this account')
        self.assertEqual(self.confirm().status_code,200)
        self.assertEqual(other.first_access_status(other_session['access_token'])['first_access']['status'],'pending')

    def test_confirmation_racing_reissue_never_confirms_old_generation_as_current(self):
        code=self.next_totp()
        def acknowledge():
            try:self.auth.confirm_first_access(self.token,1);return 'OK'
            except AuthError as error:return error.code
        def reissue():return self.auth.regenerate_password_reset_codes(self.token,self.password,code)['first_access']['password_reset_generation']
        with ThreadPoolExecutor(2) as pool:
            ack=pool.submit(acknowledge);issue=pool.submit(reissue)
            self.assertEqual(issue.result(),2)
            self.assertTrue(ack.result() in ('OK','FIRST_ACCESS_GENERATION_CONFLICT'))
        self.assertEqual(self.state()['first_access']['status'],'pending')
        self.assertEqual(self.state()['first_access']['password_reset_generation'],2)

    def test_migration_replay_preserves_completion_and_emission_is_authenticated(self):
        self.assertEqual(self.confirm().status_code,200)
        before=self.state()
        with psycopg.connect(self.dsn) as conn:
            conn.execute((ROOT/'backend/admin_auth/004_first_access.sql').read_text(encoding='utf-8'))
        self.assertEqual(self.state(),before)
        for path in ('/first-access/codes','/password-reset/codes'):
            response=self.client.post(PREFIX+path,json={'current_password':self.password,'code':'000000'})
            self.assertEqual(response.status_code,401)

    def test_http_restart_preserves_saved_codes_and_reset_still_requires_totp(self):
        from admin_auth.candidate import install_candidate_admin_auth
        from delivery.app import build_app
        self.assertEqual(self.confirm().status_code,200)
        before=self.state()['first_access']
        mfa_before=self.sql('SELECT secret_cipher,required,enabled_at FROM hs_admin_mfa')
        self.client.close()
        self.fixture.client.close()
        self.fixture.server.should_exit=True
        self.fixture.thread.join(10)
        self.assertFalse(self.fixture.thread.is_alive(),'Old HTTP server must stop before restart')
        self.fixture.sock.close()
        self.fixture.sock=socket.socket();self.fixture.sock.bind(('127.0.0.1',0))
        self.fixture.url='http://127.0.0.1:'+str(self.fixture.sock.getsockname()[1])
        app=build_app()
        install_candidate_admin_auth(app,self.dsn,protection_key=self.key,allowed_origins=[self.fixture.url])
        type(self).auth=app.state.admin_auth
        self.fixture.server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
        self.fixture.thread=threading.Thread(target=self.fixture.server.run,kwargs={'sockets':[self.fixture.sock]},daemon=True)
        self.fixture.thread.start()
        deadline=time.monotonic()+15
        while not self.fixture.server.started and time.monotonic()<deadline:time.sleep(.05)
        self.assertTrue(self.fixture.server.started,'New HTTP server must start with existing PostgreSQL state')
        self.client=httpx.Client(base_url=self.fixture.url,trust_env=False)
        self.assertEqual(self.state()['first_access'],before)
        new_password=secrets.token_urlsafe(30)
        response=self.reset(self.issued['password_reset_codes'][0],new_password)
        self.assertEqual(response.status_code,200)
        self.assertTrue('access_token' not in response.json())
        self.assertEqual(self.sql('SELECT secret_cipher,required,enabled_at FROM hs_admin_mfa'),mfa_before)
        self.assertEqual(self.client.get(PREFIX+'/session',headers=self.headers).status_code,401)
        challenge=self.client.post(PREFIX+'/login',json={'username':self.username,'password':new_password})
        self.assertEqual(challenge.status_code,200)
        self.assertEqual(challenge.json()['next_step'],'login')
        self.assertTrue('access_token' not in challenge.json())

    def test_first_access_requires_full_mfa_session_even_for_legacy_account(self):
        from admin_auth.service import AdminAuth
        self.sql('UPDATE hs_admin_mfa SET required=false,enabled_at=NULL')
        legacy=AdminAuth(self.dsn).login(self.username,self.password)
        headers={'Authorization':'Bearer '+legacy['access_token']}
        self.assertEqual(self.client.get(PREFIX+'/first-access',headers=headers).status_code,403)
        self.assertEqual(self.client.post(PREFIX+'/first-access/confirm',headers=headers,
            json={'password_reset_generation':1}).status_code,403)
        self.assertEqual(self.sql('SELECT completed_at FROM hs_admin_first_access')[0][0],None)

    def test_audit_failure_rolls_back_reissue_revocation_and_generation(self):
        before=self.state()
        code=self.next_totp()
        self.sql("CREATE FUNCTION hs_first_access_test_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                 "BEGIN RAISE EXCEPTION 'fixture audit failure'; END $$")
        self.sql('CREATE TRIGGER hs_first_access_test_failure BEFORE INSERT ON hs_admin_audit '
                 'FOR EACH ROW EXECUTE FUNCTION hs_first_access_test_failure()')
        try:
            response=self.client.post(PREFIX+'/first-access/codes',headers=self.headers,
                json={'current_password':self.password,'code':code})
            self.assertEqual(response.status_code,503)
            self.assertTrue('password_reset_codes' not in response.json())
        finally:
            self.sql('DROP TRIGGER hs_first_access_test_failure ON hs_admin_audit')
            self.sql('DROP FUNCTION hs_first_access_test_failure()')
        self.assertEqual(self.state(),before)
        self.assertEqual(self.sql('SELECT count(*) FROM hs_admin_password_reset_code WHERE revoked_at IS NOT NULL')[0][0],0)
        self.assertEqual(self.reset(self.issued['password_reset_codes'][0]).status_code,200)


if __name__=='__main__':unittest.main()
