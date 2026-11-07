"""Disposable native PostgreSQL fixture; never connects to an existing cluster."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/domain'),
                str(ROOT/'backend/delivery_tests')]
import psycopg
from delivery.action_review import ActionReview
from delivery.control_store import PostgresControls
from delivery.controls import Controls
from harpisense_engines import decide
from policy_fixtures import context, NOW
from test_delivery import IsolatedQueue


def main():
    # Explicit developer-supplied redistributable binaries; no system service use.
    binary = Path('D:/Programas/PostgreSQL/bin')
    port = 25439
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))
    private = ROOT/'.acceptance-private'/str(uuid.uuid4())
    private.mkdir(parents=True)
    password = secrets.token_urlsafe(32)
    secret = private/'password.secret'
    secret.write_text(password, encoding='utf-8')
    evidence = {'environment': 'disposable native PostgreSQL fixture on Windows host',
                'port': port, 'docker': False, 'installed_os_acceptance': False,
                'reboot': False, 'service_registration': False, 'checks': [],
                'base_commit': 'a8fef1f5810ad5077658a29fe2aa407ffd21df6d'}
    started = False
    def run(args):
        completed = subprocess.run([str(x) for x in args], stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode:
            raise RuntimeError('DISPOSABLE_POSTGRES_COMMAND_FAILED')
    def check(condition, label):
        if not condition: raise AssertionError(label)
        evidence['checks'].append(label)
    try:
        run([binary/'initdb.exe', '-D', private/'data', '-U', 'review_test',
             '--encoding=UTF8', '--auth=scram-sha-256', '--pwfile', secret])
        with (private/'data/postgresql.conf').open('a', encoding='utf-8') as stream:
            stream.write("\nlisten_addresses='127.0.0.1'\nport=25439\n")
        run([binary/'pg_ctl.exe', '-D', private/'data', '-l', private/'postgres.log', '-w', 'start'])
        started = True
        dsn = psycopg.conninfo.make_conninfo(host='127.0.0.1', port=port,
            user='review_test', password=password, dbname='postgres')
        with psycopg.connect(dsn) as conn:
            for name in ('001_local.sql', '006_action_review.sql'):
                conn.execute((ROOT/'backend/delivery'/name).read_text(encoding='utf-8'))
        controls = Controls(PostgresControls(dsn), IsolatedQueue())
        controls.change(value=dict(operation='SIMULATION', execution_enabled=True, autonomy_mode=1),
            expected_revision=1, actor='trial-admin', reason='isolated native PostgreSQL trial')
        ctx = context()
        bundle = decide(ctx, mode=1, now=NOW)
        key = bundle['decision']['decision_id']
        def resolve(tx, identifier):
            if identifier != key: raise ValueError('MISSING_EXACT_DECISION')
            return bundle, ctx, 'synthetic', 1
        review = ActionReview(controls, resolve)
        approval = review.approve(key, expected_action=bundle['decision']['action_fingerprint'],
            expected_revision=2, actor='trial-admin', now=NOW)
        check(not approval['dispatched'] and controls.get()['value']['autonomy_mode']==1,
              'M1_specific_approval_preserves_mode_without_dispatch')
        with psycopg.connect(dsn) as conn:
            check(conn.execute("SELECT count(*) FROM hs_action_review WHERE kind='result'").fetchone()[0]==0,
                  'approval_is_not_result')
        first = review.simulate(key, expected_revision=2, actor='trial-admin', now=NOW)
        restarted = ActionReview(Controls(PostgresControls(dsn), IsolatedQueue()), resolve)
        second = restarted.simulate(key, expected_revision=2, actor='trial-admin', now=NOW)
        check(first==second, 'repeat_after_new_connection_returns_same_simulation')
        check(first['origin']=='synthetic' and first['historical_profile']==1 and
              not first['mitigation_confirmed'], 'simulation_origin_and_historical_mode_preserved')
        with psycopg.connect(dsn) as conn:
            rows = conn.execute('SELECT kind,count(*) FROM hs_action_review GROUP BY kind').fetchall()
            check(dict(rows)=={'approval':1,'result':1,'verification':1}, 'separate_postgresql_records_once')
            operations = [r[0] for r in conn.execute('SELECT operation FROM hs_control_audit').fetchall()]
            check(all(operations.count('ACTION_'+k)==1 for k in ('APPROVAL','RESULT','VERIFICATION')),
                  'separate_audit_events_once')
            conn.execute((ROOT/'backend/delivery/006_action_review.sql').read_text(encoding='utf-8'))
            check(conn.execute('SELECT count(*) FROM hs_action_review').fetchone()[0]==3,
                  'additive_migration_preserves_records')
        check(controls.get()['value']['autonomy_mode']==1, 'M1_unchanged_after_simulated_replay')
        evidence['result'] = 'passed'
    except Exception as error:
        evidence.update(result='failed', failure_type=type(error).__name__)
        raise
    finally:
        if started:
            run([binary/'pg_ctl.exe', '-D', private/'data', '-w', 'stop', '-m', 'fast'])
        secret.unlink(missing_ok=True)
        target = ROOT/'docs/acceptance/security-postgres-result.json'
        target.write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8', newline='\n')
        print(json.dumps(evidence))


if __name__ == '__main__':
    main()
