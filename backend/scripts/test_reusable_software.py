"""Run the isolated PostgreSQL/HTTP matrix; emit only sanitized result metadata."""
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend/admin_auth_tests'), str(ROOT/'backend'),
               str(ROOT/'backend/domain'), str(ROOT/'genai')]
import psycopg


def main():
    dsn = os.environ['ADMIN_MFA_TEST_DATABASE_URL']
    with psycopg.connect(dsn) as conn:
        if conn.info.dbname != 'auth_fixture':
            raise RuntimeError('Disposable auth_fixture required')
        version = conn.execute('SHOW server_version').fetchone()[0]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromName(name) for name in (
        'test_password_recovery.PasswordRecoveryTests', 'test_reusable_software.ReusableTests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'at':datetime.now(timezone.utc).isoformat(), 'postgresql':version,
        'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skipped':len(result.skipped),'success':result.wasSuccessful(),
        'transport':'TCP loopback + ASGI regression','database':'disposable auth_fixture',
        'operational_deployment':False}, ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)


if __name__ == '__main__':
    main()
