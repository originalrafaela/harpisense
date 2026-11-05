"""Frozen entrypoint for product runtime and installer maintenance."""
import argparse
import sys
from pathlib import Path

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
for path in ('backend', 'backend/domain', 'genai', 'packaging/native'):
    sys.path.insert(0, str(ROOT/path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['api', 'consumer', 'prepare', 'probe', 'preflight', 'grant'])
    parser.add_argument('--state', required=True, type=Path)
    args = parser.parse_args()
    if args.operation == 'preflight':
        from provision import preflight
        preflight(args.state.parent, ROOT, 'local_managed')
        return
    if args.operation == 'prepare':
        from provision import prepare_database
        prepare_database(args.state)
        return
    from native_server.runtime import load_state, build_native_app, run_consumer, probe_broker
    state = load_state(args.state)
    if args.operation == 'grant':
        import psycopg
        from admin_auth.mfa import MFAAdminAuth
        with psycopg.connect(state['dsn']) as conn:
            if conn.execute('SELECT 1 FROM hs_admin_account').fetchone():
                raise SystemExit('ACCOUNT_EXISTS_USE_EXISTING_LOGIN')
        grant = MFAAdminAuth(state['dsn'], protection_key=Path(state['key_file']).read_bytes()).issue_local_grant()
        with (args.state.parent/'bootstrap.secret').open('w', encoding='ascii') as stream:
            stream.write(grant)
        print('Grant renovado no arquivo privado bootstrap.secret; validade 10 minutos.')
        return
    if args.operation == 'api':
        import uvicorn
        from urllib.parse import urlparse
        uvicorn.run(build_native_app(state, ROOT/'frontend/dist'),
                    host='127.0.0.1', port=urlparse(state['panel_url']).port, access_log=False)
    elif args.operation == 'consumer':
        run_consumer(state)
    else:
        probe_broker(state)


if __name__ == '__main__':
    main()
