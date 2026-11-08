import base64
import hashlib
import json
import secrets
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pyotp
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from admin_auth.candidate import install_candidate_admin_auth
from admin_auth.mfa import MFAAdminAuth
from admin_auth.service import AuthError, token_hash
from admin_auth.passwords import password_hash, verify
from license_issuer import envelopes as wire
from license_issuer.service import LicenseIssuer, IssuerError, PROOF_FIELDS, CHALLENGE_FIELDS
from license_issuer.api import create_issuer_app

PASSWORD = 'human fixture password 2026'
NEW_PASSWORD = 'replacement fixture password 2026'
PREFIX = '/api/v1/admin-auth'


def query(dsn, statement, params=()):
    with psycopg.connect(dsn) as conn:
        result = conn.execute(statement, params)
        return result.fetchall() if result.description else []


def caught(action):
    try:
        return action()
    except (AuthError, IssuerError) as exc:
        return exc.code


def race(dsn, lock_statement, actions, params=()):
    """Observe both real server connections waiting on locks before releasing."""
    barrier = threading.Barrier(len(actions))
    def work(action):
        barrier.wait(timeout=10)
        return caught(action)
    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        with psycopg.connect(dsn) as blocker:
            blocker.execute(lock_statement, params)
            futures = [pool.submit(work, action) for action in actions]
            deadline = time.monotonic() + 8
            observed = 0
            while time.monotonic() < deadline:
                with psycopg.connect(dsn) as monitor:
                    observed = monitor.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name=current_setting('application_name') AND wait_event_type='Lock'").fetchone()[0]
                if observed >= len(actions):
                    break
                time.sleep(.02)
            blocker.commit()
        results = [future.result(timeout=15) for future in futures]
    assert observed >= len(actions), 'Did not observe simultaneous PostgreSQL lock contention'
    return results


def make_auth(dsn):
    key = Fernet.generate_key()
    auth = MFAAdminAuth(dsn, protection_key=key, technical_credentials=[('gateway-fixture','gateway-password-fixture')])
    auth.fixture_protection_key = key
    return auth


def identity():
    return dict(installation_id=str(uuid.uuid4()), license_id=str(uuid.uuid4()))


def code_now(dsn, secret):
    seconds = query(dsn, 'SELECT extract(epoch FROM clock_timestamp())')[0][0]
    return pyotp.TOTP(secret).at(int(seconds))


def fresh_step(dsn):
    # Test setup only: avoid a 30-second sleep between independent route assertions.
    query(dsn, 'UPDATE hs_admin_mfa SET last_step=-1')


def enrolled(dsn):
    auth = make_auth(dsn)
    binding = identity()
    challenge = auth.bootstrap(binding, 'owner', PASSWORD)
    details = auth.begin_enrollment(challenge['challenge_token'])
    secret = details['manual_key']
    session = auth.confirm_enrollment(challenge['challenge_token'], code_now(dsn, secret))
    assert 'recovery_codes' not in session and 'password_reset_codes' not in session
    return auth, secret, session['access_token'], binding


