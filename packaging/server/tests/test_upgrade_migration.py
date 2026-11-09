"""Real PostgreSQL upgrade with a restricted runtime role and a legacy account."""
import importlib.util
import os
from pathlib import Path
import sys
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/p) for p in ('backend','backend/domain','genai')]


def test_upgrade_keeps_legacy_identity_and_grants_runtime_no_ddl():
    base = os.environ['INITIAL_AUTH_TEST_DSN']
    with psycopg.connect(base) as conn:
        assert conn.info.dbname == 'auth_initial_fixture'
    suffix = uuid.uuid4().hex[:16]
    database, role = 'gateway_upgrade_' + suffix, 'gateway_runtime_' + suffix
    spec = importlib.util.spec_from_file_location('gateway_upgrade_test', ROOT/'packaging/server/upgrade_gateway.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    # Source tree keeps backend under ROOT, release flattens only entry scripts.
    with psycopg.connect(base, autocommit=True) as owner:
        owner.execute(sql.SQL('CREATE ROLE {} LOGIN').format(sql.Identifier(role)))
        owner.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
    dsn = make_conninfo(base, dbname=database, options='-c search_path=public')
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute((ROOT/'backend/admin_auth/001_admin_auth.sql').read_text())
            conn.execute((ROOT/'backend/config_manager/001_config_manager.sql').read_text())
            # Existing tables are accessible to runtime; public CREATE is not.
            conn.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(role)))
            conn.execute(sql.SQL('GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(role)))
            conn.execute(sql.SQL('GRANT USAGE ON SCHEMA hs_config TO {}').format(sql.Identifier(role)))
            conn.execute('INSERT INTO hs_admin_account(id,username,password_hash) VALUES(1,%s,%s)', ('legacy-fixture','unchanged-fixture-verifier'))
            before = conn.execute('SELECT username,password_hash,credential_revision FROM hs_admin_account').fetchone()
            conn.execute(module.migration_sql(role))
            assert before == conn.execute('SELECT username,password_hash,credential_revision FROM hs_admin_account').fetchone()
            assert conn.execute('SELECT license_id FROM hs_admin_account').fetchone() == (None,)
        with psycopg.connect(make_conninfo(dsn, user=role)) as runtime:
            assert not runtime.execute("SELECT has_schema_privilege(current_user,'public','CREATE')").fetchone()[0]
            assert runtime.execute('SELECT version FROM hs_admin_mfa_schema').fetchone() == (1,)
            assert runtime.execute('SELECT revision FROM hs_control').fetchone() == (1,)
            for table, seq in [('hs_control_audit','hs_control_audit_id_seq'),
                               ('hs_incident_assessment','hs_incident_assessment_id_seq'),
                               ('hs_activity_event','hs_activity_event_id_seq')]:
                assert runtime.execute('SELECT has_table_privilege(current_user,%s,\'INSERT\'),has_sequence_privilege(current_user,%s,\'USAGE\')', (table,seq)).fetchone() == (True,True)
            assert runtime.execute("SELECT has_table_privilege(current_user,'hs_config.asset','SELECT'),has_table_privilege(current_user,'hs_config.asset_audit','INSERT')").fetchone() == (True,True)
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(module.migration_sql(role))
            assert before == conn.execute('SELECT username,password_hash,credential_revision FROM hs_admin_account').fetchone()
    finally:
        with psycopg.connect(base, autocommit=True) as owner:
            owner.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
            owner.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
