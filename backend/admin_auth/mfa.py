"""Opt-in candidate. Same identity, transaction lock, password and sessions as v1.

Do not select this class in the shared bootstrap before coordinated integration.
All security decisions use PostgreSQL clock and the existing singleton lock.
"""
import hmac
import io
import re
import secrets
from contextlib import contextmanager

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken

from .service import (AdminAuth, AuthError, checked_verify, token_hash,
                      valid_password, valid_username)
from .passwords import password_hash


class MFAAdminAuth(AdminAuth):
    def __init__(self, conninfo, *, protection_key, technical_credentials=()):
        super().__init__(conninfo, technical_credentials=technical_credentials)
        # Supplied by installer from an owner-only file OUTSIDE DB/backups/repo.
        self.cipher = Fernet(protection_key)

    @contextmanager
    def security_transaction(self, event):
        error = None
        with self.transaction() as conn:
            if conn.execute('SELECT version FROM hs_admin_mfa_schema').fetchone() != {'version': 1}:
                raise AuthError(503, 'AUTH_UNAVAILABLE')
            try:
                blocked = self.throttle(conn)
                if blocked:
                    raise blocked
                yield conn
            except AuthError as exc:
                error = exc
                if exc.status in (401, 403):
                    self.failed(conn)
                self.audit(conn, event, exc.code)
            else:
                self.audit(conn, event, 'OK', 1)
        if error:
            raise error

    @staticmethod
    def account(conn):
        return conn.execute('SELECT * FROM hs_admin_account WHERE id=1').fetchone()

    @staticmethod
    def state(conn):
        return conn.execute('SELECT * FROM hs_admin_mfa WHERE account_id=1').fetchone()

    @staticmethod
    def reset_throttle(conn):
        conn.execute("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity' WHERE id=1")

    def provision(self, username, password):
        # No bypass through the old local account creator in candidate mode.
        raise AuthError(409, 'PROTECTED_BOOTSTRAP_REQUIRED')

    def issue_local_grant(self, purpose='bootstrap', ttl_seconds=600):
        """Installer/operator ONLY, no HTTP endpoint. Returns secret once to caller.

        Caller MUST write directly to an owner-only local file, never stdout/logs.
        Recovery requires external operator identity verification and approval.
        """
        if purpose not in ('bootstrap', 'recover') or not 60 <= ttl_seconds <= 900:
            raise ValueError('Invalid local grant policy')
        with self.transaction() as conn:
            account = self.account(conn)
            if (purpose == 'bootstrap' and account) or (purpose == 'recover' and not account):
                raise AuthError(409, 'GRANT_NOT_ALLOWED')
            token = secrets.token_urlsafe(32)
            conn.execute('INSERT INTO hs_admin_local_grant(id,token_hash,purpose,credential_revision,expires_at) '
                         'VALUES(1,%s,%s,%s,clock_timestamp()+make_interval(secs=>%s)) '
                         'ON CONFLICT(id) DO UPDATE SET token_hash=excluded.token_hash,purpose=excluded.purpose, '
                         'credential_revision=excluded.credential_revision,expires_at=excluded.expires_at,consumed_at=NULL',
                         (token_hash(token), purpose, account['credential_revision'] if account else None, ttl_seconds))
            self.audit(conn, 'LOCAL_GRANT', purpose.upper(), 1 if account else None)
            return token

    def consume_grant(self, conn, token, purpose):
        digest = self.digest(token)
        row = conn.execute('SELECT *,expires_at>clock_timestamp() AS valid FROM hs_admin_local_grant WHERE id=1').fetchone()
        account = self.account(conn)
        if (not row or not row['valid'] or row['consumed_at'] or row['purpose'] != purpose
                or not hmac.compare_digest(row['token_hash'], digest)
                or (purpose == 'recover' and (not account or row['credential_revision'] != account['credential_revision']))):
            raise AuthError(401, 'GRANT_INVALID')
        conn.execute('UPDATE hs_admin_local_grant SET consumed_at=clock_timestamp() WHERE id=1')

    @staticmethod
    def digest(token):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            raise AuthError(401, 'TOKEN_INVALID')
        return token_hash(token)

    def challenge(self, conn, account, purpose):
        token = secrets.token_urlsafe(32)
        row = conn.execute('INSERT INTO hs_admin_mfa_challenge(token_hash,account_id,credential_revision,purpose,expires_at) '
                           "VALUES(%s,1,%s,%s,clock_timestamp()+interval '5 minutes') RETURNING expires_at",
                           (token_hash(token), account['credential_revision'], purpose)).fetchone()
        return {'challenge_token': token, 'next_step': purpose, 'expires_at': row['expires_at'].isoformat()}

    def get_challenge(self, conn, token, purpose):
        row = conn.execute('SELECT c.*,a.username,a.credential_revision AS current_revision, '
                           'c.expires_at>clock_timestamp() AS valid FROM hs_admin_mfa_challenge c '
                           'JOIN hs_admin_account a ON a.id=c.account_id WHERE c.token_hash=%s',
                           (self.digest(token),)).fetchone()
        if (not row or not row['valid'] or row['consumed_at'] or row['purpose'] != purpose
                or row['credential_revision'] != row['current_revision'] or row['attempts'] >= 5):
            raise AuthError(401, 'CHALLENGE_INVALID')
        # Failed checks commit, including this per-challenge attempt counter.
        conn.execute('UPDATE hs_admin_mfa_challenge SET attempts=attempts+1 WHERE token_hash=%s', (row['token_hash'],))
        return row

    def bootstrap(self, grant, username, password):
        valid_username(username); valid_password(password)
        self.separate_credentials(username=username, password=password)
        with self.security_transaction('BOOTSTRAP') as conn:
            if self.account(conn):
                raise AuthError(409, 'ALREADY_PROVISIONED')
            self.consume_grant(conn, grant, 'bootstrap')
            # Only an authorized local grant can trigger expensive password setup.
            encoded = password_hash(password)
            conn.execute('INSERT INTO hs_admin_account(id,username,password_hash) VALUES(1,%s,%s)', (username, encoded))
            conn.execute('INSERT INTO hs_admin_mfa(account_id,required) VALUES(1,true)')
            result = self.challenge(conn, self.account(conn), 'enroll')
        return result

    def login(self, username, password):
        with self.security_transaction('LOGIN') as conn:
            account = self.account(conn)
            correct = checked_verify(password, account['password_hash'] if account else self._dummy)
            if not account or not correct or not hmac.compare_digest(username.encode(), account['username'].encode()):
                raise AuthError(401, 'INVALID_CREDENTIALS')
            state = self.state(conn)
            if state and (state['enabled_at'] or state['required']):
                # No hs_admin_session row exists at the first-factor boundary.
                result = self.challenge(conn, account, 'login' if state['enabled_at'] else 'enroll')
            else:
                result = self.issue_session(conn, account)
                result['mfa_enrollment_required'] = False
                result['mfa_enrollment_available'] = True
                self.reset_throttle(conn)
        return result

    def decrypt(self, value):
        try:
            return self.cipher.decrypt(value.encode('ascii')).decode('ascii')
        except (InvalidToken, ValueError, UnicodeError, AttributeError):
            raise AuthError(503, 'MFA_KEY_UNAVAILABLE') from None

    def totp(self, conn, code, state):
        if not state or not state['enabled_at']:
            raise AuthError(403, 'MFA_NOT_ENABLED')
        step = self.match_step(conn, self.decrypt(state['secret_cipher']), code)
        if step <= state['last_step']:
            raise AuthError(401, 'FACTOR_INVALID')
        conn.execute('UPDATE hs_admin_mfa SET last_step=%s WHERE account_id=1', (step,))

    @staticmethod
    def match_step(conn, secret, code):
        # Strict current 30s step; no adjacent-window tolerance. Requires NTP.
        if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code):
            raise AuthError(401, 'FACTOR_INVALID')
        seconds = conn.execute('SELECT EXTRACT(EPOCH FROM clock_timestamp()) AS now').fetchone()['now']
        step = int(seconds) // 30
        if not hmac.compare_digest(pyotp.TOTP(secret).at(step * 30), code):
            raise AuthError(401, 'FACTOR_INVALID')
        return step

    def recover_code(self, conn, code):
        if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}', code):
            raise AuthError(401, 'FACTOR_INVALID')
        row = conn.execute('UPDATE hs_admin_recovery_code SET used_at=clock_timestamp() '
                           'WHERE code_hash=%s AND account_id=1 AND used_at IS NULL RETURNING code_hash',
                           (token_hash(code),)).fetchone()
        if not row:
            raise AuthError(401, 'FACTOR_INVALID')

    def verify_login(self, token, code, recovery=False):
        with self.security_transaction('MFA_RECOVERY' if recovery else 'MFA_LOGIN') as conn:
            challenge = self.get_challenge(conn, token, 'login')
            if recovery:
                self.recover_code(conn, code)
                # A recovery code grants only replacement enrollment, not admin access.
                self.revoke(conn)
                result = self.challenge(conn, self.account(conn), 'enroll')
            else:
                self.totp(conn, code, self.state(conn))
                result = self.issue_verified_session(conn, self.account(conn))
            conn.execute('UPDATE hs_admin_mfa_challenge SET consumed_at=clock_timestamp() WHERE token_hash=%s',
                         (challenge['token_hash'],))
            self.reset_throttle(conn)
        return result

    def issue_verified_session(self, conn, account):
        result = self.issue_session(conn, account)
        conn.execute('UPDATE hs_admin_session SET mfa_verified=true WHERE token_hash=%s', (token_hash(result['access_token']),))
        return result

    def session(self, conn, token):
        row = super().session(conn, token)
        state = self.state(conn)
        if state and (state['enabled_at'] or state['required']) and not row['mfa_verified']:
            raise AuthError(401, 'MFA_REQUIRED')
        return row

    def current(self, token):
        with self.transaction() as conn:
            row = self.session(conn, token)
            state = self.state(conn)
            return dict(authenticated=True, username=row['username'], expires_at=row['expires_at'].isoformat(),
                        idle_timeout_seconds=1800, mfa_available=True, mfa_enabled=bool(state and state['enabled_at']),
                        mfa_enrollment_available=True, email_recovery_available=False)

    def authorize_enrollment(self, token, password, code=None):
        """Existing-account opt-in or replacement. Password AND current factor when active."""
        with self.security_transaction('MFA_ENROLL_AUTHORIZE') as conn:
            self.session(conn, token)
            account = self.account(conn)
            if not checked_verify(password, account['password_hash']):
                raise AuthError(403, 'REAUTHENTICATION_REQUIRED')
            state = self.state(conn)
            if state and state['enabled_at']:
                self.totp(conn, code, state)
            result = self.challenge(conn, account, 'enroll')
        return result

    def begin_enrollment(self, token):
        with self.security_transaction('MFA_ENROLL_BEGIN') as conn:
            challenge = self.get_challenge(conn, token, 'enroll')
            if challenge['pending_cipher']:
                raise AuthError(409, 'ENROLLMENT_ALREADY_STARTED')
            secret = pyotp.random_base32()
            conn.execute('UPDATE hs_admin_mfa_challenge SET pending_cipher=%s WHERE token_hash=%s',
                         (self.cipher.encrypt(secret.encode()).decode(), challenge['token_hash']))
            uri = pyotp.TOTP(secret).provisioning_uri(name=challenge['username'], issuer_name='HarpiSense')
            qr = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
            stream = io.BytesIO()
            qr.save(stream)
            result = dict(manual_key=secret, provisioning_uri=uri, qr_svg=stream.getvalue().decode(),
                          expires_at=challenge['expires_at'].isoformat())
        return result

    @staticmethod
    def revoke(conn):
        conn.execute('UPDATE hs_admin_session SET revoked_at=clock_timestamp() WHERE revoked_at IS NULL')
        conn.execute('UPDATE hs_admin_mfa_challenge SET consumed_at=clock_timestamp() WHERE consumed_at IS NULL')
        conn.execute('UPDATE hs_admin_local_grant SET consumed_at=clock_timestamp() WHERE consumed_at IS NULL')

    def confirm_enrollment(self, token, code):
        with self.security_transaction('MFA_ENROLL_CONFIRM') as conn:
            challenge = self.get_challenge(conn, token, 'enroll')
            if not challenge['pending_cipher']:
                raise AuthError(409, 'ENROLLMENT_NOT_STARTED')
            step = self.match_step(conn, self.decrypt(challenge['pending_cipher']), code)
            conn.execute('INSERT INTO hs_admin_mfa(account_id,required,secret_cipher,last_step,enabled_at) '
                         'VALUES(1,true,%s,%s,clock_timestamp()) ON CONFLICT(account_id) DO UPDATE '
                         'SET required=true,secret_cipher=excluded.secret_cipher,last_step=excluded.last_step,enabled_at=excluded.enabled_at',
                         (challenge['pending_cipher'], step))
            self.revoke(conn)
            conn.execute('DELETE FROM hs_admin_recovery_code WHERE account_id=1')
            codes = [secrets.token_urlsafe(24) for _ in range(10)]
            for value in codes:
                conn.execute('INSERT INTO hs_admin_recovery_code(code_hash,account_id) VALUES(%s,1)', (token_hash(value),))
            result = self.issue_verified_session(conn, self.account(conn))
            result['recovery_codes'] = codes
            self.reset_throttle(conn)
        return result

    def local_recover(self, grant, username, password):
        with self.security_transaction('LOCAL_RECOVER') as conn:
            account = self.account(conn)
            correct = checked_verify(password, account['password_hash'] if account else self._dummy)
            if not account or not correct or not hmac.compare_digest(username.encode(), account['username'].encode()):
                raise AuthError(401, 'INVALID_CREDENTIALS')
            self.consume_grant(conn, grant, 'recover')
            self.revoke(conn)
            result = self.challenge(conn, account, 'enroll')
        return result

    def cancel_challenge(self, token):
        with self.security_transaction('MFA_CANCEL') as conn:
            conn.execute('UPDATE hs_admin_mfa_challenge SET consumed_at=clock_timestamp() '
                         'WHERE token_hash=%s AND consumed_at IS NULL', (self.digest(token),))
