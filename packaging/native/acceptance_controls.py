"""Disposable native PostgreSQL acceptance; not installer/reboot/clean-OS proof."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres-bin', required=True, type=Path)
    args = parser.parse_args()
    for folder in ('backend', 'backend/domain', 'backend/delivery_tests', 'genai', 'packaging/native'):
        sys.path.insert(0, str(ROOT/folder))
    import psycopg
    private_root = ROOT/'.native-test'
    private_root.mkdir(exist_ok=True)
    private = Path(tempfile.mkdtemp(prefix='controls-', dir=private_root))
    password = secrets.token_urlsafe(32)
    password_file = private/'postgres.secret'
    password_file.write_text(password, encoding='utf-8')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    suffix = '.exe' if os.name == 'nt' else ''
    def run(name, *arguments):
        with (private/'process.log').open('ab') as log:
            subprocess.run([str(args.postgres_bin/(name+suffix)), *map(str, arguments)],
                           stdout=log, stderr=log, check=True, timeout=180)
    started = False
    try:
        run('initdb', '-D', private/'postgres', '-U', 'native_installer', '--encoding=UTF8',
            '--auth=scram-sha-256', '--pwfile', password_file)
        with (private/'postgres/postgresql.conf').open('a', encoding='utf-8') as stream:
            stream.write(f"\nlisten_addresses='127.0.0.1'\nport={port}\n")
        run('pg_ctl', '-D', private/'postgres', '-l', private/'server.log', '-w', 'start')
        started = True
        # Exercise the same provisioning/configuration path used by both installers.
        from provision import create_state, initialize_database, prepare_database
        installation = private/'installation'
        state = create_state(installation)
        state['dsn'] = state['dsn'].replace(':15432/', f':{port}/')
        (installation/'pg-init.secret').write_text(password, encoding='utf-8')
        state_file = installation/'state.json'
        state_file.write_text(json.dumps(state), encoding='utf-8')
        initialize_database(state, installation)
        prepare_database(state_file)
        # Installer recovery/configuration must remain idempotent, without operator SQL.
        prepare_database(state_file)
        os.environ['TEST_DATABASE_URL'] = state['dsn']
        suite = unittest.TestSuite()
        for module in ('test_delivery', 'test_control_state', 'test_operational_state'):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
        evidence = {'runtime': 'native-postgresql', 'docker': False, 'platform': sys.platform,
                    'tests_run': result.testsRun, 'failures': len(result.failures),
                    'errors': len(result.errors), 'skipped': len(result.skipped),
                    'clean_os': False, 'installer_run': False, 'reboot': False,
                    'autostart': 'not_tested', 'admin_login': 'not_tested',
                    'native_provisioning': True,
                    'native_configuration_repeated': True,
                    'source_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                        for name in ('backend/delivery/controls.py', 'backend/delivery/routes.py',
                                     'backend/delivery/operational_queue.py', 'backend/delivery/simulation.py',
                                     'packaging/native/provision.py')},
                    'new_dependencies': [], 'passed': result.wasSuccessful()}
        destination = ROOT/'docs/evidence/control-state'
        destination.mkdir(parents=True, exist_ok=True)
        (destination/'native-postgresql.json').write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
        (destination/'tests.txt').write_text(output.getvalue(), encoding='utf-8')
        print(json.dumps(evidence))
        return 0 if result.wasSuccessful() else 1
    finally:
        if started: run('pg_ctl', '-D', private/'postgres', '-m', 'fast', '-w', 'stop')


if __name__ == '__main__': sys.exit(main())
