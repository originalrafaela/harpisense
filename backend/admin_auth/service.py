"""Same PostgreSQL as P11, separate identity tables, no migration on startup.

All account/session transitions serialize on a dedicated singleton row. Errors
are raised AFTER transaction commit so failed-login throttles/audit survive.
"""
import hashlib
import hmac
import math
import os
import re
import secrets
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .passwords import password_hash, verify


class AuthError(Exception):
    def __init__(self, status, code, retry_after=None):
        super().__init__(code)
        self.status, self.code, self.retry_after = status, code, retry_after


def valid_username(value):
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{3,64}', value, flags=re.ASCII):
        raise AuthError(422, 'INVALID_USERNAME')
    return value


def valid_password(value):
    if not 15 <= len(value) <= 128 or len(value.encode('utf-8')) > 512:
        raise AuthError(422, 'INVALID_PASSWORD')
    return value


def token_hash(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def checked_verify(password, encoded):
    try:
        return verify(password, encoded)
    except (ValueError, TypeError):
        raise AuthError(503, 'AUTH_UNAVAILABLE') from None


class AdminAuth:
    def __init__(self, conninfo, *, technical_credentials=()):
        # Accept the same conninfo formats as psycopg/PostgresStore.
        self.conninfo = conninfo
        self._technical = tuple(technical_credentials) + tuple(
            (os.getenv(user, ''), os.getenv(password, '')) for user, password in (
                ('HARPISENSE_ADMIN_USER', 'HARPISENSE_ADMIN_PASSWORD'),
                ('HARPI_ADMIN_USERNAME', 'HARPI_ADMIN_PASSWORD'),
                ('HARPI_GATEWAY_USERNAME', 'HARPI_GATEWAY_PASSWORD'),
                ('HARPI_MQTT_USERNAME', 'HARPI_MQTT_PASSWORD')))
        self._db_password = psycopg.conninfo.conninfo_to_dict(conninfo).get('password', '')
        self._dummy = password_hash(secrets.token_urlsafe(32))

    def separate_credentials(self, *, username=None, password=None):
        for technical_user, technical_password in self._technical:
            if username is not None and technical_user and hmac.compare_digest(username.encode(), technical_user.encode()):
                raise AuthError(422, 'TECHNICAL_CREDENTIAL_REUSE')
            if password is not None and technical_password and hmac.compare_digest(password.encode(), technical_password.encode()):
                raise AuthError(422, 'TECHNICAL_CREDENTIAL_REUSE')
        if password is not None and self._db_password and hmac.compare_digest(password.encode(), self._db_password.encode()):
            raise AuthError(422, 'TECHNICAL_CREDENTIAL_REUSE')

    @contextmanager
    def transaction(self):
        try:
            with psycopg.connect(self.conninfo, connect_timeout=5, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL lock_timeout = '5s'")
                conn.execute("SET LOCAL statement_timeout = '10s'")
                if conn.execute('SELECT id FROM hs_admin_throttle WHERE id=1 FOR UPDATE').fetchone() != {'id': 1}:
                    raise AuthError(503, 'AUTH_UNAVAILABLE')
                if conn.execute('SELECT version FROM hs_admin_schema_version').fetchone() != {'version': 1}:
                    raise AuthError(503, 'AUTH_UNAVAILABLE')
                yield conn
        except psycopg.Error:
            raise AuthError(503, 'AUTH_UNAVAILABLE') from None

    @staticmethod
    def audit(conn, event, result, account_id=None):
        conn.execute('INSERT INTO hs_admin_audit(event,result,account_id) VALUES(%s,%s,%s)',
                     (event, result, account_id))

    @staticmethod
    def throttle(conn):
        row = conn.execute('SELECT failures, EXTRACT(EPOCH FROM (blocked_until-clock_timestamp())) AS wait '
                           'FROM hs_admin_throttle WHERE id=1').fetchone()
        if row['wait'] > 0:
            return AuthError(429, 'TRY_LATER', max(1, math.ceil(row['wait'])))

    @staticmethod
    def failed(conn):
        conn.execute("UPDATE hs_admin_throttle SET failures=LEAST(failures+1,20), "
                     "blocked_until=clock_timestamp()+make_interval(secs=>CASE WHEN failures<4 THEN 0 "
                     "ELSE LEAST(60,power(2,LEAST(failures-3,6))::integer) END) WHERE id=1")

    def provision(self, username, password):
        """CLI/local operator only; deliberately no HTTP route or default account."""
        valid_username(username); valid_password(password)
        self.separate_credentials(username=username, password=password)
        encoded = password_hash(password)
        error = None
        with self.transaction() as conn:
            if conn.execute('SELECT id FROM hs_admin_account').fetchone():
                self.audit(conn, 'PROVISION', 'ALREADY_PROVISIONED', 1)
                error = AuthError(409, 'ALREADY_PROVISIONED')
            else:
                conn.execute('INSERT INTO hs_admin_account(id,username,password_hash) VALUES(1,%s,%s)',
                             (username, encoded))
                self.audit(conn, 'PROVISION', 'OK', 1)
        if error:
            raise error

    def login(self, username, password):
        error, result = None, None
        with self.transaction() as conn:
            error = self.throttle(conn)
            if error:
                self.audit(conn, 'LOGIN', error.code)
            if not error:
                account = conn.execute('SELECT * FROM hs_admin_account WHERE id=1').fetchone()
                correct = checked_verify(password, account['password_hash'] if account else self._dummy)
                same_name = account and hmac.compare_digest(username.encode(), account['username'].encode())
                if not (correct and same_name):
                    self.failed(conn)
                    error = AuthError(401, 'INVALID_CREDENTIALS')
                    self.audit(conn, 'LOGIN', error.code)
                else:
                    conn.execute("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity' WHERE id=1")
                    token = secrets.token_urlsafe(32)
                    row = conn.execute("INSERT INTO hs_admin_session(token_hash,account_id,credential_revision,expires_at) "
                                       "VALUES(%s,1,%s,clock_timestamp()+interval '8 hours') RETURNING expires_at",
                                       (token_hash(token), account['credential_revision'])).fetchone()
                    self.audit(conn, 'LOGIN', 'OK', 1)
                    result = dict(access_token=token, token_type='Bearer', expires_at=row['expires_at'].isoformat(),
                                  idle_timeout_seconds=1800, username=account['username'])
        if error:
            raise error
        return result

    def session(self, conn, token):
        if not token or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token, flags=re.ASCII):
            raise AuthError(401, 'AUTH_REQUIRED')
        row = conn.execute('SELECT s.*,a.username,a.credential_revision AS current_revision, '
                           'clock_timestamp() AS now FROM hs_admin_session s JOIN hs_admin_account a '
                           'ON a.id=s.account_id WHERE token_hash=%s', (token_hash(token),)).fetchone()
        if not row:
            raise AuthError(401, 'SESSION_INVALID')
        if row['revoked_at'] or row['credential_revision'] != row['current_revision']:
            raise AuthError(401, 'SESSION_REVOKED')
        if row['now'] >= row['expires_at'] or (row['now']-row['last_seen_at']).total_seconds() >= 1800:
            raise AuthError(401, 'SESSION_EXPIRED')
        conn.execute('UPDATE hs_admin_session SET last_seen_at=clock_timestamp() WHERE token_hash=%s',
                     (token_hash(token),))
        return row

    def current(self, token):
        with self.transaction() as conn:
            row = self.session(conn, token)
            return dict(authenticated=True, username=row['username'], expires_at=row['expires_at'].isoformat(),
                        idle_timeout_seconds=1800, mfa_available=False, email_recovery_available=False)

    def logout(self, token):
        with self.transaction() as conn:
            self.session(conn, token)
            conn.execute('UPDATE hs_admin_session SET revoked_at=clock_timestamp() WHERE token_hash=%s',
                         (token_hash(token),))
            self.audit(conn, 'LOGOUT', 'OK', 1)

    def change(self, token, current_password, *, password=None, username=None):
        if (password is None) == (username is None):
            raise AuthError(422, 'INVALID_CHANGE')
        if password is not None:
            valid_password(password)
        if username is not None:
            valid_username(username)
        error = None
        with self.transaction() as conn:
            self.session(conn, token)
            error = self.throttle(conn)
            event = 'PASSWORD_CHANGE' if password is not None else 'USERNAME_CHANGE'
            if error:
                self.audit(conn, event, error.code, 1)
            if not error:
                account = conn.execute('SELECT * FROM hs_admin_account WHERE id=1').fetchone()
                if not checked_verify(current_password, account['password_hash']):
                    self.failed(conn)
                    error = AuthError(403, 'REAUTHENTICATION_REQUIRED')
                    self.audit(conn, event, error.code, 1)
                else:
                    self.separate_credentials(username=username, password=password)
                    # Whitelisted field only; user content is always a bound parameter.
                    field, value = ('password_hash', password_hash(password)) if password is not None else ('username', username)
                    conn.execute(f'UPDATE hs_admin_account SET {field}=%s,credential_revision=credential_revision+1, '
                                 'updated_at=clock_timestamp() WHERE id=1', (value,))
                    conn.execute('UPDATE hs_admin_session SET revoked_at=clock_timestamp() WHERE revoked_at IS NULL')
                    conn.execute("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity' WHERE id=1")
                    self.audit(conn, event, 'OK', 1)
        if error:
            raise error
