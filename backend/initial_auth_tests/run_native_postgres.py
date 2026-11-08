"""Run the real PostgreSQL suite on an isolated, loopback-only native cluster.

Usage: python backend/initial_auth_tests/run_native_postgres.py --pg-bin PATH
Creates only .pg-auth-test and auth_initial_fixture in that cluster; no existing
service, user database, VM or Docker is contacted. No secrets are printed.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin', required=True, type=Path)
    parser.add_argument('--edge-backend', type=Path, help='Optional Edge backend source for real TLS/DPAPI interoperability')
    parser.add_argument('--test', action='append', help='Run only specified pytest paths/node IDs')
    args = parser.parse_args()
    directory = ROOT/'.pg-auth-test'
    binaries = args.pg_bin.resolve()
    suffix = '.exe' if os.name == 'nt' else ''
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    def pg(command, *arguments, check=True):
        # Windows postmaster inherits pipe handles: communicate() would wait until
        # server shutdown even after pg_ctl exited. Use a file, never PIPE.
        log = ROOT/'backend/initial_auth_tests/.run'
        log.mkdir(exist_ok=True)
        with (log/'native-tools.log').open('a', encoding='utf-8') as output:
            return subprocess.run([str(binaries/(command+suffix)), *map(str, arguments)], cwd=ROOT,
                                  check=check, stdout=output, stderr=subprocess.STDOUT,
                                  timeout=60, creationflags=flags)
    if not (directory/'PG_VERSION').exists():
        pg('initdb','-D',directory,'-U','hs_auth_fixture','-A','trust','--encoding=UTF8','--locale=C')
    if (directory/'postmaster.pid').exists():
        raise RuntimeError('Test cluster already running; do not reuse or stop an unknown process')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port = sock.getsockname()[1]
    # Trust is confined to a dedicated ephemeral fixture listener on loopback.
    started = False
    try:
        pg('pg_ctl','-D',directory,'-l',directory/'server.log','-o',f'-h 127.0.0.1 -p {port}','-w','start')
        started = True
        import psycopg
        from psycopg.conninfo import make_conninfo
        base = make_conninfo(host='127.0.0.1',port=port,user='hs_auth_fixture',dbname='postgres')
        with psycopg.connect(base,autocommit=True) as conn:
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname='auth_initial_fixture'").fetchone():
                conn.execute('CREATE DATABASE auth_initial_fixture')
        environment = dict(os.environ, INITIAL_AUTH_TEST_DSN=make_conninfo(base,dbname='auth_initial_fixture'))
        tests=args.test or ['backend/initial_auth_tests/test_initial_auth.py','backend/initial_auth_tests/test_hardening.py']
        if args.edge_backend:
            environment['INITIAL_AUTH_EDGE_BACKEND']=str(args.edge_backend.resolve())
            tests.append('backend/initial_auth_tests/edge_http_interop.py')
        print('Native PostgreSQL '+(directory/'PG_VERSION').read_text().strip()+'; isolated fixture; concurrent lock observation enabled', flush=True)
        result = subprocess.run([sys.executable,'-m','pytest',*tests,'-q','--tb=short'],
                                cwd=ROOT,env=environment,creationflags=flags,
                                capture_output=True,text=True,timeout=180)
        print(result.stdout, flush=True)
        if result.stderr:
            print(result.stderr,file=sys.stderr,flush=True)
        return result.returncode
    except subprocess.CalledProcessError as exc:
        # Tool output contains only initdb/pg_ctl diagnostics, no credentials.
        print('Native PostgreSQL tool failed; see backend/initial_auth_tests/.run/native-tools.log', file=sys.stderr)
        return 1
    finally:
        if started:
            pg('pg_ctl','-D',directory,'-m','fast','-w','stop')


if __name__ == '__main__':
    raise SystemExit(main())
