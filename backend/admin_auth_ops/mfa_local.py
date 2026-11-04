"""Linux installer/operator helper. No service restart or shared bootstrap edits.

python -m admin_auth_ops.mfa_local key|bootstrap|recover --key-file /absolute/path
Grant destination is a new 0600 file. Never emits secrets on stdout/stderr.
DATABASE_URL is inherited from the installer's existing secret mechanism.
"""
import argparse
import os
import stat
from pathlib import Path

from cryptography.fernet import Fernet

from admin_auth.mfa import MFAAdminAuth


def private_file(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError('An absolute private regular file is required')
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise ValueError('Owner-only file required')
    return path


def create_private(path, content):
    target = Path(path)
    if not target.is_absolute() or target.parent.is_symlink():
        raise ValueError('Absolute local private path required')
    parent = target.parent.stat()
    if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o077:
        raise ValueError('Create an owner-only directory first')
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['key', 'bootstrap', 'recover'])
    parser.add_argument('--key-file', required=True)
    parser.add_argument('--grant-file')
    args = parser.parse_args()
    if os.name != 'posix':
        parser.error('Installer helper requires Linux owner/mode controls')
    if args.operation == 'key':
        create_private(args.key_file, Fernet.generate_key())
        return
    key = private_file(args.key_file).read_bytes().strip()
    # Reserve file before issuing DB grant; do not replace an existing local file.
    if not args.grant_file:
        parser.error('--grant-file required')
    create_private(args.grant_file, b'')
    try:
        auth = MFAAdminAuth(os.environ['DATABASE_URL'], protection_key=key)
        token = auth.issue_local_grant('bootstrap' if args.operation == 'bootstrap' else 'recover')
        path = private_file(args.grant_file)
        with path.open('wb') as stream:
            stream.write(token.encode('ascii'))
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        # Empty file is safe; operator removes it before retry. Never print DSN.
        raise SystemExit('Local grant failed; inspect sanitized audit and private file') from None


if __name__ == '__main__':
    main()
