"""Installer-only Windows ACL preparation, before API service startup."""
import hashlib
import json
import struct
from provision import run, write_private


def prepare_windows_activation(state, data, activation_key):
    import win32api
    import win32security
    digest = hashlib.sha1('HARPISENSEAPI'.encode('utf-16le')).digest()
    sid = 'S-1-5-80-' + '-'.join(str(x) for x in struct.unpack('<5I', digest))
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
    try:
        installer = win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token, win32security.TokenUser)[0])
    finally:
        token.Close()
    private = data/'activation'
    private.mkdir()
    run(['icacls', private, '/inheritance:r', '/grant:r', '*S-1-5-18:(OI)(CI)F',
         '*' + sid + ':(OI)(CI)F', '*' + installer + ':(OI)(CI)F'])
    write_private(private/'activation.pending', activation_key)
    # New installation only: no persisted MFA exists yet. The API generates its
    # first protected key under its own DPAPI identity; setup never wraps that key.
    (data/'admin-mfa.key').unlink()
    state.update(activation_directory=str(private), key_file=str(private/'legacy-mfa.key'),
                 api_service_sid=sid, installer_sids=[installer],
                 handoff_pipe=r'\\.\pipe\HarpiSense-FirstUse')
    (data/'state.json').write_text(json.dumps(state), encoding='utf-8')
    if installer != 'S-1-5-18':
        run(['icacls', private, '/remove:g', '*' + installer])
    # Only traversal on the common root; no access to PostgreSQL administrator
    # credentials, cluster files, broker passwords or another service's state.
    run(['icacls', data, '/grant', '*' + sid + ':RX'])
    for path in (data/'state.json', data/'mqtt-ca.crt', data/'external-ca.crt'):
        if path.exists():
            run(['icacls', path, '/grant', '*' + sid + ':R'])
    run(['icacls', data/'logs', '/grant', '*' + sid + ':(OI)(CI)M'])
