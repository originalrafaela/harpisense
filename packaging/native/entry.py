"""Frozen entrypoint for product runtime and installer maintenance."""
import argparse
import sys
from pathlib import Path

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
for path in ('backend', 'backend/domain', 'genai', 'packaging/native'):
    sys.path.insert(0, str(ROOT/path))


def main():
    if len(sys.argv)>1 and sys.argv[1]=='xai':
        from harpisense_xai.__main__ import main as xai_main
        return xai_main(sys.argv[2:])
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['check-runtime', 'api', 'consumer', 'prepare', 'probe', 'preflight', 'grant', 'first-access'])
    parser.add_argument('--state', type=Path)
    args = parser.parse_args()
    if args.operation in ('check-runtime', 'prepare'):
        from runtime_check import check_runtime
        check_runtime()
    if args.operation == 'check-runtime':
        return
    if args.state is None:
        parser.error('--state is required for this operation')
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
    if args.operation == 'first-access':
        from native_activation import launch_installer_browser
        launch_installer_browser(state, ROOT)
        return
    if args.operation == 'grant':
        raise SystemExit('MANUAL_GRANT_DISABLED_USE_LOCAL_FIRST_ACCESS')
    if args.operation == 'api':
        import uvicorn
        from urllib.parse import urlparse
        from native_activation import NativeActivationRuntime
        with NativeActivationRuntime(state, ROOT) as runtime:
            app = build_native_app(state, ROOT/'frontend/dist',
                                   initial_access=runtime.adapter,
                                   protection_key=runtime.totp_key)
            uvicorn.run(runtime.transport.wrap(app), host='127.0.0.1',
                        port=urlparse(state['panel_url']).port,
                        proxy_headers=False, access_log=False)
    elif args.operation == 'consumer':
        run_consumer(state)
    else:
        probe_broker(state)


if __name__ == '__main__':
    main()
