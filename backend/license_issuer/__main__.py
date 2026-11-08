"""Explicit issuer migration/HTTPS entrypoint. Secrets arrive through private files."""
import argparse
import logging
from pathlib import Path
import os

import psycopg
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .api import create_issuer_app
from .service import LicenseIssuer


def private_file(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('ISSUER_PRIVATE_FILE_REQUIRED')
    if os.name=='posix' and path.stat().st_mode & 0o077:
        raise ValueError('ISSUER_PRIVATE_FILE_PERMISSIONS')
    return path.read_bytes()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('migrate','serve'))
    parser.add_argument('--dsn-file',required=True)
    parser.add_argument('--signing-key-file')
    parser.add_argument('--distributor-token-file')
    parser.add_argument('--tls-cert')
    parser.add_argument('--tls-key')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',default=8443,type=int)
    args=parser.parse_args()
    try:
        dsn=private_file(args.dsn_file).decode('utf-8').strip()
        if args.action=='migrate':
            with psycopg.connect(dsn,autocommit=True) as conn:
                conn.execute(Path(__file__).with_name('001_issuer.sql').read_text(encoding='utf-8'))
            return
        if not all((args.signing_key_file,args.distributor_token_file,args.tls_cert,args.tls_key)):
            raise ValueError('ISSUER_HTTPS_CONFIGURATION_REQUIRED')
        key=load_pem_private_key(private_file(args.signing_key_file),password=None)
        if not isinstance(key,Ed25519PrivateKey):
            raise ValueError('ISSUER_ED25519_REQUIRED')
        credential=private_file(args.distributor_token_file).decode('ascii').strip()
        app=create_issuer_app(LicenseIssuer(dsn,key),distributor_token=credential)
    except Exception:
        # Never stringify parsing/connection exceptions that may include credentials.
        raise SystemExit('ISSUER_CONFIGURATION_UNAVAILABLE') from None
    import uvicorn
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    uvicorn.run(app,host=args.host,port=args.port,ssl_certfile=args.tls_cert,ssl_keyfile=args.tls_key,
                proxy_headers=False,access_log=False)


if __name__=='__main__':
    main()
