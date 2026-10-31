"""Local one-time provisioner. No password arguments/env or public HTTP endpoint."""
import getpass
import os
import sys

from .service import AdminAuth, AuthError


def main():
    if len(sys.argv) != 2 or sys.argv[1] != 'provision':
        raise SystemExit('Usage: python -m admin_auth provision')
    if not sys.stdin.isatty():
        raise SystemExit('Interactive operator terminal required')
    username = input('HarpiSense administrator username: ')
    password = getpass.getpass('New HarpiSense password (8-128 characters): ')
    confirm = getpass.getpass('Confirm password: ')
    if password != confirm:
        raise SystemExit('Passwords do not match')
    try:
        AdminAuth(os.environ['HARPISENSE_DATABASE_URL']).provision(username, password)
    except AuthError as exc:
        raise SystemExit(exc.code) from None
    except KeyError:
        raise SystemExit('Existing HARPISENSE_DATABASE_URL required') from None
    print('Administrator provisioned; no session created.')


if __name__ == '__main__':
    main()
