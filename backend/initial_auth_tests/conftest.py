"""Disposable real PostgreSQL only. Every test gets a private schema."""
import os
import sys
import uuid
from pathlib import Path
import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/domain'), str(ROOT/'genai')]


@pytest.fixture
def dsn(request):
    base = os.getenv('INITIAL_AUTH_TEST_DSN')
    if not base:
        pytest.fail('INITIAL_AUTH_TEST_DSN must name disposable auth_initial_fixture (no skipped PostgreSQL evidence)')
    with psycopg.connect(base, autocommit=True) as conn:
        if conn.info.dbname != 'auth_initial_fixture':
            raise RuntimeError('Only disposable auth_initial_fixture is accepted')
        schema = 'auth_test_' + uuid.uuid4().hex
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    isolated = make_conninfo(base, options=f'-c search_path={schema}', application_name=schema)
    try:
        with psycopg.connect(isolated, autocommit=True) as conn:
            migrations=('001_admin_auth.sql','002_admin_mfa.sql','003_password_reset.sql','004_first_access.sql','005_initial_auth_v2.sql')
            for name in migrations[:getattr(request,'param',5)]:
                conn.execute((ROOT/'backend/admin_auth'/name).read_text(encoding='utf-8'))
            conn.execute((ROOT/'backend/license_issuer/001_issuer.sql').read_text(encoding='utf-8'))
        yield isolated
    finally:
        with psycopg.connect(base, autocommit=True) as conn:
            # Only the exact random test schema created above is removed.
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