def issuer_and_machine(dsn):
    issuer = LicenseIssuer(dsn, Ed25519PrivateKey.generate())
    machine = Ed25519PrivateKey.generate()
    public = wire.encode(machine.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return issuer, machine, public


def challenge_proof(issuer, activation_key, machine, public, installation_id=None, platform='windows'):
    challenge = issuer.challenge(activation_key, installation_id or str(uuid.uuid4()), public, platform)
    doc = wire.verify(challenge, 'challenge', issuer.keys, CHALLENGE_FIELDS)
    proof = wire.sign(machine, 'activation-proof', {field:doc[field] for field in PROOF_FIELDS})
    return challenge, proof, doc


def test_argon2_individual_salts_and_legacy_scrypt():
    first, second = password_hash(PASSWORD), password_hash(PASSWORD)
    assert first.startswith('$argon2id$') and first != second
    assert verify(PASSWORD, first) and not verify('wrong', first)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(PASSWORD.encode(),salt=salt,n=2**17,r=8,p=1,dklen=32,maxmem=256*1024*1024)
    assert verify(PASSWORD, f'scrypt$131072$8$1${salt.hex()}${digest.hex()}')


def test_forced_collision_and_persistent_hash_only(dsn):
    issuer, _, _ = issuer_and_machine(dsn)
    first = issuer.issue()
    values = iter([first['activation_key'],secrets.token_urlsafe(32)])
    issuer.random_key = lambda:next(values)
    second = issuer.issue()
    assert first != second
    assert query(dsn, 'SELECT count(*),count(DISTINCT key_hash) FROM hs_issuer_license') == [(2,2)]
    rows = str(query(dsn, 'SELECT * FROM hs_issuer_license'))
    assert first['activation_key'] not in rows and second['activation_key'] not in rows


def test_concurrent_issue_global_unique(dsn):
    issuer, _, _ = issuer_and_machine(dsn)
    with ThreadPoolExecutor(max_workers=8) as pool:
        issued = list(pool.map(lambda _:issuer.issue(),range(16)))
    assert len({row['activation_key'] for row in issued}) == 16
    assert query(dsn,'SELECT count(DISTINCT key_hash) FROM hs_issuer_license') == [(16,)]


def test_two_machines_race_and_lost_response_same_receipt(dsn):
    issuer, first_machine, public = issuer_and_machine(dsn)
    issued = issuer.issue()
    a, ap, ad = challenge_proof(issuer, issued['activation_key'], first_machine, public)
    second = Ed25519PrivateKey.generate()
    second_public = wire.encode(second.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw))
    b, bp, bd = challenge_proof(issuer,issued['activation_key'],second,second_public,platform='ubuntu')
    results = race(dsn,'SELECT * FROM hs_issuer_license WHERE license_id=%s FOR UPDATE',
        [lambda:issuer.activate(a,ap), lambda:issuer.activate(b,bp)],(issued['license_id'],))
    assert results.count('LICENSE_ALREADY_ACTIVATED') == 1
    winner = results[0] if isinstance(results[0],dict) else results[1]
    machine, pub, doc = (first_machine,public,ad) if isinstance(results[0],dict) else (second,second_public,bd)
    c, cp, _ = challenge_proof(issuer,issued['activation_key'],machine,pub,doc['installation_id'],doc['platform'])
    assert issuer.activate(c,cp) == winner  # retry after losing response, new possession proof
    assert caught(lambda:issuer.activate(c,cp)) == 'CHALLENGE_CONSUMED'
    assert query(dsn,'SELECT count(*) FROM hs_issuer_license') == [(1,)]
    receipt = wire.loads(wire.decode(winner['receipt']['payload']))
    assert 'expires_at' not in receipt


def test_expired_and_bad_proof_attempts_persist(dsn):
    issuer,machine,public = issuer_and_machine(dsn)
    issued = issuer.issue()
    a,proof,doc = challenge_proof(issuer,issued['activation_key'],machine,public)
    wrong = Ed25519PrivateKey.generate()
    bad = wire.sign(wrong,'activation-proof',{field:doc[field] for field in PROOF_FIELDS})
    for _ in range(5):
        assert caught(lambda:issuer.activate(a,bad)) == 'INVALID_PROOF'
    assert caught(lambda:issuer.activate(a,proof)) == 'RATE_LIMITED'
    a,proof,doc = challenge_proof(issuer,issued['activation_key'],machine,public)
    query(dsn,'UPDATE hs_issuer_challenge SET expires_at=0 WHERE challenge_id=%s',(doc['challenge_id'],))
    assert caught(lambda:issuer.activate(a,proof)) == 'CHALLENGE_EXPIRED'


def test_exact_bytes_unknown_fields_duplicate_json_and_wrong_purpose(dsn):
    issuer,machine,public = issuer_and_machine(dsn)
    issued = issuer.issue()
    a,proof,doc = challenge_proof(issuer,issued['activation_key'],machine,public)
    proof['payload'] = wire.encode(json.dumps({field:doc[field] for field in PROOF_FIELDS},indent=2).encode())
    assert caught(lambda:issuer.activate(a,proof)) == 'INVALID_PROOF'
    extra = {field:doc[field] for field in PROOF_FIELDS}
    extra['algorithm'] = 'none'
    assert caught(lambda:issuer.activate(a,wire.sign(machine,'activation-proof',extra))) == 'INVALID_PROOF'
    assert caught(lambda:issuer.activate(a,wire.sign(machine,'receipt',{field:doc[field] for field in PROOF_FIELDS}))) == 'INVALID_PROOF'
    with pytest.raises(ValueError):
        wire.loads('{"version":1,"version":2}')


