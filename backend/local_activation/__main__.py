"""Installer-side browser handoff. Arguments contain only paths and public IDs."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description='HarpiSense authenticated first-use browser')
    parser.add_argument('--ipc', required=True)
    parser.add_argument('--server-identity', required=True, help='Public service SID or numeric UID')
    parser.add_argument('--chromium', required=True, help='Packaged offline Chromium executable')
    args = parser.parse_args()
    try:
        import os
        from .ipc import request_unix_handoff, request_windows_handoff, launch_first_use
        if os.name == 'nt':
            handoff = request_windows_handoff(args.ipc, expected_server_sid=args.server_identity)
        else:
            handoff = request_unix_handoff(args.ipc, expected_server_uid=int(args.server_identity))
        launch_first_use(handoff, chromium_executable=args.chromium)
        return 0
    except Exception:
        # Never print driver/HTTP/IPC exceptions: they can embed cookie material.
        print('FIRST_USE_HANDOFF_FAILED', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
