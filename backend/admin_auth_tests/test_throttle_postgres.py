"""Focused real PostgreSQL 16+ regression; dedicated disposable database only.

Run with ADMIN_THROTTLE_TEST_DATABASE_URL naming admin_throttle_fixture.
No fallback to the product DSN, no production migration or service changes.
"""
import os
from pathlib import Path
import secrets
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

import psycopg
from cryptography.fernet import Fernet

from admin_auth.mfa import MFAAdminAuth
from admin_auth.service import AdminAuth, AuthError


@unittest.skipUnless(os.getenv('ADMIN_THROTTLE_TEST_DATABASE_URL'),
                     'Dedicated disposable PostgreSQL not configured')
class ThrottlePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['ADMIN_THROTTLE_TEST_DATABASE_URL']
        with psycopg.connect(cls.dsn) as conn:
            if conn.info.dbname != 'admin_throttle_fixture':
                raise RuntimeError('Only disposable admin_throttle_fixture accepted')
            if not conn.execute("SELECT to_regclass('hs_admin_schema_version')").fetchone()[0]:
                conn.execute((ROOT / 'backend/admin_auth/001_admin_auth.sql').read_text())
            conn.execute((ROOT / 'backend/admin_auth/002_admin_mfa.sql').read_text())
            print('PostgreSQL:', conn.execute('SHOW server_version').fetchone()[0])
        cls.auth = MFAAdminAuth(cls.dsn, protection_key=Fernet.generate_key())

    def setUp(self):
        with psycopg.connect(self.dsn) as conn:
            conn.execute('TRUNCATE hs_admin_mfa_challenge, hs_admin_recovery_code, '
                         'hs_admin_mfa, hs_admin_local_grant, hs_admin_session, '
                         'hs_admin_account, hs_admin_audit')
            conn.execute("UPDATE hs_admin_throttle SET failures=0, blocked_until='-infinity'")

    def test_fresh_sentinel_and_explicit_reset_allow_access(self):
        with self.auth.transaction() as conn:
            self.assertIsNone(AdminAuth.throttle(conn))
            conn.execute("UPDATE hs_admin_throttle SET failures=7, blocked_until=clock_timestamp()+interval '30 seconds'")
            self.auth.reset_throttle(conn)
            self.assertIsNone(AdminAuth.throttle(conn))
            self.assertEqual(conn.execute('SELECT failures FROM hs_admin_throttle').fetchone()['failures'], 0)

    def test_past_finite_deadline_allows_access(self):
        with self.auth.transaction() as conn:
            conn.execute("UPDATE hs_admin_throttle SET blocked_until=clock_timestamp()-interval '1 second'")
            self.assertIsNone(AdminAuth.throttle(conn))

    def test_future_deadline_preserves_429_and_retry_after(self):
        with self.auth.transaction() as conn:
            conn.execute("UPDATE hs_admin_throttle SET failures=7, blocked_until=clock_timestamp()+interval '30 seconds'")
            blocked = AdminAuth.throttle(conn)
            self.assertEqual((blocked.status, blocked.code), (429, 'TRY_LATER'))
            self.assertTrue(1 <= blocked.retry_after <= 30)
            self.assertEqual(conn.execute('SELECT failures FROM hs_admin_throttle').fetchone()['failures'], 7)

    def test_positive_infinity_fails_closed(self):
        with self.assertRaises(AuthError) as caught:
            with self.auth.transaction() as conn:
                conn.execute("UPDATE hs_admin_throttle SET blocked_until='infinity'")
                AdminAuth.throttle(conn)
        self.assertEqual((caught.exception.status, caught.exception.code), (503, 'AUTH_UNAVAILABLE'))

    def test_failed_attempts_still_create_cooldown(self):
        with self.auth.transaction() as conn:
            for _ in range(5):
                self.auth.failed(conn)
            blocked = AdminAuth.throttle(conn)
            self.assertEqual((blocked.status, blocked.code), (429, 'TRY_LATER'))
            self.assertGreaterEqual(blocked.retry_after, 1)

    def test_bootstrap_consumes_grant_without_partial_session(self):
        grant = self.auth.issue_local_grant()
        result = self.auth.bootstrap(grant, 'regression-owner', secrets.token_urlsafe(32))
        self.assertEqual(result['next_step'], 'enroll')
        self.assertNotIn('access_token', result)
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM hs_admin_account').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT count(*) FROM hs_admin_session').fetchone()[0], 0)
            self.assertTrue(conn.execute('SELECT consumed_at IS NOT NULL FROM hs_admin_local_grant').fetchone()[0])

    def test_blocked_bootstrap_does_not_consume_grant_or_create_account(self):
        grant = self.auth.issue_local_grant()
        with psycopg.connect(self.dsn) as conn:
            conn.execute("UPDATE hs_admin_throttle SET blocked_until=clock_timestamp()+interval '30 seconds'")
        with self.assertRaises(AuthError) as caught:
            self.auth.bootstrap(grant, 'regression-owner', secrets.token_urlsafe(32))
        self.assertEqual((caught.exception.status, caught.exception.code), (429, 'TRY_LATER'))
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM hs_admin_account').fetchone()[0], 0)
            self.assertTrue(conn.execute('SELECT consumed_at IS NULL FROM hs_admin_local_grant').fetchone()[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