def test_bootstrap_interrupted_resume_and_single_admin(dsn):
    auth = make_auth(dsn)
    binding = identity()
    actions = [lambda:auth.bootstrap(binding,'owner',PASSWORD),lambda:auth.bootstrap(binding,'owner',PASSWORD)]
    results = race(dsn,'SELECT id FROM hs_admin_throttle WHERE id=1 FOR UPDATE',actions)
    assert all(result['next_step']=='enroll' for result in results)
    one = auth.begin_enrollment(results[0]['challenge_token'])
    two = auth.begin_enrollment(results[1]['challenge_token'])
    assert one['manual_key'] == two['manual_key']
    assert query(dsn,'SELECT count(*) FROM hs_admin_account') == [(1,)]
    assert query(dsn,'SELECT count(*) FROM hs_admin_session') == [(0,)]
    # Simulate service restart: same protected key, persisted pending encrypted secret.
    resumed = MFAAdminAuth(dsn,protection_key=auth.fixture_protection_key)
    login = resumed.login('owner',PASSWORD)
    details = resumed.begin_enrollment(login['challenge_token'])
    assert details['manual_key']==one['manual_key']
    session = resumed.confirm_enrollment(login['challenge_token'],code_now(dsn,details['manual_key']))
    assert session['first_access']['status']=='not_issued'
    assert caught(lambda:auth.bootstrap(binding,'owner',PASSWORD))=='ALREADY_PROVISIONED'
    assert auth.administrator_state()=='ready'


def test_two_tabs_first_emission_retry_and_confirm(dsn):
    auth,secret,token,binding = enrolled(dsn)
    results = race(dsn,'SELECT id FROM hs_admin_throttle WHERE id=1 FOR UPDATE',
        [lambda:auth.issue_first_access_codes(token),lambda:auth.issue_first_access_codes(token)])
    assert results.count('CODES_ALREADY_ISSUED')==1
    issued = next(result for result in results if isinstance(result,dict))
    assert len(issued['recovery_codes'])==len(set(issued['recovery_codes']))==3
    assert all(len(code)==32 for code in issued['recovery_codes'])
    assert caught(lambda:auth.issue_first_access_codes(token))=='CODES_ALREADY_ISSUED'
    assert auth.first_access_status(token)['first_access']['status']=='pending'
    assert auth.confirm_first_access(token,1)==auth.confirm_first_access(token,1)
    assert auth.current(token)['first_access']['status']=='completed'
    rows = str(query(dsn,'SELECT * FROM hs_admin_recovery_v2'))
    assert all(code not in rows for code in issued['recovery_codes'])
    assert issued['first_access']['installation_id']==binding['installation_id']


def test_reissue_requires_password_and_new_totp_invalidates_generation(dsn):
    auth,secret,token,_ = enrolled(dsn)
    original = auth.issue_first_access_codes(token)
    fresh_step(dsn)
    assert caught(lambda:auth.regenerate_password_reset_codes(token,'wrong',code_now(dsn,secret)))=='REAUTHENTICATION_REQUIRED'
    second = auth.regenerate_password_reset_codes(token,PASSWORD,code_now(dsn,secret))
    assert second['first_access']['generation']==2
    assert caught(lambda:auth.confirm_first_access(token,1))=='GENERATION_CONFLICT'
    assert caught(lambda:auth.regenerate_password_reset_codes(token,PASSWORD,code_now(dsn,secret)))=='FACTOR_INVALID'
    fresh_step(dsn)
    assert caught(lambda:auth.reset_password('owner',original['recovery_codes'][0],NEW_PASSWORD,code_now(dsn,secret)))=='PASSWORD_RESET_INVALID'
    assert query(dsn,'SELECT count(*) FROM hs_admin_recovery_v2 WHERE revoked_at IS NULL')==[(3,)]


