"""Password-only recovery; shares MFA identity, durable throttle and transaction lock."""
import hmac
import secrets

from .mfa import MFAAdminAuth
from .passwords import password_hash
from .service import AuthError, checked_verify, token_hash, valid_password


class RecoverableAdminAuth(MFAAdminAuth):
    def issue_password_codes(self, token, password, code):
        with self.security_transaction('PASSWORD_CODES_ISSUE') as conn:
            self.session(conn, token)
            account = self.account(conn)
            if not checked_verify(password, account['password_hash']):
                raise AuthError(403, 'REAUTHENTICATION_REQUIRED')
            # A fresh current TOTP is mandatory, including for legacy accounts.
            self.totp(conn, code, self.state(conn))
            conn.execute('DELETE FROM hs_admin_password_code WHERE account_id=1')
            conn.execute('UPDATE hs_admin_password_grant SET consumed_at=clock_timestamp() WHERE consumed_at IS NULL')
            codes = [secrets.token_urlsafe(32) for _ in range(10)]
            for value in codes:
                conn.execute('INSERT INTO hs_admin_password_code(code_hash,account_id,credential_revision,expires_at) '
                             "VALUES(%s,1,%s,clock_timestamp()+interval '365 days')",
                             (token_hash(value), account['credential_revision']))
            self.reset_throttle(conn)
        return {'password_recovery_codes': codes, 'expires_in_seconds': 31536000}

    def validate_password_code(self, username, code):
        with self.security_transaction('PASSWORD_RECOVERY_VALIDATE') as conn:
            account = self.account(conn)
            # The same failure for missing account, wrong username, stale or spent code.
            valid_format = isinstance(code, str) and len(code) == 43 and code.isascii()
            digest = token_hash(code) if valid_format else token_hash('invalid')
            row = conn.execute('UPDATE hs_admin_password_code SET used_at=clock_timestamp() '
                               'WHERE code_hash=%s AND account_id=1 AND used_at IS NULL '
                               'AND expires_at>clock_timestamp() AND credential_revision=%s '
                               'AND %s RETURNING code_hash',
                               (digest, account['credential_revision'] if account else -1,
                                bool(account and hmac.compare_digest(username.encode(), account['username'].encode())))).fetchone()
            if not row:
                raise AuthError(401, 'RECOVERY_INVALID')
            grant = secrets.token_urlsafe(32)
            expiry = conn.execute('INSERT INTO hs_admin_password_grant(token_hash,account_id,credential_revision,expires_at) '
                                  "VALUES(%s,1,%s,clock_timestamp()+interval '5 minutes') RETURNING expires_at",
                                  (token_hash(grant), account['credential_revision'])).fetchone()
            self.reset_throttle(conn)
        return {'reset_token': grant, 'next_step': 'reset_password', 'expires_at': expiry['expires_at'].isoformat()}

    def reset_password(self, token, password):
        valid_password(password)
        self.separate_credentials(password=password)
        with self.security_transaction('PASSWORD_RECOVERY_COMPLETE') as conn:
            account = self.account(conn)
            try:
                digest = self.digest(token)
            except AuthError:
                raise AuthError(401, 'RECOVERY_INVALID') from None
            row = conn.execute('UPDATE hs_admin_password_grant SET consumed_at=clock_timestamp() '
                               'WHERE token_hash=%s AND consumed_at IS NULL AND expires_at>clock_timestamp() '
                               'AND credential_revision=%s RETURNING token_hash',
                               (digest, account['credential_revision'] if account else -1)).fetchone()
            if not row:
                raise AuthError(401, 'RECOVERY_INVALID')
            conn.execute('UPDATE hs_admin_account SET password_hash=%s,credential_revision=credential_revision+1, '
                         'updated_at=clock_timestamp() WHERE id=1', (password_hash(password),))
            self.revoke(conn)
            self.reset_throttle(conn)
        return {'status': 'credentials_changed', 'login_required': True, 'sessions_revoked': 'all'}

    @staticmethod
    def revoke(conn):
        MFAAdminAuth.revoke(conn)
        conn.execute('UPDATE hs_admin_password_grant SET consumed_at=clock_timestamp() WHERE consumed_at IS NULL')
