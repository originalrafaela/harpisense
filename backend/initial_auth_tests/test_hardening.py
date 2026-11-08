from pathlib import Path
import uuid
import psycopg
import pytest
from admin_auth import first_access
from admin_auth import mfa
from admin_auth.service import AuthError, token_hash
from admin_auth.passwords import password_hash
from test_initial_auth import (enrolled, query, caught, fresh_step, code_now, PASSWORD, NEW_PASSWORD, make_auth)


def test_password_reset_rolls_back_factor_and_code_on_late_failure(dsn,monkeypatch):
    auth,secret,token,_=enrolled(dsn)
    code=auth.issue_first_access_codes(token)['recovery_codes'][0]
    fresh_step(dsn)
    def fail_hash(password):
        raise AuthError(503,'AUTH_UNAVAILABLE')
    monkeypatch.setattr(mfa,'password_hash',fail_hash)
    assert caught(lambda:auth.reset_password('owner',code,NEW_PASSWORD,code_now(dsn,secret)))=='AUTH_UNAVAILABLE'
    assert query(dsn,'SELECT last_step FROM hs_admin_mfa')==[(-1,)]
    assert query(dsn,'SELECT count(*) FROM hs_admin_recovery_v2 WHERE used_at IS NOT NULL')==[(0,)]
    assert auth.current(token)['authenticated']


def test_reissue_random_failure_preserves_old_set_and_totp(dsn,monkeypatch):
    auth,secret,token,_=enrolled(dsn)
    original=auth.issue_first_access_codes(token)
    fresh_step(dsn)
    monkeypatch.setattr(first_access.secrets,'token_urlsafe',lambda _: 'A'*32)
    assert caught(lambda:auth.regenerate_password_reset_codes(token,PASSWORD,code_now(dsn,secret)))=='AUTH_UNAVAILABLE'
    assert auth.first_access_status(token)['first_access']==original['first_access']
    assert query(dsn,'SELECT last_step FROM hs_admin_mfa')==[(-1,)]
    assert query(dsn,'SELECT count(*) FROM hs_admin_recovery_v2 WHERE revoked_at IS NULL')==[(3,)]


def test_failed_factor_attempts_survive_domain_savepoint(dsn):
    auth,secret,token,_=enrolled(dsn)
    challenge=auth.login('owner',PASSWORD)['challenge_token']
    wrong='000000' if code_now(dsn,secret)!='000000' else '111111'
    for _ in range(5):
        assert caught(lambda:auth.verify_login(challenge,wrong))=='FACTOR_INVALID'
    assert query(dsn,'SELECT attempts FROM hs_admin_mfa_challenge WHERE token_hash=%s',(token_hash(challenge),))==[(5,)]
    assert caught(lambda:auth.verify_login(challenge,wrong))=='TRY_LATER'
    assert query(dsn,"SELECT count(*) FROM hs_admin_audit WHERE result='FACTOR_INVALID'")==[(5,)]


@pytest.mark.parametrize('dsn',[4],indirect=True)
def test_migration_backfill_idempotent_preserves_ready_legacy_admin(dsn):
    auth=make_auth(dsn)
    secret='JBSWY3DPEHPK3PXP'
    cipher=auth.cipher.encrypt(secret.encode()).decode()
    query(dsn,'INSERT INTO hs_admin_account(id,username,password_hash) VALUES(1,%s,%s)',('owner',password_hash(PASSWORD)))
    query(dsn,'INSERT INTO hs_admin_mfa(account_id,required,secret_cipher,enabled_at) VALUES(1,true,%s,clock_timestamp())',(cipher,))
    with auth.transaction() as conn:
        verified=auth.issue_session(conn,auth.account(conn))['access_token']
        unverified=auth.issue_session(conn,auth.account(conn))['access_token']
        conn.execute('UPDATE hs_admin_session SET mfa_verified=true WHERE token_hash=%s',(token_hash(verified),))
    migration=(Path(__file__).resolve().parents[1]/'admin_auth/005_initial_auth_v2.sql').read_text()
    with psycopg.connect(dsn,autocommit=True) as conn:
        conn.execute(migration)
        original=conn.execute('SELECT installation_id FROM hs_admin_account').fetchone()[0]
        conn.execute(migration)
        assert conn.execute('SELECT installation_id FROM hs_admin_account').fetchone()[0]==original
    uuid.UUID(str(original))
    assert auth.administrator_state()=='migration_required'
    assert auth.current(verified)['first_access']['installation_id']==str(original)
    assert caught(lambda:auth.current(unverified))=='SESSION_REVOKED'
    login=auth.login('owner',PASSWORD)
    assert login['next_step']=='login'
    assert auth.verify_login(login['challenge_token'],code_now(dsn,secret))['token_type']=='Bearer'
    assert query(dsn,'SELECT secret_cipher FROM hs_admin_mfa')==[(cipher,)]


def test_old_human_composition_refuses_startup_without_mfa_key():
    from delivery.app import build_candidate_app
    with pytest.raises(RuntimeError,match='MFA_COMPOSITION_REQUIRED'):
        build_candidate_app(installation_id='legacy-installed',capabilities=None,allowed_origins=['https://panel.example'])