def test_simultaneous_password_recovery_atomic_sessions_revoked_mfa_preserved(dsn):
    auth,secret,token,_ = enrolled(dsn)
    codes = auth.issue_first_access_codes(token)['recovery_codes']
    old_state=query(dsn,'SELECT secret_cipher FROM hs_admin_mfa')[0][0]
    fresh_step(dsn)
    factor=code_now(dsn,secret)
    results=race(dsn,'SELECT id FROM hs_admin_throttle WHERE id=1 FOR UPDATE',
        [lambda:auth.reset_password('owner',codes[0],NEW_PASSWORD,factor),lambda:auth.reset_password('owner',codes[0],'another replacement password',factor)])
    assert sum(isinstance(result,dict) for result in results)==1
    assert results.count('PASSWORD_RESET_INVALID')==1
    assert query(dsn,'SELECT count(*) FROM hs_admin_recovery_v2 WHERE used_at IS NULL AND revoked_at IS NULL')==[(2,)]
    assert query(dsn,'SELECT secret_cipher FROM hs_admin_mfa')[0][0]==old_state
    assert caught(lambda:auth.current(token))=='SESSION_REVOKED'
    assert caught(lambda:auth.reset_password('owner',codes[1],NEW_PASSWORD,factor))=='FACTOR_INVALID'
    assert query(dsn,'SELECT count(*) FROM hs_admin_recovery_v2 WHERE used_at IS NOT NULL')==[(1,)]


def test_login_mfa_replay_challenge_expiry_and_no_admin_before_factor(dsn):
    auth,secret,token,_ = enrolled(dsn)
    challenge=auth.login('owner',PASSWORD)
    assert 'access_token' not in challenge
    assert caught(lambda:auth.current(challenge['challenge_token']))=='SESSION_INVALID'
    assert caught(lambda:auth.verify_login(challenge['challenge_token'],code_now(dsn,secret)))=='FACTOR_INVALID'
    fresh_step(dsn)
    session=auth.verify_login(challenge['challenge_token'],code_now(dsn,secret))
    assert session['token_type']=='Bearer'
    assert caught(lambda:auth.verify_login(challenge['challenge_token'],code_now(dsn,secret)))=='CHALLENGE_INVALID'
    expired=auth.login('owner',PASSWORD)
    query(dsn,"UPDATE hs_admin_mfa_challenge SET expires_at=clock_timestamp()-interval '1 second' WHERE token_hash=%s",(token_hash(expired['challenge_token']),))
    assert caught(lambda:auth.verify_login(expired['challenge_token'],code_now(dsn,secret)))=='CHALLENGE_INVALID'


def test_existing_legacy_without_receipt_login_enroll_and_valid_installation(dsn):
    salt=secrets.token_bytes(16)
    hashed=hashlib.scrypt(PASSWORD.encode(),salt=salt,n=2**17,r=8,p=1,dklen=32,maxmem=256*1024*1024)
    legacy=f'scrypt$131072$8$1${salt.hex()}${hashed.hex()}'
    query(dsn,'INSERT INTO hs_admin_account(id,username,password_hash) VALUES(1,%s,%s)',('owner',legacy))
    auth=make_auth(dsn)
    assert auth.administrator_state()=='migration_required'
    login=auth.login('owner',PASSWORD)
    assert login['next_step']=='enroll' and 'access_token' not in login
    assert query(dsn,'SELECT password_hash FROM hs_admin_account')[0][0].startswith('$argon2id$')
    details=auth.begin_enrollment(login['challenge_token'])
    session=auth.confirm_enrollment(login['challenge_token'],code_now(dsn,details['manual_key']))
    state=auth.current(session['access_token'])['first_access']
    uuid.UUID(state['installation_id'])
    assert state['contract_version']==2 and state['codes_remaining']==0
    assert auth.administrator_state()=='migration_required'
    assert auth.login('owner',PASSWORD)['next_step']=='login'


class FixtureInitialAccess:
    """Explicit test adapter only; never enabled by production composition."""
    def __init__(self):
        self.binding=identity()
        self.invalidated=False
    def require(self,request):
        if request.headers.get('cookie')!='fixture-local=authorized' or self.invalidated:
            raise AuthError(403,'INITIAL_ACCESS_REQUIRED')
        return self.binding
    def status(self,request):
        self.require(request)
        return {'status':'activated'}
    def retry(self,request):
        self.require(request)
        return {'status':'activated'}
    def invalidate(self):
        self.invalidated=True


def http_app(dsn, initial_access=None):
    app=FastAPI()
    def old_admin():
        return 'technical'
    @app.get('/api/v1/p11/health',dependencies=[Depends(old_admin)])
    def health():
        return {'ok':True}
    @app.post('/api/v1/p11/ingest/{kind}',dependencies=[Depends(old_admin)])
    def ingest(kind:str):
        return {'technical':True}
    auth=install_candidate_admin_auth(app,dsn,protection_key=Fernet.generate_key(),allowed_origins=['https://panel.example'],initial_access=initial_access)
    return app,auth


def test_http_failclosed_no_basic_admin_no_body_secret_leaks(dsn,caplog):
    app,auth=http_app(dsn)
    with TestClient(app) as client:
        response=client.post(PREFIX+'/bootstrap',json={'username':'owner','password':PASSWORD})
        assert response.status_code==403
        assert response.json()['error']['code']=='INITIAL_ACCESS_REQUIRED'
        assert client.get('/api/v1/p11/health',auth=('gateway-fixture','gateway-password-fixture')).status_code==401
        assert client.post('/api/v1/p11/ingest/telemetry',json={}).status_code==200
        response=client.post(PREFIX+'/password-reset/confirm',json={'username':'owner','code':'SECRET_RECOVERY','totp_code':'SECRET_TOTP','new_password':PASSWORD})
        assert response.status_code==422 and response.headers['cache-control']=='no-store'
        assert all(secret not in response.text+caplog.text for secret in (PASSWORD,'SECRET_RECOVERY','SECRET_TOTP'))
        response=client.post(PREFIX+'/login',content='{"username":"owner","password":"first","password":"second"}',headers={'content-type':'application/json'})
        assert response.status_code==422
        assert client.post(PREFIX+'/mfa/recover',json={'challenge_token':secrets.token_urlsafe(32),'code':'123456'}).status_code==403


def test_http_contract_bootstrap_codes_and_mfa_invalidates_initial_sessions(dsn,caplog):
    initial=FixtureInitialAccess()
    app,auth=http_app(dsn,initial)
    with TestClient(app) as client:
        headers={'cookie':'fixture-local=authorized'}
        response=client.post(PREFIX+'/bootstrap',json={'username':'owner','password':PASSWORD},headers=headers)
        assert response.status_code==200
        challenge=response.json()['challenge_token']
        details=client.post(PREFIX+'/mfa/enrollment/begin',json={'challenge_token':challenge}).json()
        response=client.post(PREFIX+'/mfa/enrollment/confirm',json={'challenge_token':challenge,'code':code_now(dsn,details['manual_key'])})
        assert response.status_code==200 and initial.invalidated
        body=response.json()
        assert 'recovery_codes' not in body
        bearer={'authorization':'Bearer '+body['access_token']}
        codes=client.post(PREFIX+'/first-access/codes',json={},headers=bearer)
        assert codes.status_code==200 and len(codes.json()['recovery_codes'])==3
        repeat=client.post(PREFIX+'/first-access/codes',json={},headers=bearer)
        assert repeat.status_code==409 and repeat.json()['first_access']['generation']==1
        assert 'recovery_codes' not in repeat.json()
        assert client.post(PREFIX+'/first-access/codes',json={'current_password':PASSWORD},headers=bearer).status_code==422
        assert client.post(PREFIX+'/first-access/confirm',json={'generation':1},headers=bearer).status_code==200
        schema=client.get('/openapi.json').json()
        assert '/api/v1/admin-auth/first-access/reissue' in schema['paths']
        for sensitive in (PASSWORD,details['manual_key'],details['provisioning_uri'],details['qr_svg'],body['access_token']):
            assert sensitive not in caplog.text
        assert all(code not in caplog.text for code in codes.json()['recovery_codes'])


def test_issuer_https_authorization_and_sanitized_errors(dsn,caplog):
    issuer,_,_=issuer_and_machine(dsn)
    credential=secrets.token_urlsafe(32)
    app=create_issuer_app(issuer,distributor_token=credential)
    with TestClient(app,base_url='https://issuer.example') as client:
        assert client.post('/api/v1/licenses/issue',json={}).status_code==401
        issued=client.post('/api/v1/licenses/issue',json={},headers={'authorization':'Bearer '+credential})
        assert issued.status_code==200
        response=client.post('/api/v1/licenses/challenges',json={'activation_key':issued.json()['activation_key'],'installation_id':'bad','installation_public_key':'bad','platform':'windows'})
        assert response.status_code==400
        assert issued.json()['activation_key'] not in response.text+caplog.text
        response=client.post('/api/v1/licenses/challenges',content='{"activation_key":"SECRET_LICENSE","activation_key":"other"}')
        assert response.status_code==400 and 'SECRET_LICENSE' not in response.text
    with TestClient(app) as client:
        assert client.post('/api/v1/licenses/issue',json={},headers={'x-forwarded-proto':'https'}).status_code==403
